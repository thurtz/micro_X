# main.py

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

# --- New Import ---
import modules.config_handler

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
from modules.curses_ui_manager import CursesUIManager

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

# --- FIX: Define a custom exception for integrity check failures ---
class StartupIntegrityError(Exception):
    """Custom exception to signal a fatal integrity check failure during startup."""
    pass

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
    """
    Loads configurations from default and user JSONC files.
    The default_config.json file is mandatory for the application to start.
    It now uses the config_handler module to support comments.
    """
    global config
    default_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, USER_CONFIG_FILENAME)

    # Step 1: Load the mandatory default configuration file.
    base_config = modules.config_handler.load_jsonc_file(default_config_path)
    if base_config is None:
        error_msg = f"CRITICAL ERROR: Default configuration file not found or failed to parse at '{default_config_path}'. Application cannot start."
        logger.critical(error_msg)
        raise FileNotFoundError(error_msg)

    logger.info(f"Successfully loaded base configuration from {default_config_path}")
    config = base_config

    # Step 2: Load optional user configuration and merge it.
    user_settings = modules.config_handler.load_jsonc_file(user_config_path)
    if user_settings:
        config = merge_configs(config, user_settings)
        logger.info(f"Loaded and merged user configurations from {user_config_path}")
    else:
        logger.info(f"{user_config_path} not found or is invalid. No user configuration overrides applied.")


load_configuration() # Load config at startup

def normal_input_accept_handler(buff):
    """
    Handles normal user input submission from the prompt_toolkit input field. This is the default handler for the input field.
    It's also used when submitting an edited command after choosing 'Modify' in AI confirmation.

    This function is a universal handler for both prompt_toolkit's buffer object and the raw
    string passed from CursesUIManager, ensuring compatibility across both UI backends.
    """
    global shell_engine_instance, ui_manager_instance # These are globals

    # Check if the input is a raw string (from the Curses UI) or a buffer (from prompt_toolkit)
    if isinstance(buff, str):
        user_input_stripped = buff.strip()
    else:
        # Assume it's a prompt_toolkit buffer-like object
        user_input_stripped = buff.text.strip()

    logger.info(f"normal_input_accept_handler received: '{user_input_stripped}'")

    # FIX: Explicitly clear the CursesUIManager's input buffer to prevent the visual bug
    # where the text remains on screen while the asynchronous processing runs.
    if isinstance(ui_manager_instance, CursesUIManager):
        ui_manager_instance.input_text = ""

    was_in_edit_mode = False
    if ui_manager_instance:
        was_in_edit_mode = ui_manager_instance.is_in_edit_mode
        if was_in_edit_mode:
            logger.info("Input submission is from edit mode context.")

    async def _handle_input():
        try:
            # --- START OF CHANGE ---
            # This logic ensures that the separator is added after built-in commands like /help.
            was_handled_as_builtin = await shell_engine_instance.handle_built_in_command(user_input_stripped)

            if not was_handled_as_builtin:
                # If it wasn't a built-in, process it as a normal command.
                # The separator logic for this path is handled within ShellEngine.process_command.
                await shell_engine_instance.submit_user_input(user_input_stripped, from_edit_mode=was_in_edit_mode)
            else:
                # If a built-in command was handled (and it wasn't an exit command, which would have
                # terminated the process), we need to manually restore the input handler to ensure
                # the UI state is correct and the separator is added.
                # We skip this if we were in edit mode, as the 'finally' block below will handle it.
                if not was_in_edit_mode:
                    if shell_engine_instance and shell_engine_instance.main_restore_normal_input_ref:
                        shell_engine_instance.main_restore_normal_input_ref()
            # --- END OF CHANGE ---
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

# --- FIX: Removed the _exit_app_main() function.
# Its logic is now handled by the SystemExit exception raised directly by sys.exit().

async def perform_startup_integrity_checks() -> Tuple[bool, bool]:
    """
    Performs Git integrity checks at startup. Returns: (is_developer_mode, integrity_ok)
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

    # --- FIX START: UI Backend Selection and Initialization ---
    # This block correctly selects the UI backend based on the configuration,
    # initializes the appropriate UI manager, and then passes the instance
    # to the ShellEngine. This resolves the dependency order issue.
    ui_backend_choice = config.get("ui", {}).get("ui_backend", "prompt_toolkit")

    # 1. Create the UI manager instance first.
    if ui_backend_choice == "curses":
        logger.info("Selected UI Backend: curses")
        ui_manager_instance = CursesUIManager(config)
    else:
        if ui_backend_choice != "prompt_toolkit":
            logger.warning(f"Unrecognized UI backend '{ui_backend_choice}' configured. Defaulting to 'prompt_toolkit'.")
        logger.info("Selected UI Backend: prompt_toolkit")
        ui_manager_instance = UIManager(config)

    # 2. Create the ShellEngine instance and pass the UI manager to it.
    shell_engine_instance = ShellEngine(config, ui_manager_instance,
                                        category_manager_module=sys.modules['modules.category_manager'],
                                        ai_handler_module=sys.modules['modules.ai_handler'],
                                        ollama_manager_module=sys.modules['modules.ollama_manager'],
                                        main_restore_normal_input_ref=restore_normal_input_handler,
                                        main_normal_input_accept_handler_ref=normal_input_accept_handler,
                                        is_developer_mode=False, # Will be set after integrity checks
                                        git_context_manager_instance=None # Will be set after integrity checks
                                        )

    # 3. For CursesUIManager, ensure the shell_engine_instance is set after its creation.
    if isinstance(ui_manager_instance, CursesUIManager):
      ui_manager_instance.shell_engine_instance = shell_engine_instance
    # --- FIX END ---

    # Initialize Git context after the shell engine has its ui_manager
    git_fetch_timeout_from_config = config.get('timeouts', {}).get('git_fetch_timeout')
    if git_fetch_timeout_from_config is not None:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR, fetch_timeout=git_fetch_timeout_from_config)
    else:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR)
    shell_engine_instance.git_context_manager_instance = git_context_manager_instance

    # Perform integrity checks and set developer mode flag on shell engine
    is_developer_mode, integrity_checks_passed = await perform_startup_integrity_checks()
    shell_engine_instance.is_developer_mode = is_developer_mode

    integrity_config = config.get("integrity_check", {})
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)

    if not is_developer_mode and not integrity_checks_passed and halt_on_failure:
        logger.critical("Halting micro_X due to failed integrity checks on a protected branch.")
        raise StartupIntegrityError("Failed integrity checks on a protected branch.")

    ui_manager_instance.main_restore_normal_input_ref = restore_normal_input_handler

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

    # --- FIX START: Conditional UI Initialization Arguments ---
    # This block constructs the arguments for initialize_ui_elements
    # conditionally, preventing a TypeError because CursesUIManager and UIManager
    # expect different parameters.
    kwargs_for_ui_init = {
        "initial_prompt_text": f"({initial_prompt_dir}) > ",
        "history": history,
        "output_buffer_main": initial_buffer_for_ui
    }
    # The Curses UI manager needs a reference to the shell engine for its input loop.
    if ui_backend_choice == "curses":
        kwargs_for_ui_init["shell_engine_instance"] = shell_engine_instance

    layout_or_stdscr = ui_manager_instance.initialize_ui_elements(**kwargs_for_ui_init)
    # --- FIX END ---

    # --- FIX START: Conditional Application Execution ---
    # This block correctly handles the two different execution paths for the
    # selected UI backend.
    if ui_backend_choice == "curses":
        # CursesUIManager has its own async run loop.
        await ui_manager_instance.run_async()
    else:
        # This is the original path for the prompt_toolkit backend.
        if ui_manager_instance and ui_manager_instance.input_field:
            ui_manager_instance.input_field.buffer.accept_handler = normal_input_accept_handler
        else:
            logger.critical("UIManager did not create input_field. Cannot set accept_handler.")
            sys.exit(1) # Use sys.exit directly

        if ui_manager_instance:
            ui_manager_instance.initial_prompt_settled = True
            ui_manager_instance.last_output_was_separator = False
            ui_manager_instance.add_startup_separator()

        enable_mouse = config.get("ui", {}).get("enable_mouse_support", False)
        logger.info(f"Prompt Toolkit Application mouse_support will be set to: {enable_mouse}")

        app_instance = Application(
            layout=layout_or_stdscr, # This is the layout from UIManager
            key_bindings=ui_manager_instance.get_key_bindings(),
            style=ui_manager_instance.style,
            full_screen=True,
            mouse_support=enable_mouse
        )
        if ui_manager_instance:
            ui_manager_instance.app = app_instance

        logger.info("micro_X Shell application starting.")
        await app_instance.run_async()
    # --- FIX END ---

    logger.info("micro_X Shell application run_async completed.")


def run_shell():
    """ Main entry point to run the shell application. """
    logger.info("=" * 80)
    logger.info("  micro_X Session Started")
    logger.info(f"  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    try:
        asyncio.run(main_async_runner())
    except StartupIntegrityError as e:
        print(f"\nFATAL STARTUP ERROR: {e}")
        print("Please resolve the Git integrity issues before running on this protected branch.")
        logger.critical(f"Application halting due to fatal integrity error: {e}")
    except (FileNotFoundError, ValueError, IOError) as e:
        print(f"\nFATAL STARTUP ERROR: {e}")
        print(f"Please ensure 'config/default_config.json' exists and is a valid JSON file.")
        logger.critical(f"Application halting due to fatal configuration error: {e}")
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
