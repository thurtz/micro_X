#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory

import asyncio
import subprocess
import uuid # Still needed by ShellEngine if expand_shell_variables is static/helper
import shlex
import os
import re # Still needed by ShellEngine if expand_shell_variables is static/helper
import logging
import json
import time
import shutil
import hashlib
import sys

# Import the new ShellEngine class
from modules.shell_engine import ShellEngine

from modules.ai_handler import get_validated_ai_command, is_valid_linux_command_according_to_ai
# Import specific functions from category_manager that might be needed by ShellEngine or main
from modules.category_manager import (
    init_category_manager, classify_command,
    add_command_to_category as cm_add_command_to_category,
    handle_command_subsystem_input, UNKNOWN_CATEGORY_SENTINEL,
    CATEGORY_MAP as CM_CATEGORY_MAP, CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS
)
# output_analyzer is now imported directly within ShellEngine where needed
# from modules.output_analyzer import is_tui_like_output # Potentially used by ShellEngine's tmux execution
from modules.ollama_manager import (
    ensure_ollama_service, explicit_start_ollama_service, explicit_stop_ollama_service,
    explicit_restart_ollama_service, get_ollama_status_info
)
from modules.ui_manager import UIManager

LOG_DIR = "logs"
CONFIG_DIR = "config"
HISTORY_FILENAME = ".micro_x_history"
REQUIREMENTS_FILENAME = "requirements.txt"
UTILS_DIR_NAME = "utils"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True)
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME)
REQUIREMENTS_FILE_PATH = os.path.join(SCRIPT_DIR, REQUIREMENTS_FILENAME)
UTILS_DIR_PATH = os.path.join(SCRIPT_DIR, UTILS_DIR_NAME)
os.makedirs(UTILS_DIR_PATH, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)
logger = logging.getLogger(__name__)

config = {}
DEFAULT_CONFIG_FILENAME = "default_config.json"
USER_CONFIG_FILENAME = "user_config.json"
ollama_service_ready = False # This state might eventually move or be managed via ShellEngine/OllamaManager more directly

# --- Global instances (will be initialized in main_async_runner) ---
app_instance = None
ui_manager_instance = None
shell_engine_instance = None # New global for ShellEngine instance
# current_directory is now managed by ShellEngine instance

def merge_configs(base, override):
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_configuration():
    global config
    default_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, USER_CONFIG_FILENAME)
    # Fallback config remains the same
    fallback_config = {
        "ai_models": {"primary_translator": "llama3.2:3b", "direct_translator": "vitali87/shell-commands-qwen2-1.5b", "validator": "herawen/lisa:latest", "explainer": "llama3.2:3b"},
        "timeouts": {"tmux_poll_seconds": 300, "tmux_semi_interactive_sleep_seconds": 1},
        "behavior": {"input_field_height": 3, "default_category_for_unclassified": "simple", "validator_ai_attempts": 3, "translation_validation_cycles": 3, "ai_retry_delay_seconds": 1, "ollama_api_call_retries": 2},
        "ui": {"max_prompt_length": 20},
        "paths": {"tmux_log_base_path": "/tmp"},
        "prompts": {
            "validator": {"system": "You are a Linux command validation assistant...", "user_template": "Is the following string likely a Linux command: '{command_text}'"},
            "primary_translator": {"system": "You are a helpful assistant that translates human language queries...", "user_template": "Translate to a single Linux command: \"{human_input}\"."},
            "direct_translator": {"system": "Translate the following user request into a single Linux command...", "user_template": "Translate to a single Linux command: \"{human_input}\"."},
            "explainer": {"system": "You are a helpful assistant that explains Linux commands...", "user_template": "Explain the following Linux command: '{command_text}'"}
        },
        "ollama_service": {"executable_path": None, "auto_start_serve": True, "startup_wait_seconds": 10, "server_check_retries": 5, "server_check_interval_seconds": 2}
    }
    config = fallback_config.copy()
    logger.info("Initialized with hardcoded fallback general configurations.")
    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f: default_settings = json.load(f)
            config = merge_configs(config, default_settings)
            logger.info(f"Loaded general configurations from {default_config_path}")
        except Exception as e: logger.error(f"Error loading {default_config_path}: {e}.", exc_info=True)
    else:
        logger.warning(f"{default_config_path} not found. Creating it now.")
        try:
            os.makedirs(os.path.dirname(default_config_path), exist_ok=True)
            with open(default_config_path, 'w') as f: json.dump(fallback_config, f, indent=2)
            logger.info(f"Created default general configuration file at {default_config_path} with fallback values.")
        except Exception as e: logger.error(f"Could not create default config file: {e}", exc_info=True)

    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r') as f: user_settings = json.load(f)
            config = merge_configs(config, user_settings)
            logger.info(f"Loaded and merged general configurations from {user_config_path}")
        except Exception as e: logger.error(f"Error loading {user_config_path}: {e}.", exc_info=True)
    else: logger.info(f"{user_config_path} not found. No user general overrides applied.")

load_configuration()

def normal_input_accept_handler(buff):
    """
    Handles normal user input submission.
    This will eventually delegate to ShellEngine.submit_input.
    """
    # Reverted to call handle_input_async directly until ShellEngine.submit_input is implemented
    asyncio.create_task(handle_input_async(buff.text))


def restore_normal_input_handler():
    """ Restores the UI to normal input mode via UIManager. """
    global ui_manager_instance, shell_engine_instance
    if ui_manager_instance and shell_engine_instance:
        ui_manager_instance.set_normal_input_mode(normal_input_accept_handler, shell_engine_instance.current_directory)
    elif not ui_manager_instance:
        logger.warning("restore_normal_input_handler: ui_manager_instance is None.")
    elif not shell_engine_instance:
        logger.warning("restore_normal_input_handler: shell_engine_instance is None.")


def _exit_app_main():
    """ Callback for UIManager to exit the main application. """
    global app_instance
    if app_instance and app_instance.is_running:
        app_instance.exit()
    else:
        logger.warning("_exit_app_main called but app_instance not running or None.")

def get_file_hash(filepath):
    # This function is general utility, could stay or move to a utils module if not already there.
    # For now, keeping it here as it's used by handle_update_command.
    if not os.path.exists(filepath): return None
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f: hasher.update(f.read())
    return hasher.hexdigest()

async def handle_update_command():
    # This function is a built-in command handler, could potentially move to ShellEngine
    # or be called by ShellEngine. For now, keep in main.py.
    global ui_manager_instance # Needs UIManager for output
    if not ui_manager_instance: logger.error("handle_update_command: UIManager not initialized."); return
    ui_manager_instance.append_output("🔄 Checking for updates...", style_class='info')
    logger.info("Update command received.")
    current_app_inst = ui_manager_instance.get_app_instance()
    if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

    if not shutil.which("git"):
        ui_manager_instance.append_output("❌ Update failed: 'git' not found.", style_class='error')
        logger.error("Update failed: git not found."); return

    original_req_hash = get_file_hash(REQUIREMENTS_FILE_PATH); requirements_changed = False
    try:
        branch_process = await asyncio.to_thread(subprocess.run, ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=SCRIPT_DIR, capture_output=True, text=True, check=True)
        current_branch = branch_process.stdout.strip()
        ui_manager_instance.append_output(f"ℹ️ On branch: '{current_branch}'. Fetching updates...", style_class='info'); logger.info(f"Current git branch: {current_branch}")
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

        pull_process = await asyncio.to_thread(subprocess.run, ['git', 'pull', 'origin', current_branch], cwd=SCRIPT_DIR, capture_output=True, text=True)
        if pull_process.returncode == 0:
            ui_manager_instance.append_output(f"✅ Git pull successful.\nOutput:\n{pull_process.stdout.strip()}", style_class='success'); logger.info(f"Git pull output: {pull_process.stdout.strip()}")
            if "Already up to date." in pull_process.stdout: ui_manager_instance.append_output("✅ micro_X is up to date.", style_class='success')
            else:
                ui_manager_instance.append_output("✅ Updates downloaded.", style_class='success')
                if original_req_hash != get_file_hash(REQUIREMENTS_FILE_PATH): requirements_changed = True; ui_manager_instance.append_output("⚠️ requirements.txt changed.", style_class='warning'); logger.info("requirements.txt changed.")
                ui_manager_instance.append_output("💡 Restart micro_X for changes.", style_class='info')
                if requirements_changed: ui_manager_instance.append_output(f"💡 After restart, update dependencies:\n    cd \"{SCRIPT_DIR}\"\n    source .venv/bin/activate\n    pip install -r {REQUIREMENTS_FILENAME}", style_class='info')
        else: ui_manager_instance.append_output(f"❌ Git pull failed.\nError:\n{pull_process.stderr.strip()}", style_class='error'); logger.error(f"Git pull failed. Stderr: {pull_process.stderr.strip()}")
    except subprocess.CalledProcessError as e: ui_manager_instance.append_output(f"❌ Update failed: git error.\n{e.stderr}", style_class='error'); logger.error(f"Update git error: {e}", exc_info=True)
    except FileNotFoundError: ui_manager_instance.append_output("❌ Update failed: 'git' not found.", style_class='error'); logger.error("Update failed: git not found.")
    except Exception as e: ui_manager_instance.append_output(f"❌ Unexpected error during update: {e}", style_class='error'); logger.error(f"Unexpected update error: {e}", exc_info=True)
    finally:
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

async def handle_utils_command_async(full_command_str: str):
    # This function is a built-in command handler, could potentially move to ShellEngine
    # or be called by ShellEngine. For now, keep in main.py.
    global ui_manager_instance # Needs UIManager for output
    if not ui_manager_instance: logger.error("handle_utils_command_async: UIManager not initialized."); return
    logger.info(f"Handling /utils command: {full_command_str}")
    ui_manager_instance.append_output("🛠️ Processing /utils command...", style_class='info')
    current_app_inst = ui_manager_instance.get_app_instance()
    if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

    try: parts = shlex.split(full_command_str)
    except ValueError as e:
        ui_manager_instance.append_output(f"❌ Error parsing /utils command: {e}", style_class='error')
        logger.warning(f"shlex error for /utils '{full_command_str}': {e}")
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

    utils_help_message = "ℹ️ Usage: /utils <script_name_no_ext> [args...] | list | help"
    if len(parts) < 2:
        ui_manager_instance.append_output(utils_help_message, style_class='info')
        logger.debug("Insufficient arguments for /utils command.")
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

    subcommand_or_script_name = parts[1]; args = parts[2:]
    if subcommand_or_script_name.lower() in ["list", "help"]:
        try:
            if not os.path.exists(UTILS_DIR_PATH) or not os.path.isdir(UTILS_DIR_PATH):
                ui_manager_instance.append_output(f"❌ Utility directory '{UTILS_DIR_NAME}' not found at '{UTILS_DIR_PATH}'.", style_class='error'); logger.error(f"Utility directory not found: {UTILS_DIR_PATH}")
                if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
            available_scripts = [f[:-3] for f in os.listdir(UTILS_DIR_PATH) if os.path.isfile(os.path.join(UTILS_DIR_PATH, f)) and f.endswith(".py") and f != "__init__.py"]
            if available_scripts:
                ui_manager_instance.append_output("Available utility scripts (run with /utils <script_name>):", style_class='info')
                for script_name in sorted(available_scripts): ui_manager_instance.append_output(f"  - {script_name}", style_class='info')
            else: ui_manager_instance.append_output(f"No executable Python utility scripts found in '{UTILS_DIR_NAME}'.", style_class='info')
            logger.info(f"Listed utils scripts: {available_scripts}")
        except Exception as e: ui_manager_instance.append_output(f"❌ Error listing utility scripts: {e}", style_class='error'); logger.error(f"Error listing utility scripts: {e}", exc_info=True)
        finally:
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

    script_filename = f"{subcommand_or_script_name}.py"; script_path = os.path.join(UTILS_DIR_PATH, script_filename)
    if not os.path.isfile(script_path):
        ui_manager_instance.append_output(f"❌ Utility script not found: {script_filename} in '{UTILS_DIR_NAME}' directory.", style_class='error'); logger.warning(f"Utility script not found: {script_path}")
        ui_manager_instance.append_output(utils_help_message, style_class='info')
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

    command_to_execute_list = [sys.executable, script_path] + args; command_str_for_display = f"{sys.executable} {script_path} {' '.join(args)}"
    ui_manager_instance.append_output(f"🚀 Executing utility: {command_str_for_display}\n    (Working directory: {SCRIPT_DIR})", style_class='info'); logger.info(f"Executing utility script: {command_to_execute_list} with cwd={SCRIPT_DIR}")
    if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()
    try:
        process = await asyncio.to_thread(subprocess.run, command_to_execute_list, capture_output=True, text=True, cwd=SCRIPT_DIR, check=False, errors='replace')
        output_prefix = f"Output from '{script_filename}':\n"; has_output = False
        if process.stdout: ui_manager_instance.append_output(f"{output_prefix}{process.stdout.strip()}"); has_output = True
        if process.stderr: ui_manager_instance.append_output(f"Stderr from '{script_filename}':\n{process.stderr.strip()}", style_class='warning'); has_output = True
        if not has_output and process.returncode == 0: ui_manager_instance.append_output(f"{output_prefix}(No output)", style_class='info')

        if process.returncode != 0:
            ui_manager_instance.append_output(f"⚠️ Utility '{script_filename}' exited with code {process.returncode}.", style_class='warning')
            logger.warning(f"Utility script '{script_path}' exited with code {process.returncode}. Args: {args}")
        else:
            if not process.stderr: ui_manager_instance.append_output(f"✅ Utility '{script_filename}' completed.", style_class='success')
            logger.info(f"Utility script '{script_path}' completed with code {process.returncode}. Args: {args}")
    except FileNotFoundError: ui_manager_instance.append_output(f"❌ Error: Python interpreter ('{sys.executable}') or script ('{script_filename}') not found.", style_class='error'); logger.error(f"FileNotFoundError executing utility: {command_to_execute_list}", exc_info=True)
    except Exception as e: ui_manager_instance.append_output(f"❌ Unexpected error executing utility '{script_filename}': {e}", style_class='error'); logger.error(f"Error executing utility script '{script_path}': {e}", exc_info=True)
    finally:
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

def display_general_help():
    # This function is UI related, could stay or move to UIManager if it becomes more complex.
    # For now, keep in main.py.
    global ui_manager_instance
    if not ui_manager_instance: logger.error("display_general_help: UIManager not initialized."); return
    help_text_styled = [
        ('class:help-title', "micro_X AI-Enhanced Shell - Help\n\n"),
        ('class:help-text', "Welcome to micro_X! An intelligent shell that blends traditional command execution with AI capabilities.\n"),
        ('class:help-header', "\nAvailable Commands:\n"),
        ('class:help-command', "  /ai <query>           "), ('class:help-description', "- Translate natural language <query> into a Linux command.\n"),
        ('class:help-example', "                          Example: /ai list all text files in current folder\n"),
        ('class:help-command', "  /command <subcommand>   "), ('class:help-description', "- Manage command categorizations (simple, semi_interactive, interactive_tui).\n"),
        ('class:help-example', "                          Type '/command help' for detailed options.\n"),
        ('class:help-command', "  /ollama <subcommand>    "), ('class:help-description', "- Manage the Ollama service (start, stop, restart, status).\n"),
        ('class:help-example', "                          Type '/ollama help' for detailed options.\n"),
        ('class:help-command', "  /utils <script> [args]  "), ('class:help-description', "- Run a utility script from the 'utils' directory.\n"),
        ('class:help-example', "                          Type '/utils list' or '/utils help' for available scripts.\n"),
        ('class:help-command', "  /update               "), ('class:help-description', "- Check for and download updates for micro_X from its repository.\n"),
        ('class:help-command', "  /help                 "), ('class:help-description', "- Display this help message.\n"),
        ('class:help-command', "  exit | quit           "), ('class:help-description', "- Exit the micro_X shell.\n"),
        ('class:help-header', "\nDirect Commands:\n"),
        ('class:help-text', "  You can type standard Linux commands directly (e.g., 'ls -l', 'cd my_folder').\n"),
        ('class:help-text', "  Unknown commands will trigger an interactive categorization flow.\n"),
        ('class:help-text', "  AI-generated commands will prompt for confirmation (with categorization options) before execution.\n"),
        ('class:help-header', "\nKeybindings:\n"),
        ('class:help-text', "  Common keybindings are displayed at the bottom of the screen.\n"),
        ('class:help-text', "  Ctrl+C / Ctrl+D: Exit micro_X or cancel current categorization/confirmation/edit.\n"), # Updated help
        ('class:help-text', "  Ctrl+N: Insert a newline in the input field.\n"),
        ('class:help-header', "\nConfiguration:\n"),
        ('class:help-text', "  AI models and some behaviors can be customized in 'config/user_config.json'.\n"),
        ('class:help-text', "  Command categorizations are saved in 'config/user_command_categories.json'.\n"),
        ('class:help-text', "\nHappy shelling!\n")
    ]
    help_output_string = "".join([text for _, text in help_text_styled])
    ui_manager_instance.append_output(help_output_string, style_class='help-base')
    logger.info("Displayed general help.")

def display_ollama_help():
    # Similar to display_general_help, keep in main.py for now.
    global ui_manager_instance
    if not ui_manager_instance: logger.error("display_ollama_help: UIManager not initialized."); return
    help_text = [
        ("class:help-title", "Ollama Service Management - Help\n"),
        ("class:help-text", "Use these commands to manage the Ollama service used by micro_X.\n"),
        ("class:help-header", "\nAvailable /ollama Subcommands:\n"),
        ("class:help-command", "  /ollama start           "), ("class:help-description", "- Attempts to start the managed Ollama service if not already running.\n"),
        ("class:help-command", "  /ollama stop            "), ("class:help-description", "- Attempts to stop the managed Ollama service.\n"),
        ("class:help-command", "  /ollama restart         "), ("class:help-description", "- Attempts to restart the managed Ollama service.\n"),
        ("class:help-command", "  /ollama status          "), ("class:help-description", "- Shows the current status of the Ollama service and managed session.\n"),
        ("class:help-command", "  /ollama help            "), ("class:help-description", "- Displays this help message.\n"),
        ("class:help-text", "\nNote: These commands primarily interact with an Ollama instance managed by micro_X in a tmux session. ")
    ]
    help_output_string = "".join([text for _, text in help_text])
    ui_manager_instance.append_output(help_output_string, style_class='help-base')
    logger.info("Displayed Ollama command help.")

async def handle_ollama_command_async(user_input_parts: list):
    # This function is a built-in command handler, could potentially move to ShellEngine
    # or be called by ShellEngine. For now, keep in main.py.
    global ui_manager_instance, ollama_service_ready # Needs UIManager and affects ollama_service_ready
    if not ui_manager_instance: logger.error("handle_ollama_command_async: UIManager not initialized."); return
    append_output_func = ui_manager_instance.append_output
    logger.info(f"Handling /ollama command: {user_input_parts}")

    if len(user_input_parts) < 2: display_ollama_help(); return
    subcommand = user_input_parts[1].lower()

    if subcommand == "start":
        append_output_func("⚙️ Attempting to start Ollama service...", style_class='info')
        # ensure_ollama_service and explicit_start_ollama_service are from ollama_manager
        success = await explicit_start_ollama_service(config, append_output_func)
        if success:
            append_output_func("✅ Ollama service start process initiated. Check status shortly.", style_class='success')
            ollama_service_ready = await ensure_ollama_service(config, append_output_func)
        else: append_output_func("❌ Ollama service start process failed.", style_class='error'); ollama_service_ready = False
    elif subcommand == "stop":
        append_output_func("⚙️ Attempting to stop Ollama service...", style_class='info')
        success = await explicit_stop_ollama_service(config, append_output_func)
        if success: append_output_func("✅ Ollama service stop process initiated.", style_class='success')
        else: append_output_func("❌ Ollama service stop process failed.", style_class='error')
        ollama_service_ready = False
    elif subcommand == "restart":
        append_output_func("⚙️ Attempting to restart Ollama service...", style_class='info')
        success = await explicit_restart_ollama_service(config, append_output_func)
        if success:
            append_output_func("✅ Ollama service restart process initiated. Check status shortly.", style_class='success')
            ollama_service_ready = await ensure_ollama_service(config, append_output_func)
        else: append_output_func("❌ Ollama service restart process failed.", style_class='error'); ollama_service_ready = False
    elif subcommand == "status": await get_ollama_status_info(config, append_output_func)
    elif subcommand == "help": display_ollama_help()
    else: append_output_func(f"❌ Unknown /ollama subcommand: '{subcommand}'.", style_class='error'); logger.warning(f"Unknown /ollama subcommand: {subcommand}")


# This is the main input processing logic. This will be significantly refactored
# into ShellEngine.submit_input and ShellEngine.process_command_internal
async def handle_input_async(user_input: str):
    global ui_manager_instance, shell_engine_instance, ollama_service_ready
    if not ui_manager_instance:
        logger.error("handle_input_async: UIManager not initialized.")
        return
    append_output_func = ui_manager_instance.append_output

    if ui_manager_instance.categorization_flow_active or \
       ui_manager_instance.confirmation_flow_active or \
       ui_manager_instance.is_in_edit_mode:
        logger.warning("Input ignored: a UI flow or edit mode is active in UIManager.")
        return

    user_input_stripped = user_input.strip()
    logger.info(f"Received input: '{user_input_stripped}'")
    if not user_input_stripped:
        return

    current_app_inst = ui_manager_instance.get_app_instance()

    # --- Built-in command routing ---
    # This section will largely move to ShellEngine.submit_input
    if user_input_stripped.lower() in {"/help", "help"}:
        display_general_help()
        return
    if user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
        append_output_func("Exiting micro_X Shell 🚪", style_class='info')
        logger.info("Exit command received.")
        if current_app_inst and current_app_inst.is_running:
            if ui_manager_instance.main_exit_app_ref:
                ui_manager_instance.main_exit_app_ref()
            else:
                current_app_inst.exit()
        return
    if user_input_stripped.lower() == "/update":
        await handle_update_command()
        return
    if user_input_stripped.startswith("/utils"):
        await handle_utils_command_async(user_input_stripped)
        return
    if user_input_stripped.startswith("/ollama"):
        try:
            parts = user_input_stripped.split()
            await handle_ollama_command_async(parts)
        except Exception as e:
            append_output_func(f"❌ Error processing /ollama command: {e}", style_class='error')
            logger.error(f"Error in /ollama command '{user_input_stripped}': {e}", exc_info=True)
        return

    # `cd` command handling will move to ShellEngine
    if user_input_stripped == "cd" or user_input_stripped.startswith("cd "):
        logger.info(f"Handling 'cd' command directly: {user_input_stripped}")
        # This will become: await shell_engine_instance.handle_cd_command(user_input_stripped)
        await shell_engine_instance.handle_cd_command(user_input_stripped) # Call the new method in ShellEngine
        # restore_normal_input_handler() is called by ShellEngine.handle_cd_command
        return

    # AI query handling will move to ShellEngine
    if user_input_stripped.startswith("/ai "):
        if not ollama_service_ready:
            append_output_func("⚠️ Ollama service is not available.", style_class='warning')
            append_output_func("    Try '/ollama status' or '/ollama start'.", style_class='info')
            logger.warning("Attempted /ai command while Ollama service is not ready.")
            return
        human_query = user_input_stripped[len("/ai "):].strip()
        if not human_query:
            append_output_func("⚠️ AI query empty.", style_class='warning')
            return

        append_output_func(f"🤖 AI Query: {human_query}", style_class='ai-query')
        append_output_func(f"🧠 Thinking...", style_class='ai-thinking')
        if current_app_inst and current_app_inst.is_running:
            current_app_inst.invalidate()

        app_getter = ui_manager_instance.get_app_instance
        # This call to process_command will be internal to ShellEngine
        linux_command, ai_raw_candidate = await get_validated_ai_command(human_query, config, append_output_func, app_getter)
        if linux_command:
            append_output_func(f"🤖 AI Suggests (validated): {linux_command}", style_class='ai-response')
            # This call to process_command will be internal to ShellEngine
            await process_command(linux_command, f"/ai {human_query} -> {linux_command}", ai_raw_candidate, None, is_ai_generated=True)
        else:
            append_output_func("🤔 AI could not produce a validated command.", style_class='warning')
        return

    # /command subsystem handling
    if user_input_stripped.startswith("/command"):
        # handle_command_subsystem_input might be called from ShellEngine
        command_action = handle_command_subsystem_input(user_input_stripped)
        if isinstance(command_action, dict) and command_action.get('action') == 'force_run':
            cmd_to_run = command_action['command']
            forced_cat = command_action['category']
            display_input = f"/command run {forced_cat} \"{cmd_to_run}\""
            append_output_func(f"⚡ Forcing execution of '{cmd_to_run}' as '{forced_cat}'...", style_class='info')
            # This call to process_command will be internal to ShellEngine
            await process_command(cmd_to_run, display_input, None, None, forced_category=forced_cat, is_ai_generated=False)
        return

    # --- Direct command processing ---
    # This entire block will be the core of ShellEngine.process_command_internal
    logger.debug(f"handle_input_async: Classifying direct command: '{user_input_stripped}'")
    category = classify_command(user_input_stripped) # This will be self.category_manager.classify_command
    logger.debug(f"handle_input_async: classify_command returned: '{category}' for command '{user_input_stripped}'")

    if category != UNKNOWN_CATEGORY_SENTINEL:
        logger.debug(f"Direct input '{user_input_stripped}' is known: '{category}'.")
        await process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
    else:
        logger.debug(f"Direct input '{user_input_stripped}' unknown. Validating with AI.")
        if not ollama_service_ready:
            append_output_func(f"⚠️ Ollama service not available for validation.", style_class='warning')
            append_output_func(f"    Attempting direct categorization or try '/ollama status' or '/ollama start'.", style_class='info')
            logger.warning(f"Ollama service not ready. Skipping AI validation for '{user_input_stripped}'.")
            await process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
            return

        append_output_func(f"🔎 Validating '{user_input_stripped}' with AI...", style_class='info')
        if current_app_inst and current_app_inst.is_running:
            current_app_inst.invalidate()
        # This will be self.ai_handler.is_valid_linux_command_according_to_ai
        is_cmd_ai_says = await is_valid_linux_command_according_to_ai(user_input_stripped, config)

        # Heuristic logic for phrase vs command
        has_space = ' ' in user_input_stripped
        is_path_indicator = user_input_stripped.startswith(('/', './', '../'))
        has_double_hyphen = '--' in user_input_stripped
        has_single_hyphen_option = bool(re.search(r'(?:^|\s)-\w', user_input_stripped))
        is_problematic_leading_dollar = False
        if user_input_stripped.startswith('$'):
            if len(user_input_stripped) == 1: is_problematic_leading_dollar = True
            elif len(user_input_stripped) > 1 and user_input_stripped[1].isalnum() and user_input_stripped[1] != '{':
                is_problematic_leading_dollar = True

        is_command_syntax_present = is_path_indicator or has_double_hyphen or has_single_hyphen_option or \
                                    ('$' in user_input_stripped and not is_problematic_leading_dollar)
        user_input_looks_like_phrase = False
        if is_problematic_leading_dollar:
            user_input_looks_like_phrase = True
        elif not has_space:
            user_input_looks_like_phrase = False
        elif is_command_syntax_present:
            user_input_looks_like_phrase = False
        else:
            user_input_looks_like_phrase = True

        logger.debug(f"Input: '{user_input_stripped}', Validator AI: {is_cmd_ai_says}, Heuristic phrase: {user_input_looks_like_phrase}")

        if is_cmd_ai_says is True and not user_input_looks_like_phrase:
            append_output_func(f"✅ AI believes '{user_input_stripped}' is direct command. Categorizing.", style_class='success')
            logger.info(f"Validator AI confirmed '{user_input_stripped}' as command (not phrase).")
            await process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
        else:
            log_msg = ""
            ui_msg = ""
            ui_style = 'ai-thinking'
            if is_cmd_ai_says is False:
                log_msg = f"Validator AI suggests '{user_input_stripped}' not command."
                ui_msg = f"💬 AI suggests '{user_input_stripped}' not direct command. Trying as NL query..."
            elif is_cmd_ai_says is True and user_input_looks_like_phrase:
                log_msg = f"Validator AI confirmed '{user_input_stripped}' as command, but heuristic overrides."
                ui_msg = f"💬 AI validated '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."
            else: # is_cmd_ai_says is None (inconclusive)
                log_msg = f"Validator AI for '{user_input_stripped}' inconclusive."
                ui_msg = f"⚠️ AI validation for '{user_input_stripped}' inconclusive. Trying as NL query..."
                ui_style = 'warning'

            logger.info(f"{log_msg} Treating as natural language.")
            append_output_func(ui_msg, style_class=ui_style)
            if current_app_inst and current_app_inst.is_running:
                current_app_inst.invalidate()

            if not ollama_service_ready:
                append_output_func("⚠️ Ollama service not available for translation.", style_class='warning')
                append_output_func("    Try '/ollama status' or '/ollama start'.", style_class='info')
                logger.warning("Ollama service not ready. Skipping NL translation.")
                await process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
                return

            app_getter = ui_manager_instance.get_app_instance
            # This will be self.ai_handler.get_validated_ai_command
            linux_command, ai_raw_candidate = await get_validated_ai_command(user_input_stripped, config, append_output_func, app_getter)
            if linux_command:
                append_output_func(f"🤖 AI Translated & Validated to: {linux_command}", style_class='ai-response')
                original_direct_for_prompt = user_input_stripped if linux_command != user_input_stripped else None
                await process_command(linux_command, f"'{user_input_stripped}' -> {linux_command}", ai_raw_candidate, original_direct_for_prompt, is_ai_generated=True)
            else:
                append_output_func(f"🤔 AI could not produce validated command for '{user_input_stripped}'. Trying original as direct command.", style_class='warning')
                logger.info(f"Validated AI translation failed for '{user_input_stripped}'.")
                await process_command(user_input_stripped, user_input_stripped, ai_raw_candidate, None, is_ai_generated=False)


# This function is the core command processing pipeline.
# It will be moved to ShellEngine as a primary method.
async def process_command(command_str_original: str, original_user_input_for_display: str,
                            ai_raw_candidate: str | None = None,
                            original_direct_input_if_different: str | None = None,
                            forced_category: str | None = None,
                            is_ai_generated: bool = False):
    global ui_manager_instance, shell_engine_instance
    if not ui_manager_instance:
        logger.error("process_command: UIManager not initialized.")
        return
    if not shell_engine_instance: # Added check for shell_engine_instance
        logger.error("process_command: ShellEngine not initialized.")
        return

    append_output_func = ui_manager_instance.append_output
    confirmation_result = None

    # AI Command Confirmation Flow (handled by UIManager)
    if is_ai_generated and not forced_category:
        logger.info(f"AI generated command '{command_str_original}'. Initiating confirmation flow via UIManager.")
        confirmation_result = await ui_manager_instance.prompt_for_command_confirmation(
            command_str_original,
            original_user_input_for_display,
            normal_input_accept_handler # Pass the main normal handler
        )

        action = confirmation_result.get('action')
        confirmed_command = confirmation_result.get('command', command_str_original)
        chosen_category_from_confirmation = confirmation_result.get('category')

        if action == 'edit_mode_engaged':
            append_output_func("⌨️ Command loaded into input field for editing. Press Enter to submit.", style_class='info')
            # UIManager handles setting edit mode. main.py's restore_normal_input_handler will be called by UIManager
            # or the next input cycle if edit is cancelled.
            return

        if action == 'execute_and_categorize' and chosen_category_from_confirmation:
            append_output_func(f"✅ User confirmed execution of: {confirmed_command} (as {chosen_category_from_confirmation})", style_class='success')
            command_str_original = confirmed_command
            logger.info(f"User chose to run '{command_str_original}' and categorize as '{chosen_category_from_confirmation}'.")
            cm_add_command_to_category(command_str_original, chosen_category_from_confirmation) # This will be self.category_manager.add_command_to_category
            forced_category = chosen_category_from_confirmation
        elif action == 'execute':
            append_output_func(f"✅ User confirmed execution of: {confirmed_command}", style_class='success')
            command_str_original = confirmed_command
        elif action == 'cancel':
            append_output_func(f"❌ Execution of '{command_str_original}' cancelled.", style_class='info')
            logger.info(f"User cancelled execution of AI command: {command_str_original}")
            restore_normal_input_handler() # Restore normal input as flow is over
            return
        else: # Includes None if future was cancelled or unexpected action
            if action is not None : # Only log error if action was something unexpected, not just None from cancellation
                append_output_func(f"Internal error or unexpected action in confirmation flow ({action}). Aborting.", style_class='error')
                logger.error(f"Internal error in confirmation flow. Action: {action}")
            restore_normal_input_handler() # Restore normal input
            return

    category = forced_category
    command_for_classification = command_str_original
    command_to_be_added_if_new = command_for_classification

    # Command Categorization Flow (if not forced and unknown)
    if not category:
        logger.debug(f"process_command: Classifying command_for_classification: '{command_for_classification}' (is_ai_generated: {is_ai_generated})")
        category = classify_command(command_for_classification) # This will be self.category_manager.classify_command
        logger.debug(f"process_command: classify_command returned: '{category}' for command '{command_for_classification}'")

        if category == UNKNOWN_CATEGORY_SENTINEL:
            logger.info(f"Command '{command_for_classification}' uncategorized. Starting interactive flow via UIManager.")
            # prompt_for_categorization is now part of UIManager
            categorization_result = await ui_manager_instance.start_categorization_flow(
                command_for_classification,
                ai_raw_candidate,
                original_direct_input_if_different
            )

            action_cat = categorization_result.get('action')
            if action_cat == 'cancel_execution':
                append_output_func(f"Execution of '{command_for_classification}' cancelled.", style_class='info')
                logger.info(f"Execution of '{command_for_classification}' cancelled by user during categorization.")
                # UIManager's start_categorization_flow should handle restoring normal input on cancel
                return
            elif action_cat == 'categorize_and_execute':
                command_to_be_added_if_new = categorization_result['command']
                chosen_cat_for_json = categorization_result['category']
                cm_add_command_to_category(command_to_be_added_if_new, chosen_cat_for_json) # This will be self.category_manager.add_command_to_category
                category = chosen_cat_for_json
                logger.info(f"Command '{command_to_be_added_if_new}' categorized as '{category}'.")
                if command_to_be_added_if_new != command_str_original:
                    logger.info(f"Using '{command_to_be_added_if_new}' for execution.")
                    command_str_original = command_to_be_added_if_new
            else: # Includes 'execute_as_default' or other outcomes
                category = config['behavior']['default_category_for_unclassified']
                append_output_func(f"Executing '{command_for_classification}' as default '{category}'.", style_class='info')
                logger.info(f"Command '{command_for_classification}' executed with default category '{category}'.")

    # Expand, Sanitize, and Execute
    # These calls will use shell_engine_instance methods
    command_to_execute_expanded = shell_engine_instance.expand_shell_variables(command_str_original)
    if command_str_original != command_to_execute_expanded:
        logger.info(f"Expanded command: '{command_to_execute_expanded}' (original: '{command_str_original}')")
        if command_to_execute_expanded != command_for_classification and command_to_execute_expanded != command_to_be_added_if_new:
            append_output_func(f"Expanded for execution: {command_to_execute_expanded}", style_class='info')

    # sanitize_and_validate will be shell_engine_instance.sanitize_and_validate
    command_to_execute_sanitized = shell_engine_instance.sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
    if not command_to_execute_sanitized:
        append_output_func(f"Command '{command_to_execute_expanded}' blocked.", style_class='security-warning') # Style corrected
        logger.warning(f"Command '{command_to_execute_expanded}' blocked.")
        restore_normal_input_handler()
        return

    logger.info(f"Final command: '{command_to_execute_sanitized}', Category: '{category}'")
    exec_message_prefix = "Executing"
    if forced_category:
        if confirmation_result and confirmation_result.get('action') == 'execute_and_categorize':
            exec_message_prefix = f"Executing (user categorized as {category})"
        else:
            exec_message_prefix = "Forced execution"

    append_output_func(f"▶️ {exec_message_prefix} ({category} - {CM_CATEGORY_DESCRIPTIONS.get(category, 'Unknown')}): {command_to_execute_sanitized}", style_class='executing')

    # execute_shell_command and execute_command_in_tmux will be shell_engine_instance methods
    if category == "simple":
        await shell_engine_instance.execute_shell_command(command_to_execute_sanitized, original_user_input_for_display) # Call new method
    else:
        await shell_engine_instance.execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category) # Call new method

    # Restore normal input if no other flow is active (UIManager might handle this more centrally later)
    if ui_manager_instance and not ui_manager_instance.categorization_flow_active and not ui_manager_instance.confirmation_flow_active and not ui_manager_instance.is_in_edit_mode:
        restore_normal_input_handler()


async def main_async_runner():
    global app_instance, ollama_service_ready, ui_manager_instance, shell_engine_instance

    ui_manager_instance = UIManager(config)
    ui_manager_instance.main_exit_app_ref = _exit_app_main
    ui_manager_instance.main_restore_normal_input_ref = restore_normal_input_handler

    # Initialize ShellEngine - it needs config and ui_manager.
    # It might also need references to category_manager and ai_handler modules/functions.
    # For now, passing None, will be refined in later phases.
    # The category_manager and ai_handler modules are globally imported for now.
    shell_engine_instance = ShellEngine(config, ui_manager_instance,
                                        category_manager_module=sys.modules['modules.category_manager'], # Pass module
                                        ai_handler_module=sys.modules['modules.ai_handler']) # Pass module


    init_category_manager(SCRIPT_DIR, CONFIG_DIR, ui_manager_instance.append_output)
    ollama_service_ready = await ensure_ollama_service(config, ui_manager_instance.append_output)

    if not ollama_service_ready:
        ui_manager_instance.append_output("⚠️ Ollama service is not available or failed to start. AI-dependent features will be affected.", style_class='error')
        ui_manager_instance.append_output("    You can try '/ollama help' for manual control options.", style_class='info')
        logger.warning("Ollama service check failed or service could not be started.")
    else:
        ui_manager_instance.append_output("✅ Ollama service is active and ready.", style_class='success')
        logger.info("Ollama service is active.")

    history = FileHistory(HISTORY_FILE_PATH)
    home_dir = os.path.expanduser("~")
    max_prompt_len = config.get('ui', {}).get('max_prompt_length', 20)

    # Prompt directory calculation now uses shell_engine_instance.current_directory
    current_dir_for_prompt = shell_engine_instance.current_directory
    if current_dir_for_prompt == home_dir: initial_prompt_dir = "~"
    elif current_dir_for_prompt.startswith(home_dir + os.sep):
        rel_path = current_dir_for_prompt[len(home_dir)+1:]; full_rel_prompt = "~/" + rel_path
        initial_prompt_dir = full_rel_prompt if len(full_rel_prompt) <= max_prompt_len else "~/" + "..." + rel_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
    else:
        base_name = os.path.basename(current_dir_for_prompt)
        initial_prompt_dir = base_name if len(base_name) <= max_prompt_len else "..." + base_name[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."

    initial_welcome_message = (
        "Welcome to micro_X Shell 🚀\n"
        "Type a Linux command, or try '/ai your query' (e.g., /ai list text files).\n"
        "Key shortcuts are shown below. For more help, type '/help'.\n"
        "Use '/command help' for category options, '/utils help' for utilities, or '/update' to get new code.\n"
        "Use '/ollama help' to manage the Ollama service.\n"
    )

    initial_buffer_for_ui = list(ui_manager_instance.output_buffer)
    is_buffer_empty_or_just_welcome = not initial_buffer_for_ui or \
                                      (len(initial_buffer_for_ui) == 1 and initial_buffer_for_ui[0][1] == initial_welcome_message)

    if is_buffer_empty_or_just_welcome and not any(item[1] == initial_welcome_message for item in initial_buffer_for_ui):
        initial_buffer_for_ui.insert(0, ('class:welcome', initial_welcome_message))
    elif not any(item[1] == initial_welcome_message for item in initial_buffer_for_ui):
        initial_buffer_for_ui.append(('class:welcome', initial_welcome_message))

    layout_from_ui_manager = ui_manager_instance.initialize_ui_elements(
        initial_prompt_text=f"({initial_prompt_dir}) > ",
        history=history,
        output_buffer_main=initial_buffer_for_ui
    )

    if ui_manager_instance and ui_manager_instance.input_field:
        # normal_input_accept_handler now uses shell_engine_instance.submit_input
        ui_manager_instance.input_field.buffer.accept_handler = normal_input_accept_handler
    else:
        logger.critical("UIManager did not create input_field. Cannot set accept_handler.")
        return

    app_instance = Application(
        layout=layout_from_ui_manager,
        key_bindings=ui_manager_instance.get_key_bindings(),
        style=ui_manager_instance.style,
        full_screen=True,
        mouse_support=True
    )
    if ui_manager_instance:
        ui_manager_instance.app = app_instance


    logger.info("micro_X Shell application starting.")
    await app_instance.run_async()

def run_shell():
    try:
        asyncio.run(main_async_runner())
    except (EOFError, KeyboardInterrupt):
        print("\nExiting micro_X Shell. 👋"); logger.info("Exiting due to EOF or KeyboardInterrupt at run_shell level.")
    except Exception as e:
        print(f"\nUnexpected critical error: {e}"); logger.critical("Critical error in run_shell or main_async_runner", exc_info=True)
    finally:
        logger.info("micro_X Shell application stopped.")

if __name__ == "__main__":
    run_shell()
