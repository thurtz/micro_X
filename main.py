#!/usr/bin/env python

from prompt_toolkit import Application
# from prompt_toolkit.document import Document # No longer directly used in main.py
from prompt_toolkit.history import FileHistory

import asyncio
import subprocess
import uuid
import shlex # Keep for shlex.split if used by modules called from main
import os
import re
import logging
import json
# import time # No longer directly used in main.py
import shutil # Keep if used by modules called from main
import hashlib # Keep if used by modules called from main
import sys
from typing import Tuple

# --- New Import for GitContextManager ---
from modules.git_context_manager import GitContextManager # DEFAULT_GIT_FETCH_TIMEOUT is defined here

# Import the ShellEngine class
from modules.shell_engine import ShellEngine

# ai_handler, category_manager, ollama_manager are now primarily used via ShellEngine
# but their init or constants might still be needed here or by UIManager.
from modules.category_manager import (
    init_category_manager, # classify_command not directly used in main.py anymore
    # add_command_to_category as cm_add_command_to_category, # not directly used in main.py anymore
    # handle_command_subsystem_input, # not directly used in main.py anymore
    # UNKNOWN_CATEGORY_SENTINEL, # not directly used in main.py anymore
    CATEGORY_MAP as CM_CATEGORY_MAP, CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS # Used by UIManager
)
from modules.ui_manager import UIManager
# modules.ai_handler and modules.ollama_manager are primarily accessed via ShellEngine instance

LOG_DIR = "logs"
CONFIG_DIR = "config"
HISTORY_FILENAME = ".micro_x_history"
REQUIREMENTS_FILENAME = "requirements.txt" # Still used by ShellEngine's update command
UTILS_DIR_NAME = "utils" # Still used by ShellEngine's utils command

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # This is the Project Root
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True)
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME)
# REQUIREMENTS_FILE_PATH = os.path.join(SCRIPT_DIR, REQUIREMENTS_FILENAME) # Handled in ShellEngine
# UTILS_DIR_PATH = os.path.join(SCRIPT_DIR, UTILS_DIR_NAME) # Handled in ShellEngine
# os.makedirs(UTILS_DIR_PATH, exist_ok=True) # Handled in ShellEngine

logging.basicConfig(
    level=logging.DEBUG, # Keep DEBUG for development
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)
logger = logging.getLogger(__name__)

config = {}
DEFAULT_CONFIG_FILENAME = "default_config.json"
USER_CONFIG_FILENAME = "user_config.json"

# --- Global instances (will be initialized in main_async_runner) ---
app_instance = None # prompt_toolkit Application instance
ui_manager_instance = None
shell_engine_instance = None
git_context_manager_instance = None # New global for GitContextManager instance

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
    fallback_config = {
        "ai_models": {"primary_translator": "llama3.2:3b", "direct_translator": "vitali87/shell-commands-qwen2-1.5b", "validator": "herawen/lisa:latest", "explainer": "llama3.2:3b"},
        "timeouts": {"tmux_poll_seconds": 300, "tmux_semi_interactive_sleep_seconds": 1, "git_fetch_timeout": 10}, # Default git_fetch_timeout
        "behavior": {"input_field_height": 3, "default_category_for_unclassified": "simple", "validator_ai_attempts": 3, "translation_validation_cycles": 3, "ai_retry_delay_seconds": 1, "ollama_api_call_retries": 2},
        "ui": {"max_prompt_length": 20},
        "paths": {"tmux_log_base_path": "/tmp"},
        "prompts": {
            "validator": {"system": "You are a Linux command validation assistant...", "user_template": "Is the following string likely a Linux command: '{command_text}'"},
            "primary_translator": {"system": "You are a helpful assistant that translates human language queries...", "user_template": "Translate to a single Linux command: \"{human_input}\"."},
            "direct_translator": {"system": "Translate the following user request into a single Linux command...", "user_template": "Translate to a single Linux command: \"{human_input}\"."},
            "explainer": {"system": "You are a helpful assistant that explains Linux commands...", "user_template": "Explain the following Linux command: '{command_text}'"}
        },
        "ollama_service": {"executable_path": None, "auto_start_serve": True, "startup_wait_seconds": 10, "server_check_retries": 5, "server_check_interval_seconds": 2},
        "integrity_check": { # New section for integrity check configuration
            "protected_branches": ["main", "testing"],
            "developer_branch": "dev",
            "halt_on_integrity_failure": True # For protected branches
        }
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
    # No need to check for empty here, ShellEngine.submit_user_input handles it.

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
    """ Callback for UIManager or other modules to exit the main application. """
    global app_instance
    logger.info("Exit requested by _exit_app_main.")
    if app_instance and app_instance.is_running:
        app_instance.exit()
    else:
        logger.warning("_exit_app_main called but app_instance not running or None. Attempting sys.exit.")
        # Fallback if app isn't running but exit is critical (e.g., integrity check fail before app run)
        sys.exit(1) # Indicate error exit

async def perform_startup_integrity_checks() -> Tuple[bool, bool]:
    """
    Performs startup integrity checks based on Git context.

    Returns:
        Tuple[bool, bool]: (is_developer_mode, integrity_checks_passed_or_not_applicable)
                           If integrity_checks_passed is False, main app should halt if not in dev mode.
    """
    global git_context_manager_instance, ui_manager_instance, config
    
    is_developer_mode = False # Default to not developer mode
    integrity_ok = True       # Assume okay unless a check fails

    integrity_config = config.get("integrity_check", {})
    protected_branches = integrity_config.get("protected_branches", ["main", "testing"])
    developer_branch = integrity_config.get("developer_branch", "dev")
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)
    
    # Get git_fetch_timeout from config, if not present, GitContextManager will use its own default.
    git_fetch_timeout_from_config = config.get('timeouts', {}).get('git_fetch_timeout')

    if git_fetch_timeout_from_config is not None:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR, fetch_timeout=git_fetch_timeout_from_config)
    else:
        # If not in config, GitContextManager will use its internal DEFAULT_GIT_FETCH_TIMEOUT
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR)


    if not await git_context_manager_instance.is_git_available():
        ui_manager_instance.append_output(
            "⚠️ Git command not found. Integrity checks cannot be performed. Assuming developer mode.",
            style_class='error'
        )
        logger.error("Git command not found. Integrity checks skipped. Defaulting to developer mode.")
        return True, True # is_developer_mode = True, integrity_ok = True (as checks are skipped)

    if not await git_context_manager_instance.is_repository():
        ui_manager_instance.append_output(
            f"⚠️ Project directory '{SCRIPT_DIR}' is not a Git repository. Integrity checks cannot be performed. Assuming developer mode.",
            style_class='error'
        )
        logger.error(f"Not a Git repository at '{SCRIPT_DIR}'. Integrity checks skipped. Defaulting to developer mode.")
        return True, True # is_developer_mode = True, integrity_ok = True

    current_branch = await git_context_manager_instance.get_current_branch()
    head_commit = await git_context_manager_instance.get_head_commit_hash()
    logger.info(f"Detected Git branch: {current_branch}, HEAD: {head_commit}")
    ui_manager_instance.append_output(f"ℹ️ Git context: Branch '{current_branch}', Commit '{head_commit[:7] if head_commit else 'N/A'}'", style_class='info')


    if current_branch == developer_branch:
        is_developer_mode = True
        ui_manager_instance.append_output(f"✅ Running in Developer Mode (branch: '{developer_branch}'). Integrity checks are informational.", style_class='success')
        logger.info(f"Developer mode enabled: '{developer_branch}' branch checked out.")
        # Optionally, still run checks and log/display warnings in dev mode
        # For now, just enabling dev mode is enough.
    elif current_branch in protected_branches:
        is_developer_mode = False
        ui_manager_instance.append_output(f"ℹ️ Running on protected branch '{current_branch}'. Performing integrity checks...", style_class='info')
        
        # 1. Check for clean working directory
        is_clean = await git_context_manager_instance.is_working_directory_clean()
        if not is_clean:
            status_output = await git_context_manager_instance.get_working_tree_status() # Get details
            error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): Uncommitted local changes detected."
            detail_msg = f"   Git status details:\n{status_output if status_output else 'Could not get detailed status.'}"
            ui_manager_instance.append_output(error_msg, style_class='error')
            ui_manager_instance.append_output(detail_msg, style_class='error')
            logger.critical(f"{error_msg}\n{detail_msg}")
            integrity_ok = False
        else:
            ui_manager_instance.append_output(f"✅ Working directory is clean for branch '{current_branch}'.", style_class='info')


        # 2. Check sync status with remote (only if working dir is clean)
        if integrity_ok:
            # fetch_remote_branch is now called inside compare_head_with_remote_tracking
            comparison_status, local_h, remote_h = await git_context_manager_instance.compare_head_with_remote_tracking(current_branch)
            
            if comparison_status == "synced":
                ui_manager_instance.append_output(f"✅ Branch '{current_branch}' is synced with 'origin/{current_branch}'.", style_class='success')
                logger.info(f"Branch '{current_branch}' (Local: {local_h[:7] if local_h else 'N/A'}) is synced with remote (Remote: {remote_h[:7] if remote_h else 'N/A'}).")
            elif comparison_status == "no_upstream":
                 warn_msg = f"⚠️ Branch '{current_branch}' has no upstream configured or remote branch not found. Cannot verify sync. Proceeding with caution."
                 ui_manager_instance.append_output(warn_msg, style_class='warning')
                 logger.warning(warn_msg)
                 # Decide if this is a critical failure or just a warning. For now, a warning.
            elif comparison_status == "fetch_failed": # This case might be removed if fetch is always part of compare
                 warn_msg = f"⚠️ Could not fetch remote for branch '{current_branch}'. Sync status check might be based on stale data."
                 ui_manager_instance.append_output(warn_msg, style_class='warning')
                 logger.warning(warn_msg)
                 # For now, let's not make this a hard fail, but it's a risk.
            elif comparison_status in ["ahead", "behind", "diverged"]:
                error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): Local branch has {comparison_status} from 'origin/{current_branch}'."
                detail_msg = f"   Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}"
                ui_manager_instance.append_output(error_msg, style_class='error')
                ui_manager_instance.append_output(detail_msg, style_class='error')
                logger.critical(f"{error_msg} {detail_msg}")
                integrity_ok = False
            else: # "error" or unexpected status
                error_msg = f"❌ Integrity Check Failed (Branch: {current_branch}): Could not determine sync status with remote. Status: {comparison_status}"
                ui_manager_instance.append_output(error_msg, style_class='error')
                logger.critical(error_msg)
                integrity_ok = False
        
        # 3. (Future) GPG Signed Tag/Commit Check for 'main' branch
        # if current_branch == "main" and integrity_ok:
        #     is_trusted_commit, sig_status_msg = await git_context_manager_instance.verify_commit_signature(head_commit) # or verify against a known tag's commit
        #     if not is_trusted_commit:
        #         ui_manager_instance.append_output(f"❌ Integrity Check Failed (Branch: main): Commit '{head_commit[:7]}' signature check failed: {sig_status_msg}", style_class='error')
        #         logger.critical(f"Commit signature check failed for main branch HEAD {head_commit}: {sig_status_msg}")
        #         integrity_ok = False
        #     else:
        #         ui_manager_instance.append_output(f"✅ Commit '{head_commit[:7]}' on main branch passed signature check (Placeholder).", style_class='success')


        if integrity_ok:
            ui_manager_instance.append_output(f"✅ All integrity checks passed for branch '{current_branch}'.", style_class='success')
            logger.info(f"All integrity checks passed for branch '{current_branch}'.")
        elif halt_on_failure:
            logger.critical(f"Halting application due to integrity check failure on protected branch '{current_branch}'.")
            # _exit_app_main() will be called by the caller of this function if integrity_ok is False
            pass # Caller handles exit

    else: # Other branches (feature branches, detached HEAD)
        is_developer_mode = True
        ui_manager_instance.append_output(
            f"ℹ️ Running on unrecognized branch/commit '{current_branch}'. Developer mode assumed. Integrity checks informational.",
            style_class='info'
        )
        logger.info(f"Developer mode assumed for unrecognized branch/commit: '{current_branch}'.")

    return is_developer_mode, integrity_ok


async def main_async_runner():
    global app_instance, ui_manager_instance, shell_engine_instance, git_context_manager_instance

    # Initialize UIManager early for startup messages
    ui_manager_instance = UIManager(config)
    ui_manager_instance.main_exit_app_ref = _exit_app_main # For UIManager to exit app
    ui_manager_instance.main_restore_normal_input_ref = restore_normal_input_handler

    # --- Perform Startup Integrity Checks ---
    is_developer_mode, integrity_checks_passed = await perform_startup_integrity_checks()
    
    # If integrity checks failed and we are not in developer mode, halt.
    # The perform_startup_integrity_checks function already appends UI messages.
    integrity_config = config.get("integrity_check", {})
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)

    if not is_developer_mode and not integrity_checks_passed and halt_on_failure:
        # Messages already displayed by perform_startup_integrity_checks
        logger.critical("Halting micro_X due to failed integrity checks on a protected branch.")
        _exit_app_main() # Request application exit
        return # Important to return here to stop further initialization

    # Initialize ShellEngine - it needs config and ui_manager.
    shell_engine_instance = ShellEngine(config, ui_manager_instance,
                                        category_manager_module=sys.modules['modules.category_manager'],
                                        ai_handler_module=sys.modules['modules.ai_handler'],
                                        ollama_manager_module=sys.modules['modules.ollama_manager'],
                                        main_exit_app_ref=_exit_app_main,
                                        main_restore_normal_input_ref=restore_normal_input_handler,
                                        is_developer_mode=is_developer_mode, # Pass determined mode
                                        git_context_manager_instance=git_context_manager_instance # Pass GCM instance
                                        )

    # Check Ollama service readiness using the ShellEngine's ollama_manager_module
    # This can now happen after integrity checks
    ollama_service_ready = await shell_engine_instance.ollama_manager_module.ensure_ollama_service(config, ui_manager_instance.append_output)

    if not ollama_service_ready:
        ui_manager_instance.append_output("⚠️ Ollama service is not available or failed to start. AI-dependent features will be affected.", style_class='error')
        ui_manager_instance.append_output("   You can try '/ollama help' for manual control options.", style_class='info')
        logger.warning("Ollama service check failed or service could not be started.")
    else:
        ui_manager_instance.append_output("✅ Ollama service is active and ready.", style_class='success')
        logger.info("Ollama service is active.")

    # Initialize category manager
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

    initial_buffer_for_ui = list(ui_manager_instance.output_buffer) # Get current buffer content (includes integrity messages)
    is_buffer_empty_or_just_welcome = not initial_buffer_for_ui or \
                                      (len(initial_buffer_for_ui) == 1 and initial_buffer_for_ui[0][1] == initial_welcome_message)

    if is_buffer_empty_or_just_welcome and not any(item[1] == initial_welcome_message for item in initial_buffer_for_ui):
        # Prepend welcome if buffer is empty or only had a previous welcome attempt
        initial_buffer_for_ui.insert(0, ('class:welcome', initial_welcome_message))
    elif not any(item[1] == initial_welcome_message for item in initial_buffer_for_ui):
        # Append if buffer has content but not the welcome message
        initial_buffer_for_ui.append(('class:welcome', initial_welcome_message))


    layout_from_ui_manager = ui_manager_instance.initialize_ui_elements(
        initial_prompt_text=f"({initial_prompt_dir}) > ",
        history=history,
        output_buffer_main=initial_buffer_for_ui # Pass the potentially modified buffer
    )

    if ui_manager_instance and ui_manager_instance.input_field:
        ui_manager_instance.input_field.buffer.accept_handler = normal_input_accept_handler
    else:
        logger.critical("UIManager did not create input_field. Cannot set accept_handler.")
        return # Critical failure

    app_instance = Application(
        layout=layout_from_ui_manager,
        key_bindings=ui_manager_instance.get_key_bindings(),
        style=ui_manager_instance.style,
        full_screen=True,
        mouse_support=True
    )
    if ui_manager_instance:
        ui_manager_instance.app = app_instance # Give UIManager a reference to the app

    logger.info("micro_X Shell application starting.")
    await app_instance.run_async()
    logger.info("micro_X Shell application run_async completed.")


def run_shell():
    try:
        asyncio.run(main_async_runner())
    except (EOFError, KeyboardInterrupt):
        print("\nExiting micro_X Shell. 👋"); logger.info("Exiting due to EOF or KeyboardInterrupt at run_shell level.")
    except SystemExit as e: # Catch SystemExit from _exit_app_main
        if e.code == 0:
             print("\nExiting micro_X Shell. 👋"); logger.info("Exiting micro_X Shell normally.")
        else:
             print(f"\nExiting micro_X Shell due to an issue (Code: {e.code}). Check logs at {LOG_FILE}"); logger.warning(f"Exiting micro_X Shell with code {e.code}.")
    except Exception as e:
        print(f"\nUnexpected critical error: {e}"); logger.critical("Critical error in run_shell or main_async_runner", exc_info=True)
    finally:
        # Log final shutdown state from GitContextManager if available
        global git_context_manager_instance
        if git_context_manager_instance : # Check if instance was created
            # Try to get current loop; if not running, these async calls might fail or not complete.
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError: # No running event loop
                loop = None

            if loop and loop.is_running():
                try:
                    # These calls are async, ensure they can run if loop is still active
                    final_branch = asyncio.run_coroutine_threadsafe(git_context_manager_instance.get_current_branch(), loop).result(timeout=1)
                    final_commit = asyncio.run_coroutine_threadsafe(git_context_manager_instance.get_head_commit_hash(), loop).result(timeout=1)
                    logger.info(f"micro_X Shell final state: Branch='{final_branch}', Commit='{final_commit[:7] if final_commit else 'N/A'}'")
                except Exception as git_log_err: # Catch timeout or other errors
                    logger.error(f"Error logging final git state during active loop: {git_log_err}")
            else: # Fallback if no loop or not running, log what we can (might be limited)
                 logger.info(f"micro_X Shell final state (sync log attempt): Project Root='{git_context_manager_instance.project_root}' (Branch/commit info requires running loop for async calls)")


        logger.info("micro_X Shell application stopped.")
        # Ensure logs are flushed if using buffered handlers, though FileHandler usually flushes on close/exit.
        logging.shutdown()


if __name__ == "__main__":
    run_shell()
