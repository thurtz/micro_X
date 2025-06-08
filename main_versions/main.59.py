#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.history import FileHistory

import asyncio
import subprocess
import uuid
import shlex
import os
import re
import logging
import json
import shutil
import hashlib
import sys
import datetime # Added for log timestamps
from typing import Tuple, Optional

from modules.git_context_manager import GitContextManager
from modules.shell_engine import ShellEngine
import modules.category_manager
import modules.ai_handler
import modules.ollama_manager
from modules.category_manager import (
    init_category_manager,
    CATEGORY_MAP as CM_CATEGORY_MAP, CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS
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

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)
logger = logging.getLogger(__name__)

config = {}
DEFAULT_CONFIG_FILENAME = "default_config.json"
USER_CONFIG_FILENAME = "user_config.json"

app_instance = None
ui_manager_instance = None
shell_engine_instance = None
git_context_manager_instance = None

def merge_configs(base, override):
    """ Helper function to recursively merge dictionaries. """
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_configuration():
    """ Loads configurations from default and user JSON files, merging them. """
    global config
    default_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, USER_CONFIG_FILENAME)
    
    # Define a comprehensive fallback configuration
    fallback_config = {
        "ai_models": {"primary_translator": "llama3.2:3b", "direct_translator": "vitali87/shell-commands-qwen2-1.5b", "validator": "herawen/lisa:latest", "explainer": "llama3.2:3b"},
        "timeouts": {"tmux_poll_seconds": 300, "tmux_semi_interactive_sleep_seconds": 1, "git_fetch_timeout": 10},
        "behavior": {"input_field_height": 3, "default_category_for_unclassified": "simple", "validator_ai_attempts": 3, "translation_validation_cycles": 3, "ai_retry_delay_seconds": 1, "ollama_api_call_retries": 2, "tui_detection_line_threshold_pct": 30.0, "tui_detection_char_threshold_pct": 3.0, "use_strict_extraction_for_primary_translator": True},
        "ui": {
            "max_prompt_length": 20,
            "enable_output_separator": True,
            "output_separator_character": "─",
            "output_separator_length": 30,
            "enable_startup_separator": True,
            "startup_separator_string": "🚀 micro_X Initialized & Ready 🚀\n──────────────────────────────\n",
            "enable_mouse_support": False # Fallback default for mouse support
        },
        "paths": {"tmux_log_base_path": "/tmp"},
        "prompts": {
            "validator": {"system": "You are a Linux command validation assistant. Your task is to determine if a given string is likely a valid Linux command. If the string looks like a phrase rather than a linux command then the answer is no. If the string looks like a Linux command rather than a phrase then the answer is yes. Answer only with 'yes' or 'no'.", "user_template": "Is the following string likely a Linux command: '{command_text}'"},
            "primary_translator": {"system": "You are a helpful assistant that translates human language queries into a single, precise Linux command.\nStrictly enclose the Linux command within <bash></bash> tags.\nDo not add any other explanations, apologies, or text outside these tags.\nIf the request is ambiguous, unsafe, or cannot be translated into a single command, respond with only \"<unsafe>Cannot translate safely</unsafe>\" or a similar message within <unsafe> tags.", "user_template": "Translate to a single Linux command: \"{human_input}\"."},
            "direct_translator": {"system": "Translate the following user request into a single Linux command. Output only the command. Do not include any other text, explanations, or markdown formatting.", "user_template": "Translate to a single Linux command: \"{human_input}\"."},
            "explainer": {"system": "You are a helpful assistant that explains Linux commands in simple, clear terms. Describe what the command does, its main arguments/options shown, and any significant side effects or risks. Be concise. If the command is trivial, a very short explanation is fine. If it seems dangerous or complex, highlight that.", "user_template": "Explain the following Linux command: '{command_text}'"}
        },
        "ollama_service": {"executable_path": None, "auto_start_serve": True, "startup_wait_seconds": 10, "server_check_retries": 5, "server_check_interval_seconds": 2},
        "integrity_check": {
            "protected_branches": ["main", "testing"],
            "developer_branch": "dev",
            "halt_on_integrity_failure": True,
            "allow_run_if_behind_remote": True
        }
    }
    config = fallback_config.copy() # Start with fallback
    logger.info("Initialized with hardcoded fallback general configurations.")

    # Load default config
    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f: default_settings = json.load(f)
            config = merge_configs(config, default_settings) # Merge fallback with default
            logger.info(f"Loaded general configurations from {default_config_path}")
        except Exception as e: logger.error(f"Error loading {default_config_path}: {e}.", exc_info=True)
    else:
        logger.warning(f"{default_config_path} not found. Creating it now with fallback values.")
        try:
            os.makedirs(os.path.dirname(default_config_path), exist_ok=True)
            with open(default_config_path, 'w') as f: json.dump(fallback_config, f, indent=2)
            logger.info(f"Created default general configuration file at {default_config_path} with fallback values.")
        except Exception as e: logger.error(f"Could not create default config file: {e}", exc_info=True)
    
    # Load user config and merge on top
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r') as f: user_settings = json.load(f)
            config = merge_configs(config, user_settings) # Merge current config with user settings
            logger.info(f"Loaded and merged general configurations from {user_config_path}")
        except Exception as e: logger.error(f"Error loading {user_config_path}: {e}.", exc_info=True)
    else: logger.info(f"{user_config_path} not found. No user general overrides applied.")

    # Ensure critical UI keys exist after merging, especially new ones like enable_mouse_support
    if "ui" not in config: config["ui"] = {}
    if "enable_mouse_support" not in config["ui"]:
        config["ui"]["enable_mouse_support"] = fallback_config["ui"]["enable_mouse_support"]
        logger.info(f"UI config 'enable_mouse_support' was missing, set to fallback default: {config['ui']['enable_mouse_support']}")


load_configuration() # Load config at startup

def normal_input_accept_handler(buff):
    """
    Handles normal user input submission from the prompt_toolkit input field.
    This is the default handler for the input field.
    It's also used when submitting an edited command after choosing 'Modify' in AI confirmation.
    """
    global shell_engine_instance, ui_manager_instance # These are globals
    user_input_stripped = buff.text.strip()
    logger.info(f"normal_input_accept_handler received: '{user_input_stripped}'")

    was_in_edit_mode = False
    if ui_manager_instance:
        was_in_edit_mode = ui_manager_instance.is_in_edit_mode
        if was_in_edit_mode:
            logger.info("Input submission is from edit mode context.")

    async def _handle_input():
        try:
            if not await shell_engine_instance.handle_built_in_command(user_input_stripped):
                await shell_engine_instance.submit_user_input(user_input_stripped, from_edit_mode=was_in_edit_mode)
        finally:
            if was_in_edit_mode:
                logger.debug("Input was from edit mode; explicitly calling restore_normal_input_handler.")
                if ui_manager_instance:
                    logger.debug(f"Before calling restore_normal_input_handler, ui_manager.is_in_edit_mode was {ui_manager_instance.is_in_edit_mode}. Resetting to False.")
                    ui_manager_instance.is_in_edit_mode = False 
                
                if shell_engine_instance and shell_engine_instance.main_restore_normal_input_ref:
                    shell_engine_instance.main_restore_normal_input_ref()
                else:
                    logger.warning("Could not call restore_normal_input_handler after edit mode submission: ref missing.")

    asyncio.create_task(_handle_input())


def restore_normal_input_handler():
    """
    Restores the UI to normal input mode. This is typically called after
    a special flow (like categorization or confirmation) is completed or cancelled.
    It re-attaches the 'normal_input_accept_handler' to the input field.
    This function will also add an interaction separator if configured and appropriate.
    """
    global ui_manager_instance, shell_engine_instance
    logger.debug("restore_normal_input_handler called.")
    if ui_manager_instance and shell_engine_instance:
        if ui_manager_instance.initial_prompt_settled and \
           ui_manager_instance.config.get("ui", {}).get("enable_output_separator", True) and \
           not ui_manager_instance.categorization_flow_active and \
           not ui_manager_instance.confirmation_flow_active and \
           not ui_manager_instance.is_in_edit_mode: 
            logger.debug("Conditions met for adding interaction separator.")
            ui_manager_instance.add_interaction_separator()

        ui_manager_instance.set_normal_input_mode(normal_input_accept_handler, shell_engine_instance.current_directory)
    elif not ui_manager_instance:
        logger.warning("restore_normal_input_handler: ui_manager_instance is None.")
    elif not shell_engine_instance:
        logger.warning("restore_normal_input_handler: shell_engine_instance is None.")

def _exit_app_main():
    """ Handles application exit logic. """
    global app_instance
    logger.info("Exit requested by _exit_app_main.")
    if app_instance and app_instance.is_running:
        app_instance.exit()
    else:
        logger.warning("_exit_app_main called but app_instance not running or None. Attempting sys.exit.")
        sys.exit(0) # Exit gracefully if app not running

async def perform_startup_integrity_checks() -> Tuple[bool, bool]:
    """
    Performs Git integrity checks at startup.
    Returns: (is_developer_mode, integrity_ok)
    """
    global git_context_manager_instance, ui_manager_instance, config, SCRIPT_DIR
    is_developer_mode = False
    integrity_ok = True
    integrity_config = config.get("integrity_check", {})
    protected_branches = integrity_config.get("protected_branches", ["main", "testing"])
    developer_branch = integrity_config.get("developer_branch", "dev")
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)
    allow_run_if_behind = integrity_config.get("allow_run_if_behind_remote", True)

    git_fetch_timeout_from_config = config.get('timeouts', {}).get('git_fetch_timeout')

    if git_fetch_timeout_from_config is not None:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR, fetch_timeout=git_fetch_timeout_from_config)
    else:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR) # Uses default timeout

    if not await git_context_manager_instance.is_git_available():
        ui_manager_instance.append_output("⚠️ Git command not found. Integrity checks cannot be performed. Assuming developer mode.", style_class='error')
        logger.error("Git command not found. Integrity checks skipped. Defaulting to developer mode.")
        return True, True 

    if not await git_context_manager_instance.is_repository():
        ui_manager_instance.append_output(f"⚠️ Project directory '{SCRIPT_DIR}' is not a Git repository. Integrity checks cannot be performed. Assuming developer mode.", style_class='error')
        logger.error(f"Not a Git repository at '{SCRIPT_DIR}'. Integrity checks skipped. Defaulting to developer mode.")
        return True, True 

    current_branch = await git_context_manager_instance.get_current_branch()
    head_commit = await git_context_manager_instance.get_head_commit_hash()
    logger.info(f"Detected Git branch: {current_branch}, HEAD: {head_commit}")
    ui_manager_instance.append_output(f"ℹ️ Git context: Branch '{current_branch}', Commit '{head_commit[:7] if head_commit else 'N/A'}'", style_class='info')

    if current_branch == developer_branch:
        is_developer_mode = True
        ui_manager_instance.append_output(f"✅ Running in Developer Mode (branch: '{developer_branch}'). Integrity checks are informational.", style_class='success')
        logger.info(f"Developer mode enabled: '{developer_branch}' branch checked out.")
    elif current_branch in protected_branches:
        is_developer_mode = False
        ui_manager_instance.append_output(f"ℹ️ Running on protected branch '{current_branch}'. Performing integrity checks...", style_class='info')
        
        is_clean = await git_context_manager_instance.is_working_directory_clean()
        if not is_clean:
            status_output_tuple = await git_context_manager_instance._run_git_command(["status", "--porcelain"])
            status_output_details = status_output_tuple[1] if status_output_tuple[0] else "Could not get detailed status."
            error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): Uncommitted local changes or untracked files detected."
            detail_msg = f"   Git status details:\n{status_output_details}" 
            ui_manager_instance.append_output(error_msg, style_class='error')
            ui_manager_instance.append_output(detail_msg, style_class='error') 
            logger.critical(f"{error_msg}\n{detail_msg}")
            integrity_ok = False
        else:
            ui_manager_instance.append_output(f"✅ Working directory is clean for branch '{current_branch}'.", style_class='info')

        if integrity_ok: 
            comparison_status, local_h, remote_h, fetch_status = await git_context_manager_instance.compare_head_with_remote_tracking(current_branch)
            
            if fetch_status == "success":
                if comparison_status == "synced":
                    ui_manager_instance.append_output(f"✅ Branch '{current_branch}' is synced with 'origin/{current_branch}'.", style_class='success')
                    logger.info(f"Branch '{current_branch}' (Local: {local_h[:7] if local_h else 'N/A'}) is synced with remote (Remote: {remote_h[:7] if remote_h else 'N/A'}).")
                elif comparison_status == "behind" and allow_run_if_behind:
                    warn_msg = f"⚠️ Your local branch '{current_branch}' is behind 'origin/{current_branch}'. New updates are available."
                    suggest_msg = "   Suggestion: Run the '/update' command to get the latest version."
                    ui_manager_instance.append_output(warn_msg, style_class='warning')
                    ui_manager_instance.append_output(suggest_msg, style_class='info')
                    logger.warning(f"{warn_msg} Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}")
                elif comparison_status in ["ahead", "diverged"] or (comparison_status == "behind" and not allow_run_if_behind):
                    status_description = comparison_status
                    if comparison_status == "behind" and not allow_run_if_behind:
                        status_description = "behind (and configuration disallows running)"
                    error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): Local branch has '{status_description}' from 'origin/{current_branch}'."
                    detail_msg = f"   Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}"
                    ui_manager_instance.append_output(error_msg, style_class='error')
                    ui_manager_instance.append_output(detail_msg, style_class='error')
                    logger.critical(f"{error_msg} {detail_msg}")
                    integrity_ok = False
                else: 
                    error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): Cannot reliably compare with remote after successful fetch. Status: {comparison_status}."
                    detail_msg = f"   Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}"
                    ui_manager_instance.append_output(error_msg, style_class='error')
                    ui_manager_instance.append_output(detail_msg, style_class='error')
                    logger.critical(f"{error_msg} {detail_msg}")
                    integrity_ok = False
            elif fetch_status in ["timeout", "offline_or_unreachable"]:
                ui_manager_instance.append_output(f"⚠️ Could not contact remote for branch '{current_branch}' (Reason: {fetch_status}). Comparing against local cache.", style_class='warning')
                if comparison_status == "synced_local_cache" or comparison_status == "behind_local_cache": 
                    ui_manager_instance.append_output(f"ℹ️ Branch '{current_branch}' is consistent with the last known state of 'origin/{current_branch}'. Running in offline-verified mode.", style_class='info')
                elif comparison_status == "ahead_local_cache" or comparison_status == "diverged_local_cache":
                    error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}, Offline): Local branch has unpushed changes or diverged from the last known remote state. Status: {comparison_status}"
                    detail_msg = f"   Local: {local_h[:7] if local_h else 'N/A'}, Last Known Remote: {remote_h[:7] if remote_h else 'N/A'}"
                    ui_manager_instance.append_output(error_msg, style_class='error')
                    ui_manager_instance.append_output(detail_msg, style_class='error')
                    logger.critical(f"{error_msg} {detail_msg}")
                    integrity_ok = False
                elif comparison_status == "no_upstream_info_locally":
                    error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}, Offline): No local information about the remote tracking branch. Cannot verify integrity."
                    ui_manager_instance.append_output(error_msg, style_class='error')
                    logger.critical(error_msg)
                    integrity_ok = False
                else: 
                    error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}, Offline): Error comparing with local cache. Status: {comparison_status}"
                    ui_manager_instance.append_output(error_msg, style_class='error')
                    logger.critical(error_msg)
                    integrity_ok = False
            elif fetch_status == "other_error":
                error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): A non-network error occurred during 'git fetch'."
                ui_manager_instance.append_output(error_msg, style_class='error')
                logger.critical(f"{error_msg} - Check git fetch logs or permissions.")
                integrity_ok = False
        
        if integrity_ok:
            logger.info(f"Integrity checks completed for branch '{current_branch}'. Final status: OK")
        elif halt_on_failure:
            logger.critical(f"Application integrity compromised on protected branch '{current_branch}'. Halting as per configuration.")
    else: 
        is_developer_mode = True 
        ui_manager_instance.append_output(f"ℹ️ Running on unrecognized branch/commit '{current_branch}'. Developer mode assumed. Integrity checks informational.", style_class='info')
        logger.info(f"Developer mode assumed for unrecognized branch/commit: '{current_branch}'.")

    return is_developer_mode, integrity_ok


async def main_async_runner():
    """ Main asynchronous runner for the application. """
    global app_instance, ui_manager_instance, shell_engine_instance, git_context_manager_instance

    ui_manager_instance = UIManager(config)
    ui_manager_instance.main_exit_app_ref = _exit_app_main
    ui_manager_instance.main_restore_normal_input_ref = restore_normal_input_handler

    is_developer_mode, integrity_checks_passed = await perform_startup_integrity_checks()
    integrity_config = config.get("integrity_check", {})
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)

    if not is_developer_mode and not integrity_checks_passed and halt_on_failure:
        logger.critical("Halting micro_X due to failed integrity checks on a protected branch.")
        _exit_app_main() 
        return 

    shell_engine_instance = ShellEngine(config, ui_manager_instance,
                                        category_manager_module=sys.modules['modules.category_manager'],
                                        ai_handler_module=sys.modules['modules.ai_handler'],
                                        ollama_manager_module=sys.modules['modules.ollama_manager'],
                                        main_exit_app_ref=_exit_app_main,
                                        main_restore_normal_input_ref=restore_normal_input_handler,
                                        main_normal_input_accept_handler_ref=normal_input_accept_handler, 
                                        is_developer_mode=is_developer_mode,
                                        git_context_manager_instance=git_context_manager_instance
                                        )
    
    ollama_service_ready = await shell_engine_instance.ollama_manager_module.ensure_ollama_service(config, ui_manager_instance.append_output)
    if not ollama_service_ready:
        ui_manager_instance.append_output("⚠️ Ollama service is not available or failed to start. AI-dependent features will be affected.", style_class='error')
        ui_manager_instance.append_output("   You can try '/ollama help' for manual control options.", style_class='info')
        logger.warning("Ollama service check failed or service could not be started.")
    else:
        ui_manager_instance.append_output("✅ Ollama service is active and ready.", style_class='success')
        logger.info("Ollama service is active.")


    init_category_manager(SCRIPT_DIR, CONFIG_DIR, ui_manager_instance.append_output)
    
    history = FileHistory(HISTORY_FILE_PATH)
    
    home_dir = os.path.expanduser("~")
    max_prompt_len = config.get('ui', {}).get('max_prompt_length', 20)
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
        ui_manager_instance.input_field.buffer.accept_handler = normal_input_accept_handler
    else:
        logger.critical("UIManager did not create input_field. Cannot set accept_handler.")
        _exit_app_main()
        return

    if ui_manager_instance:
        ui_manager_instance.initial_prompt_settled = True 
        ui_manager_instance.last_output_was_separator = False 
        ui_manager_instance.add_startup_separator()

    # Read mouse support configuration
    enable_mouse = config.get("ui", {}).get("enable_mouse_support", False)
    logger.info(f"Prompt Toolkit Application mouse_support will be set to: {enable_mouse}")

    app_instance = Application(
        layout=layout_from_ui_manager,
        key_bindings=ui_manager_instance.get_key_bindings(),
        style=ui_manager_instance.style,
        full_screen=True,
        mouse_support=enable_mouse # Use configured value
    )
    if ui_manager_instance:
        ui_manager_instance.app = app_instance 

    logger.info("micro_X Shell application starting.")
    await app_instance.run_async()
    logger.info("micro_X Shell application run_async completed.")


def run_shell():
    """ Main entry point to run the shell application. """
    logger.info("=" * 80) 
    logger.info("  micro_X Session Started") 
    logger.info(f"  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80) 
    try:
        asyncio.run(main_async_runner())
    except (EOFError, KeyboardInterrupt):
        print("\nExiting micro_X Shell. 👋"); logger.info("Exiting due to EOF or KeyboardInterrupt at run_shell level.")
    except SystemExit as e:
        if e.code == 0: 
            print("\nExiting micro_X Shell. 👋"); logger.info("Exiting micro_X Shell normally via SystemExit(0).")
        else:
            print(f"\nExiting micro_X Shell due to an issue (Code: {e.code}). Check logs at {LOG_FILE}"); logger.warning(f"Exiting micro_X Shell with code {e.code}.")
    except Exception as e:
        print(f"\nUnexpected critical error: {e}"); logger.critical("Critical error in run_shell or main_async_runner", exc_info=True)
    finally:
        global git_context_manager_instance
        if git_context_manager_instance :
            loop = None
            try: loop = asyncio.get_running_loop()
            except RuntimeError: loop = None 

            if loop and loop.is_running():
                try:
                    final_branch_future = asyncio.run_coroutine_threadsafe(git_context_manager_instance.get_current_branch(), loop)
                    final_commit_future = asyncio.run_coroutine_threadsafe(git_context_manager_instance.get_head_commit_hash(), loop)
                    final_branch = final_branch_future.result(timeout=0.5) 
                    final_commit = final_commit_future.result(timeout=0.5)
                    logger.info(f"micro_X Shell final state: Branch='{final_branch}', Commit='{final_commit[:7] if final_commit else 'N/A'}'")
                except Exception as git_log_err:
                    logger.error(f"Error logging final git state during active loop: {git_log_err}")
            else: 
                logger.info(f"micro_X Shell final state (sync log attempt): Project Root='{git_context_manager_instance.project_root}' (Branch/commit info requires running loop for async calls)")

        logger.info("micro_X Shell application stopped.")
        logger.info("=" * 80) 
        logger.info("  micro_X Session Ended") 
        logger.info(f"  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80) 
        logging.shutdown() 

if __name__ == "__main__":
    run_shell()
# This is the main entry point for the micro_X shell application.