#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory

import asyncio
import subprocess
import uuid
import shlex
import os
import re
import logging
import json
import time
import shutil
import hashlib
import sys

# Import the new ShellEngine class
from modules.shell_engine import ShellEngine

# ai_handler, category_manager, ollama_manager are now primarily used via ShellEngine
# but their init or constants might still be needed here or by UIManager.
# Keep them imported for now, as UIManager still needs category_manager constants
# and ai_handler's explain function.
# Removed: get_validated_ai_command, is_valid_linux_command_according_to_ai (now accessed via shell_engine_instance.ai_handler_module)
from modules.category_manager import (
    init_category_manager, classify_command, # classify_command not directly used in main.py anymore
    add_command_to_category as cm_add_command_to_category, # not directly used in main.py anymore
    handle_command_subsystem_input, # not directly used in main.py anymore
    UNKNOWN_CATEGORY_SENTINEL, # not directly used in main.py anymore
    CATEGORY_MAP as CM_CATEGORY_MAP, CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS # Used by UIManager
)
# Removed: ensure_ollama_service, explicit_start_ollama_service, explicit_stop_ollama_service, explicit_restart_ollama_service, get_ollama_status_info (now accessed via shell_engine_instance.ollama_manager_module)
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

# --- Global instances (will be initialized in main_async_runner) ---
app_instance = None
ui_manager_instance = None
shell_engine_instance = None # New global for ShellEngine instance

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
    Delegates to ShellEngine for processing.
    """
    global shell_engine_instance
    user_input_stripped = buff.text.strip()
    if not user_input_stripped:
        return

    # First, try to handle as a built-in command
    # If not handled as built-in, pass to submit_user_input for full processing
    async def _handle_input():
        if not await shell_engine_instance.handle_built_in_command(user_input_stripped):
            await shell_engine_instance.submit_user_input(user_input_stripped)

    asyncio.create_task(_handle_input())


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

# Removed: get_file_hash (moved to ShellEngine's _handle_update_command)
# Removed: handle_update_command (moved to ShellEngine)
# Removed: handle_utils_command_async (moved to ShellEngine)
# Removed: display_general_help (moved to ShellEngine)
# Removed: display_ollama_help (moved to ShellEngine)
# Removed: handle_ollama_command_async (moved to ShellEngine)
# Removed: handle_input_async (replaced by ShellEngine.submit_user_input)
# Removed: process_command (moved to ShellEngine)


async def main_async_runner():
    global app_instance, ui_manager_instance, shell_engine_instance

    ui_manager_instance = UIManager(config)
    ui_manager_instance.main_exit_app_ref = _exit_app_main
    ui_manager_instance.main_restore_normal_input_ref = restore_normal_input_handler

    # Initialize ShellEngine - it needs config and ui_manager.
    # It also needs references to category_manager, ai_handler, and ollama_manager modules.
    shell_engine_instance = ShellEngine(config, ui_manager_instance,
                                        category_manager_module=sys.modules['modules.category_manager'], # Pass module
                                        ai_handler_module=sys.modules['modules.ai_handler'], # Pass module
                                        ollama_manager_module=sys.modules['modules.ollama_manager'], # Pass the ollama_manager module
                                        main_exit_app_ref=_exit_app_main, # Pass the exit callback
                                        main_restore_normal_input_ref=restore_normal_input_handler) # Pass the restore input callback


    # Check Ollama service readiness using the new ShellEngine's ollama_manager_module
    ollama_service_ready = await shell_engine_instance.ollama_manager_module.ensure_ollama_service(config, ui_manager_instance.append_output)

    if not ollama_service_ready:
        ui_manager_instance.append_output("⚠️ Ollama service is not available or failed to start. AI-dependent features will be affected.", style_class='error')
        ui_manager_instance.append_output("    You can try '/ollama help' for manual control options.", style_class='info')
        logger.warning("Ollama service check failed or service could not be started.")
    else:
        ui_manager_instance.append_output("✅ Ollama service is active and ready.", style_class='success')
        logger.info("Ollama service is active.")

    # Initialize category manager after shell_engine_instance is created,
    # as category_manager might need to interact with it indirectly.
    # (Though currently, it only needs SCRIPT_DIR and append_output).
    init_category_manager(SCRIPT_DIR, CONFIG_DIR, ui_manager_instance.append_output)


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
