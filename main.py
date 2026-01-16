# main.py

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
import socket
import datetime 
from typing import Tuple, Optional

# --- Pre-Import Configuration Step ---
# We must load config and set OLLAMA_HOST *before* importing modules that might 
# initialize Ollama clients at module level (like langchain_ollama).

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = "logs"
CONFIG_DIR = "config"
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True)
HISTORY_FILENAME = ".micro_x_history"
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME)

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)]
)
logging.getLogger("markdown_it").setLevel(logging.WARNING) # Reduce noise
logger = logging.getLogger(__name__)

# --- Load Startup Modules ---
from modules.startup.config_loader import load_configuration_early
from modules.startup.integrity import perform_startup_integrity_checks, StartupIntegrityError
from modules.startup.api_server import start_api_server, API_SOCKET_PATH
import modules.config_handler

# Perform early config load
config = load_configuration_early(SCRIPT_DIR, CONFIG_DIR)

# Set OLLAMA_HOST immediately
ollama_host = config.get('ollama_service', {}).get('ollama_host', 'http://localhost')
ollama_port = config.get('ollama_service', {}).get('ollama_port', 11434)

# Ensure protocol is present
if not str(ollama_host).startswith(('http://', 'https://')):
    ollama_host = f'http://{ollama_host}'

os.environ['OLLAMA_HOST'] = f"{ollama_host}:{ollama_port}"
logger.info(f"Initialized OLLAMA_HOST={os.environ['OLLAMA_HOST']}")

# --- Now Import the rest of the application ---
from prompt_toolkit import Application
from prompt_toolkit.history import FileHistory

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
from modules.textual_ui_manager import TextualUIManager
from modules.textual_app import MicroXTextualApp
from modules.embedding_manager import EmbeddingManager

app_instance = None
ui_manager_instance = None
shell_engine_instance = None
git_context_manager_instance = None

# --- Process Management & Concurrency Control ---
input_lock = asyncio.Lock()


# Ensure Ollama Manager knows about the config (redundant but safe)
modules.ollama_manager.set_ollama_host_from_config(config)

def normal_input_accept_handler(buff):
    """Universal handler for input submission from both prompt_toolkit and Curses UI."""
    global shell_engine_instance, ui_manager_instance, config

    user_input_stripped = buff.strip() if isinstance(buff, str) else buff.text.strip()
    logger.info(f"normal_input_accept_handler received: '{user_input_stripped}'")

    if isinstance(ui_manager_instance, CursesUIManager):
        ui_manager_instance.input_text = ""

    was_in_edit_mode = ui_manager_instance.is_in_edit_mode if ui_manager_instance else False
    if was_in_edit_mode:
        logger.info("Input submission is from edit mode context.")

    async def _handle_input():
        command_lock_timeout = config.get('timeouts', {}).get('command_lock_timeout_seconds', 15.0)
        
        try:
            await asyncio.wait_for(input_lock.acquire(), timeout=command_lock_timeout)
        except asyncio.TimeoutError:
            logger.error(f"Could not acquire input lock within {command_lock_timeout}s. A previous command may be stuck.")
            if ui_manager_instance and shell_engine_instance:
                hung_task_result = await ui_manager_instance.prompt_for_hung_task(shell_engine_instance.current_process_command)
                action = hung_task_result.get('action')
                if action == 'kill':
                    await shell_engine_instance.kill_current_process()
                    # After killing, we can now re-acquire the lock and proceed with the new command.
                    # The lock should have been released by the finally block of the killed task's execution wrapper.
                    # To be safe, we can try to acquire it again here.
                    if not input_lock.locked():
                         asyncio.create_task(_handle_input()) # Retry the original input
                    else:
                        ui_manager_instance.append_output("⚠️ Lock still held after kill signal. Please restart.", style_class='error')
                elif action == 'ignore':
                    ui_manager_instance.append_output("ℹ️ Ignoring hung task. Your new command is queued.", style_class='info')
                    asyncio.create_task(_handle_input()) # Re-queue the current command
            return

        try:
            was_handled_as_builtin = await shell_engine_instance.handle_built_in_command(user_input_stripped)

            if not was_handled_as_builtin:
                await shell_engine_instance.submit_user_input(user_input_stripped, from_edit_mode=was_in_edit_mode)
            else:
                if not was_in_edit_mode and shell_engine_instance and shell_engine_instance.main_restore_normal_input_ref:
                    shell_engine_instance.main_restore_normal_input_ref()
        finally:
            if input_lock.locked():
                input_lock.release()
            
            if was_in_edit_mode:
                logger.debug("Input was from edit mode; explicitly calling restore_normal_input_handler.")
                if ui_manager_instance:
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
    """Triggers a clean exit of the application by raising SystemExit."""
    logger.info("Exit requested by a component. Raising SystemExit(0) to terminate.")
    sys.exit(0)





async def main_async_runner():
    """ Main asynchronous runner for the application. """
    global app_instance, ui_manager_instance, shell_engine_instance, git_context_manager_instance

    # Start the API server as a background task
    api_server_task = asyncio.create_task(start_api_server(input_lock, lambda: shell_engine_instance))
    logger.info("API server task created.")

    # Initialize history early for UI backends that need it
    history = FileHistory(HISTORY_FILE_PATH)

    # --- FIX START: UI Backend Selection and Initialization ---
    # This block correctly selects the UI backend based on the configuration,
    # initializes the appropriate UI manager, and then passes the instance
    # to the ShellEngine. This resolves the dependency order issue.
    ui_backend_choice = config.get("ui", {}).get("ui_backend", "prompt_toolkit")

    # 1. Create the ShellEngine instance first, but without the ui_manager reference.
    shell_engine_instance = ShellEngine(config, None, # ui_manager is set later
                                        category_manager_module=sys.modules['modules.category_manager'],
                                        ai_handler_module=sys.modules['modules.ai_handler'],
                                        ollama_manager_module=sys.modules['modules.ollama_manager'],
                                        main_exit_app_ref=_exit_app_main,
                                        main_restore_normal_input_ref=restore_normal_input_handler,
                                        main_normal_input_accept_handler_ref=normal_input_accept_handler,
                                        is_developer_mode=False, # Will be set after integrity checks
                                        git_context_manager_instance=None # Will be set after integrity checks
                                        )

    # 2. Create the UI manager instance, passing the shell_engine_instance to it.
    if ui_backend_choice == "curses":
        logger.info("Selected UI Backend: curses")
        ui_manager_instance = CursesUIManager(config, shell_engine_instance)
    elif ui_backend_choice == "textual":
        logger.info("Selected UI Backend: textual")
        ui_manager_instance = TextualUIManager(config, shell_engine_instance)
    else:
        if ui_backend_choice != "prompt_toolkit":
            logger.warning(f"Unrecognized UI backend '{ui_backend_choice}' configured. Defaulting to 'prompt_toolkit'.")
        logger.info("Selected UI Backend: prompt_toolkit")
        ui_manager_instance = UIManager(config, shell_engine_instance)

    # 3. Now, set the ui_manager on the shell_engine_instance.
    shell_engine_instance.ui_manager = ui_manager_instance

    # 3. For CursesUIManager, ensure the shell_engine_instance is set after its creation.
    if isinstance(ui_manager_instance, CursesUIManager):
      ui_manager_instance.shell_engine_instance = shell_engine_instance
      ui_manager_instance.main_exit_app_ref = _exit_app_main
    
    # --- FIX END ---

    # Initialize Git context after the shell engine has its ui_manager
    git_fetch_timeout_from_config = config.get('timeouts', {}).get('git_fetch_timeout')
    if git_fetch_timeout_from_config is not None:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR, fetch_timeout=git_fetch_timeout_from_config)
    else:
        git_context_manager_instance = GitContextManager(project_root=SCRIPT_DIR)
    shell_engine_instance.git_context_manager_instance = git_context_manager_instance

    # Perform integrity checks and set developer mode flag on shell engine
    is_developer_mode, integrity_checks_passed = await perform_startup_integrity_checks(
        config, ui_manager_instance, SCRIPT_DIR, git_context_manager_instance
    )
    shell_engine_instance.is_developer_mode = is_developer_mode

    integrity_config = config.get("integrity_check", {})
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)

    if not is_developer_mode and not integrity_checks_passed and halt_on_failure:
        # This block is now primarily for logging, the exception is the key signal
        logger.critical("Halting micro_X due to failed integrity checks on a protected branch.")
        # The actual error with details should have already been raised by a sub-check.
        # This is a fallback to ensure halting if a sub-check returns False instead of raising.
        raise StartupIntegrityError("Failed integrity checks on a protected branch.", details="Halting as per configuration.")

    ui_manager_instance.main_exit_app_ref = _exit_app_main
    ui_manager_instance.main_restore_normal_input_ref = restore_normal_input_handler

    if config.get("behavior", {}).get("verbosity_level") != "quiet":
        ollama_service_ready = await shell_engine_instance.ollama_manager_module.ensure_ollama_service(config, ui_manager_instance.append_output)
        if not ollama_service_ready:
            ui_manager_instance.append_output("⚠️ Ollama service is not available or failed to start. AI-dependent features will be affected.", style_class='error')
            ui_manager_instance.append_output("   You can try '/ollama help' for manual control options.", style_class='info')
            logger.warning("Ollama service check failed or service could not be started.")
        else:
            ui_manager_instance.append_output("✅ Ollama service is active and ready.", style_class='success')
            logger.info("Ollama service is active.")
            embedding_manager_instance = EmbeddingManager(config)
            embedding_manager_instance.initialize()
            shell_engine_instance.embedding_manager_instance = embedding_manager_instance
    else:
        # In quiet mode, we still need to check for the service, but we don't print messages.
        ollama_service_ready = await shell_engine_instance.ollama_manager_module.is_ollama_server_running()
        if ollama_service_ready:
            embedding_manager_instance = EmbeddingManager(config)
            embedding_manager_instance.initialize()
            shell_engine_instance.embedding_manager_instance = embedding_manager_instance


    init_category_manager(SCRIPT_DIR, CONFIG_DIR, ui_manager_instance.append_output)

    home_dir = os.path.expanduser("~")
    max_prompt_len = config.get('ui', {}).get('max_prompt_length', 20)
    current_dir_for_prompt = shell_engine_instance.current_directory
    if current_dir_for_prompt == home_dir: initial_prompt_dir = "~"
    elif current_dir_for_prompt.startswith(home_dir + os.sep):
        rel_path = current_dir_for_prompt[len(home_dir)+1:]; full_rel_prompt = "~"; full_rel_prompt += rel_path
        initial_prompt_dir = full_rel_prompt if len(full_rel_prompt) <= max_prompt_len else "~"; initial_prompt_dir += "..." + rel_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
    else:
        base_name = os.path.basename(current_dir_for_prompt)
        initial_prompt_dir = base_name if len(base_name) <= max_prompt_len else "..." + base_name[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."

    if config.get("behavior", {}).get("verbosity_level") != "quiet":
        # Check for Documentation Knowledge Base
        kb_path = os.path.join(SCRIPT_DIR, "knowledge_bases", "micro_X_docs")
        kb_hint = ""
        if not os.path.exists(kb_path):
            kb_hint = "\nℹ️  Documentation Knowledge Base is missing. Run '/docs --build-kb' to build it."

        version = config.get("application", {}).get("version", "unknown")
        try:
            current_branch = await git_context_manager_instance.get_current_branch()
        except Exception:
            current_branch = "N/A"

        initial_welcome_message = f"""
# Welcome to micro_X Shell 🚀
**Version:** {version} | **Branch:** {current_branch}

**Getting Started:**
* Type a standard Linux command (e.g., `ls -la`).
* Type a natural language query (e.g., "show me large files").

**Shortcuts:**
* **Copy:** Hold `Shift` + Select, then `Ctrl+Shift+C`
* **Paste:** `Ctrl+Shift+V`
* **Help:** `F1` or type `/help`
* **Quit:** `Ctrl+Q`
"""
        initial_welcome_message += kb_hint

        initial_buffer_for_ui = list(ui_manager_instance.output_buffer)

        is_buffer_empty_or_just_welcome = not initial_buffer_for_ui or \
                                          (len(initial_buffer_for_ui) == 1 and initial_buffer_for_ui[0][1] == initial_welcome_message)

        if is_buffer_empty_or_just_welcome and not any(item[1] == initial_welcome_message for item in initial_buffer_for_ui):
            initial_buffer_for_ui.insert(0, ('class:welcome', initial_welcome_message))
        elif not any(item[1] == initial_welcome_message for item in initial_buffer_for_ui):
            initial_buffer_for_ui.append(('class:welcome', initial_welcome_message))
    else:
        initial_buffer_for_ui = []

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
    elif ui_backend_choice == "textual":
        logger.info("Starting Textual App...")
        # Initialize Textual App
        history_strings = list(history.load_history_strings())
        # Pass the current output buffer as initial logs
        app_instance = MicroXTextualApp(
            shell_engine=shell_engine_instance, 
            history=history_strings,
            initial_logs=initial_buffer_for_ui,
            history_path=HISTORY_FILE_PATH
        )
        if isinstance(ui_manager_instance, TextualUIManager):
            ui_manager_instance.app = app_instance
        app_instance.shell_engine = shell_engine_instance
        
        await app_instance.run_async()
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
    version = config.get("application", {}).get("version", "unknown")
    logger.info("=" * 80)
    logger.info(f"  micro_X Session Started (Version: {version})")
    logger.info(f"  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    try:
        asyncio.run(main_async_runner())
    except StartupIntegrityError as e:
        print(f"\nFATAL STARTUP ERROR: {e}")
        if e.details:
            print(f"\n{e.details}")
        print("\nPlease resolve the Git integrity issues before running on this protected branch.")
        logger.critical(f"Application halting due to fatal integrity error: {e}", exc_info=True)
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
        # Clean up the API socket file
        if os.path.exists(API_SOCKET_PATH):
            os.remove(API_SOCKET_PATH)
            logger.info(f"Cleaned up API socket file: {API_SOCKET_PATH}")

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
