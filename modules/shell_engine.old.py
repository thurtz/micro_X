# modules/shell_engine.py
import asyncio
import os
import shlex
import subprocess
import uuid
import re
import logging
import time
import shutil
import sys # New import for sys.modules references
import hashlib # Needed for _handle_update_command's get_file_hash

# Imports from other project modules will be added as needed.
from modules.output_analyzer import is_tui_like_output
from modules import ollama_manager
from modules import category_manager
from modules import ai_handler

logger = logging.getLogger(__name__)

class ShellEngine:
    def __init__(self, config, ui_manager, category_manager_module=None, ai_handler_module=None, ollama_manager_module=None, main_exit_app_ref=None, main_restore_normal_input_ref=None):
        """
        Initializes the ShellEngine.

        Args:
            config (dict): The application configuration.
            ui_manager (UIManager): An instance of the UIManager.
            category_manager_module: Reference to the category_manager module or relevant functions.
            ai_handler_module: Reference to the ai_handler module or relevant functions.
            ollama_manager_module: Reference to the ollama_manager module or relevant functions.
            main_exit_app_ref (callable): Callback to main.py's exit function.
            main_restore_normal_input_ref (callable): Callback to main.py's restore_normal_input_handler.
        """
        self.config = config
        self.ui_manager = ui_manager
        self.category_manager_module = category_manager_module
        self.ai_handler_module = ai_handler_module
        self.ollama_manager_module = ollama_manager_module
        self.main_exit_app_ref = main_exit_app_ref
        self.main_restore_normal_input_ref = main_restore_normal_input_ref

        self.current_directory = os.getcwd()
        # Define SCRIPT_DIR and related paths here, as they are needed by moved functions
        self.SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # This should ideally be passed from main
        # For now, derive them based on common project structure assumptions relative to modules/shell_engine.py
        # In a real app, self.SCRIPT_DIR should be provided more explicitly from the main app entry point.
        self.PROJECT_ROOT = os.path.dirname(self.SCRIPT_DIR) if os.path.basename(self.SCRIPT_DIR) == 'modules' else self.SCRIPT_DIR
        self.REQUIREMENTS_FILENAME = "requirements.txt"
        self.REQUIREMENTS_FILE_PATH = os.path.join(self.PROJECT_ROOT, self.REQUIREMENTS_FILENAME)
        self.UTILS_DIR_NAME = "utils"
        self.UTILS_DIR_PATH = os.path.join(self.PROJECT_ROOT, self.UTILS_DIR_NAME)
        os.makedirs(self.UTILS_DIR_PATH, exist_ok=True) # Ensure it exists for listing

        logger.info("ShellEngine initialized.")

    def expand_shell_variables(self, command_string: str) -> str:
        """
        Expands shell variables like $PWD, ${PWD}, and others in a command string.
        Custom handling for $PWD and ${PWD} to use the engine's current_directory.

        Args:
            command_string (str): The command string with potential shell variables.

        Returns:
            str: The command string with variables expanded.
        """
        # Use a unique placeholder for PWD to avoid conflicts with other variables
        # that might be legitimately named PWD (e.g. in a script being analyzed).
        pwd_placeholder = f"__MICRO_X_PWD_PLACEHOLDER_{uuid.uuid4().hex}__"

        # Replace $PWD (not followed by other valid variable characters) and ${PWD} with the placeholder
        temp_command_string = re.sub(r'\$PWD(?![a-zA-Z0-9_])', pwd_placeholder, command_string)
        temp_command_string = re.sub(r'\$\{PWD\}', pwd_placeholder, temp_command_string)

        # Expand other environment variables using os.path.expandvars
        # This will not expand the placeholder as it's not a valid env var format
        expanded_string = os.path.expandvars(temp_command_string)

        # Replace the placeholder with the actual current working directory
        # Use self.current_directory which is managed by the ShellEngine
        expanded_string = expanded_string.replace(pwd_placeholder, self.current_directory)

        if command_string != expanded_string:
            logger.debug(f"Expanded shell variables: '{command_string}' -> '{expanded_string}' (PWD: '{self.current_directory}')")
        return expanded_string

    def sanitize_and_validate(self, command: str, original_input_for_log: str) -> str | None:
        """
        Performs basic sanitization and validation of a command string.
        Blocks known dangerous patterns.

        Args:
            command (str): The command string to sanitize.
            original_input_for_log (str): The original user input, for logging purposes.

        Returns:
            str | None: The sanitized command string, or None if blocked.
        """
        # List of regex patterns for potentially dangerous commands.
        dangerous_patterns = [
            # Modified to not block /tmp paths, but still block other /S* paths with rm -f or -rf
            r'\brm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/(?!(?:tmp|var/tmp)\b)\S*',
            r'\brm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\s*(?:$|\.\.?\s*$|\*(?:\s.*|$))', # Specifically block rm -rf / or rm -rf /*
            r'\bmkfs\b',
            r'\bdd\b\s+if=/dev/random',
            r'\bdd\b\s+if=/dev/zero',
            r'\b(shutdown|reboot|halt|poweroff)\b',
            r'>\s*/dev/sd[a-z]+',
            r':\(\)\{:\|:&};:',
            r'\b(wget|curl)\s+.*\s*\|\s*(sh|bash|python|perl)\b'
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                logger.warning(f"DANGEROUS command blocked (matched pattern '{pattern}'): '{command}' (original input: '{original_input_for_log}')")
                self.ui_manager.append_output(f"🛡️ Command blocked for security: {command}", style_class='security-critical')
                return None
        return command

    async def handle_cd_command(self, full_cd_command: str):
        """
        Handles the 'cd' command, updating the shell's current directory.
        This function was moved from main.py.
        """
        if not self.ui_manager:
            logger.error("ShellEngine.handle_cd_command: UIManager not initialized."); return

        append_output_func = self.ui_manager.append_output
        try:
            parts = full_cd_command.split(" ", 1); target_dir_str = parts[1].strip() if len(parts) > 1 else "~"
            # expanduser and expandvars are fine here, abspath uses current_directory from shell_engine
            expanded_dir_arg = os.path.expanduser(os.path.expandvars(target_dir_str))
            new_dir_abs = os.path.abspath(os.path.join(self.current_directory, expanded_dir_arg)) if not os.path.isabs(expanded_dir_arg) else expanded_dir_arg

            if os.path.isdir(new_dir_abs):
                self.current_directory = new_dir_abs # Update ShellEngine's current_directory
                self.ui_manager.update_input_prompt(self.current_directory)
                append_output_func(f"📂 Changed directory to: {self.current_directory}", style_class='info'); logger.info(f"Directory changed to: {self.current_directory}")
            else: append_output_func(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.", style_class='error'); logger.warning(f"Failed cd to '{new_dir_abs}'.")
        except Exception as e: append_output_func(f"❌ Error processing 'cd' command: {e}", style_class='error'); logger.exception(f"Error in handle_cd_command for '{full_cd_command}'")
        finally:
            # After cd, always restore normal input mode.
            # This calls the main restore_normal_input_ref, which will then call set_normal_input_mode on UIManager
            if self.main_restore_normal_input_ref:
                self.main_restore_normal_input_ref()


    async def execute_shell_command(self, command_to_execute: str, original_user_input_display: str):
        """
        Executes a 'simple' command directly using subprocess.Popen.
        Output is captured and appended to the UI.
        This function was moved from main.py.
        """
        if not self.ui_manager:
            logger.error("ShellEngine.execute_shell_command: UIManager not available.")
            return

        append_output_func = self.ui_manager.append_output
        logger.info(f"Executing simple command: '{command_to_execute}' in '{self.current_directory}'")
        try:
            if not command_to_execute.strip():
                append_output_func("⚠️ Empty command cannot be executed.", style_class='warning')
                logger.warning(f"Attempted to execute empty command: '{command_to_execute}' from input: '{original_user_input_display}'")
                return

            process = await asyncio.create_subprocess_shell(
                command_to_execute,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.current_directory
            )
            stdout, stderr = await process.communicate()

            output_prefix = f"Output from '{original_user_input_display}':\n"

            if stdout:
                append_output_func(f"{output_prefix}{stdout.decode(errors='replace').strip()}")
            if stderr:
                append_output_func(f"Stderr from '{original_user_input_display}':\n{stderr.decode(errors='replace').strip()}", style_class='warning')

            if not stdout and not stderr and process.returncode == 0:
                append_output_func(f"{output_prefix}(No output)", style_class='info')

            if process.returncode != 0:
                logger.warning(f"Command '{command_to_execute}' exited with code {process.returncode}")
                if not stderr: # If stderr already printed, this might be redundant
                    append_output_func(f"⚠️ Command '{original_user_input_display}' exited with code {process.returncode}.", style_class='warning')

        except FileNotFoundError: # Typically means 'bash' or the command itself wasn't found
            append_output_func(f"❌ Shell (bash) or command not found for: {command_to_execute}", style_class='error')
            logger.error(f"Shell (bash) or command not found for: {command_to_execute}")
        except Exception as e:
            append_output_func(f"❌ Error executing '{command_to_execute}': {e}", style_class='error')
            logger.exception(f"Error executing shell command: {e}")

    async def execute_command_in_tmux(self, command_to_execute: str, original_user_input_display: str, category: str):
        """
        Executes a 'semi_interactive' or 'interactive_tui' command in a new tmux window.
        This function was moved from main.py.
        """
        if not self.ui_manager:
            logger.error("ShellEngine.execute_command_in_tmux: UIManager not available.")
            return

        append_output_func = self.ui_manager.append_output
        logger.info(f"Executing tmux command ({category}): '{command_to_execute}' in '{self.current_directory}'")

        try:
            unique_id = str(uuid.uuid4())[:8]
            window_name = f"micro_x_{unique_id}"

            if shutil.which("tmux") is None:
                append_output_func("❌ Error: tmux not found. Cannot execute command in tmux.", style_class='error')
                logger.error("tmux not found for tmux execution.")
                return

            tmux_poll_timeout = self.config.get('timeouts', {}).get('tmux_poll_seconds', 300)
            tmux_sleep_after = self.config.get('timeouts', {}).get('tmux_semi_interactive_sleep_seconds', 1)
            tmux_log_base = self.config.get('paths', {}).get('tmux_log_base_path', '/tmp')

            if category == "semi_interactive":
                os.makedirs(tmux_log_base, exist_ok=True)
                log_path = os.path.join(tmux_log_base, f"micro_x_output_{unique_id}.log")

                # Properly escape the command for bash -c ''
                replacement_for_single_quote = "'\"'\"'" # bash trick: ' -> '\'' -> '"'"'
                escaped_command_str = command_to_execute.replace("'", replacement_for_single_quote)

                # The wrapped command will execute the user's command, tee its output to a log, and then sleep.
                wrapped_command = f"bash -c '{escaped_command_str}' |& tee {shlex.quote(log_path)}; sleep {tmux_sleep_after}"

                tmux_cmd_list_launch = ["tmux", "new-window", "-d", "-n", window_name, wrapped_command] # -d for detached

                logger.info(f"Launching semi_interactive tmux: {' '.join(tmux_cmd_list_launch)} (log: {log_path})")

                process_launch = await asyncio.create_subprocess_exec(
                    *tmux_cmd_list_launch,
                    cwd=self.current_directory,
                    stdout=asyncio.subprocess.PIPE, # Capture tmux's own stdout/stderr for launch
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_launch, stderr_launch = await process_launch.communicate()

                if process_launch.returncode != 0:
                    err_msg = stderr_launch.decode(errors='replace').strip() if stderr_launch else "Unknown tmux error"
                    append_output_func(f"❌ Error launching semi-interactive tmux session '{window_name}': {err_msg}", style_class='error')
                    logger.error(f"Failed to launch semi-interactive tmux: {err_msg}")
                    return

                append_output_func(f"⚡ Launched semi-interactive command in tmux (window: {window_name}). Waiting for output (max {tmux_poll_timeout}s)...", style_class='info')
                if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()


                start_time = time.time()
                output_captured_from_log = False
                window_closed_or_cmd_done = False

                while time.time() - start_time < tmux_poll_timeout:
                    await asyncio.sleep(1) # Poll interval
                    try:
                        # Check if tmux window still exists
                        check_proc = await asyncio.create_subprocess_exec(
                            "tmux", "list-windows", "-F", "#{window_name}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout_check, _ = await check_proc.communicate()
                        if window_name not in stdout_check.decode(errors='replace'):
                            logger.info(f"Tmux window '{window_name}' for semi-interactive command closed or finished.")
                            window_closed_or_cmd_done = True
                            break
                    except Exception as tmux_err:
                        logger.warning(f"Error checking tmux windows for '{window_name}': {tmux_err}")
                        window_closed_or_cmd_done = True # Assume closed if we can't check
                        break

                if not window_closed_or_cmd_done:
                    append_output_func(f"⚠️ Tmux window '{window_name}' poll timed out. Output might be incomplete or window still running.", style_class='warning')
                    logger.warning(f"Tmux poll for '{window_name}' timed out.")

                # Process the log file
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                            output_content = f.read().strip()

                        tui_line_threshold = self.config.get('behavior', {}).get('tui_detection_line_threshold_pct', 30.0)
                        tui_char_threshold = self.config.get('behavior', {}).get('tui_detection_char_threshold_pct', 3.0)

                        if output_content and is_tui_like_output(output_content, tui_line_threshold, tui_char_threshold):
                            logger.info(f"Output from '{original_user_input_display}' (semi-interactive) detected as TUI-like.")
                            suggestion_command = f'/command move "{command_to_execute}" interactive_tui'
                            append_output_func(f"Output from '{original_user_input_display}':\n[Semi-interactive TUI-like output not displayed directly.]\n💡 Tip: Try: {suggestion_command}", style_class='info')
                            output_captured_from_log = True
                        elif output_content:
                            append_output_func(f"Output from '{original_user_input_display}':\n{output_content}")
                            output_captured_from_log = True
                        elif window_closed_or_cmd_done: # Window closed but log was empty
                            append_output_func(f"Output from '{original_user_input_display}': (No output captured in log)", style_class='info')
                            output_captured_from_log = True
                    except Exception as e_read:
                        logger.error(f"Error reading/analyzing tmux log {log_path}: {e_read}", exc_info=True)
                        append_output_func(f"❌ Error reading/analyzing tmux log: {e_read}", style_class='error')
                    finally:
                        try:
                            os.remove(log_path)
                        except OSError as e_del:
                            logger.error(f"Error deleting tmux log {log_path}: {e_del}")
                elif window_closed_or_cmd_done: # Window closed, no log file found
                    append_output_func(f"Output from '{original_user_input_display}': (Tmux window closed, no log found)", style_class='info')

                if not output_captured_from_log and not window_closed_or_cmd_done: # Timed out, log didn't exist or was empty
                    append_output_func(f"Output from '{original_user_input_display}': (Tmux window may still be running or timed out without output)", style_class='warning')


            else: # "interactive_tui"
                tmux_cmd_list = ["tmux", "new-window", "-n", window_name, command_to_execute]
                logger.info(f"Launching interactive_tui tmux: {' '.join(tmux_cmd_list)}")
                append_output_func(f"⚡ Launching interactive command in tmux (window: {window_name}). micro_X will wait for it to complete or be detached.", style_class='info')
                if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()

                process = await asyncio.to_thread(
                    subprocess.run,
                    tmux_cmd_list,
                    cwd=self.current_directory,
                    check=False
                )

                if process.returncode == 0:
                    append_output_func(f"✅ Interactive tmux session for '{original_user_input_display}' ended.", style_class='success')
                else:
                    err_msg = f"exited with code {process.returncode}"
                    append_output_func(f"❌ Error or non-zero exit in tmux session '{window_name}': {err_msg}", style_class='error')
                    logger.error(f"Error reported by tmux run for cmd '{command_to_execute}': {err_msg}")

        except FileNotFoundError: # For shutil.which("tmux") or if tmux disappears mid-process
            append_output_func("❌ Error: tmux not found.", style_class='error')
            logger.error("tmux not found during tmux interaction.")
        except subprocess.CalledProcessError as e: # Should be caught by specific run checks now
            append_output_func(f"❌ Error interacting with tmux: {e.stderr or e}", style_class='error')
            logger.exception(f"CalledProcessError during tmux interaction: {e}")
        except Exception as e:
            append_output_func(f"❌ Unexpected error interacting with tmux: {e}", style_class='error')
            logger.exception(f"Unexpected error during tmux interaction: {e}")

    # --- Moved Built-in Command Handlers from main.py ---

    def _display_general_help(self):
        if not self.ui_manager: logger.error("display_general_help: UIManager not initialized."); return
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
            ('class:help-text', "  Command history: '.micro_x_history'.\n"),
            ('class:help-text', "\nHappy shelling!\n")
        ]
        help_output_string = "".join([text for _, text in help_text_styled])
        self.ui_manager.append_output(help_output_string, style_class='help-base')
        logger.info("Displayed general help.")

    def _display_ollama_help(self):
        if not self.ui_manager: logger.error("display_ollama_help: UIManager not initialized."); return
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
        self.ui_manager.append_output(help_output_string, style_class='help-base')
        logger.info("Displayed Ollama command help.")

    async def _handle_update_command(self):
        if not self.ui_manager: logger.error("handle_update_command: UIManager not initialized."); return
        self.ui_manager.append_output("🔄 Checking for updates...", style_class='info')
        logger.info("Update command received.")
        current_app_inst = self.ui_manager.get_app_instance()
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

        # Helper function to get file hash (originally in main.py)
        def get_file_hash(filepath):
            if not os.path.exists(filepath): return None
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f: hasher.update(f.read())
            return hasher.hexdigest()

        if not shutil.which("git"):
            self.ui_manager.append_output("❌ Update failed: 'git' not found.", style_class='error')
            logger.error("Update failed: git not found."); return

        # Use self.PROJECT_ROOT and self.REQUIREMENTS_FILE_PATH
        original_req_hash = get_file_hash(self.REQUIREMENTS_FILE_PATH); requirements_changed = False
        try:
            branch_process = await asyncio.to_thread(subprocess.run, ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=self.PROJECT_ROOT, capture_output=True, text=True, check=True)
            current_branch = branch_process.stdout.strip()
            self.ui_manager.append_output(f"ℹ️ On branch: '{current_branch}'. Fetching updates...", style_class='info'); logger.info(f"Current git branch: {current_branch}")
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

            pull_process = await asyncio.to_thread(subprocess.run, ['git', 'pull', 'origin', current_branch], cwd=self.PROJECT_ROOT, capture_output=True, text=True)
            if pull_process.returncode == 0:
                self.ui_manager.append_output(f"✅ Git pull successful.\nOutput:\n{pull_process.stdout.strip()}", style_class='success'); logger.info(f"Git pull output: {pull_process.stdout.strip()}")
                if "Already up to date." in pull_process.stdout: self.ui_manager.append_output("✅ micro_X is up to date.", style_class='success')
                else:
                    self.ui_manager.append_output("✅ Updates downloaded.", style_class='success')
                    if original_req_hash != get_file_hash(self.REQUIREMENTS_FILE_PATH): requirements_changed = True; self.ui_manager.append_output("⚠️ requirements.txt changed.", style_class='warning'); logger.info("requirements.txt changed.")
                    self.ui_manager.append_output("💡 Restart micro_X for changes.", style_class='info')
                    if requirements_changed: self.ui_manager.append_output(f"💡 After restart, update dependencies:\n    cd \"{self.PROJECT_ROOT}\"\n    source .venv/bin/activate\n    pip install -r {self.REQUIREMENTS_FILENAME}", style_class='info')
            else: self.ui_manager.append_output(f"❌ Git pull failed.\nError:\n{pull_process.stderr.strip()}", style_class='error'); logger.error(f"Git pull failed. Stderr: {pull_process.stderr.strip()}")
        except subprocess.CalledProcessError as e: self.ui_manager.append_output(f"❌ Update failed: git error.\n{e.stderr}", style_class='error'); logger.error(f"Update git error: {e}", exc_info=True)
        except FileNotFoundError: self.ui_manager.append_output("❌ Update failed: 'git' not found.", style_class='error'); logger.error("Update failed: git not found.")
        except Exception as e: self.ui_manager.append_output(f"❌ Unexpected error during update: {e}", style_class='error'); logger.error(f"Unexpected update error: {e}", exc_info=True)
        finally:
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

    async def _handle_utils_command_async(self, full_command_str: str):
        if not self.ui_manager: logger.error("handle_utils_command_async: UIManager not initialized."); return
        logger.info(f"Handling /utils command: {full_command_str}")
        self.ui_manager.append_output("🛠️ Processing /utils command...", style_class='info')
        current_app_inst = self.ui_manager.get_app_instance()
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

        try: parts = shlex.split(full_command_str)
        except ValueError as e:
            self.ui_manager.append_output(f"❌ Error parsing /utils command: {e}", style_class='error')
            logger.warning(f"shlex error for /utils '{full_command_str}': {e}")
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

        utils_help_message = "ℹ️ Usage: /utils <script_name_no_ext> [args...] | list | help"
        if len(parts) < 2:
            self.ui_manager.append_output(utils_help_message, style_class='info')
            logger.debug("Insufficient arguments for /utils command.")
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

        subcommand_or_script_name = parts[1]; args = parts[2:]
        if subcommand_or_script_name.lower() in ["list", "help"]:
            try:
                if not os.path.exists(self.UTILS_DIR_PATH) or not os.path.isdir(self.UTILS_DIR_PATH):
                    self.ui_manager.append_output(f"❌ Utility directory '{self.UTILS_DIR_NAME}' not found at '{self.UTILS_DIR_PATH}'.", style_class='error'); logger.error(f"Utility directory not found: {self.UTILS_DIR_PATH}")
                    if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
                available_scripts = [f[:-3] for f in os.listdir(self.UTILS_DIR_PATH) if os.path.isfile(os.path.join(self.UTILS_DIR_PATH, f)) and f.endswith(".py") and f != "__init__.py"]
                if available_scripts:
                    self.ui_manager.append_output("Available utility scripts (run with /utils <script_name>):", style_class='info')
                    for script_name in sorted(available_scripts): self.ui_manager.append_output(f"  - {script_name}", style_class='info')
                else: self.ui_manager.append_output(f"No executable Python utility scripts found in '{self.UTILS_DIR_NAME}'.", style_class='info')
                logger.info(f"Listed utils scripts: {available_scripts}")
            except Exception as e: self.ui_manager.append_output(f"❌ Error listing utility scripts: {e}", style_class='error'); logger.error(f"Error listing utility scripts: {e}", exc_info=True)
            finally:
                if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

        script_filename = f"{subcommand_or_script_name}.py"; script_path = os.path.join(self.UTILS_DIR_PATH, script_filename)
        if not os.path.isfile(script_path):
            self.ui_manager.append_output(f"❌ Utility script not found: {script_filename} in '{self.UTILS_DIR_NAME}' directory.", style_class='error'); logger.warning(f"Utility script not found: {script_path}")
            self.ui_manager.append_output(utils_help_message, style_class='info')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return

        command_to_execute_list = [sys.executable, script_path] + args; command_str_for_display = f"{sys.executable} {script_path} {' '.join(args)}"
        self.ui_manager.append_output(f"🚀 Executing utility: {command_str_for_display}\n    (Working directory: {self.PROJECT_ROOT})", style_class='info'); logger.info(f"Executing utility script: {command_to_execute_list} with cwd={self.PROJECT_ROOT}")
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()
        try:
            process = await asyncio.to_thread(subprocess.run, command_to_execute_list, capture_output=True, text=True, cwd=self.PROJECT_ROOT, check=False, errors='replace')
            output_prefix = f"Output from '{script_filename}':\n"; has_output = False
            if process.stdout: self.ui_manager.append_output(f"{output_prefix}{process.stdout.strip()}"); has_output = True
            if process.stderr: self.ui_manager.append_output(f"Stderr from '{script_filename}':\n{process.stderr.strip()}", style_class='warning'); has_output = True
            if not has_output and process.returncode == 0: self.ui_manager.append_output(f"{output_prefix}(No output)", style_class='info')

            if process.returncode != 0:
                self.ui_manager.append_output(f"⚠️ Utility '{script_filename}' exited with code {process.returncode}.", style_class='warning')
                logger.warning(f"Utility script '{script_path}' exited with code {process.returncode}. Args: {args}")
            else:
                if not process.stderr: self.ui_manager.append_output(f"✅ Utility '{script_filename}' completed.", style_class='success')
                logger.info(f"Utility script '{script_path}' completed with code {process.returncode}. Args: {args}")
        except FileNotFoundError: self.ui_manager.append_output(f"❌ Error: Python interpreter ('{sys.executable}') or script ('{script_filename}') not found.", style_class='error'); logger.error(f"FileNotFoundError executing utility: {command_to_execute_list}", exc_info=True)
        except Exception as e: self.ui_manager.append_output(f"❌ Unexpected error executing utility '{script_filename}': {e}", style_class='error'); logger.error(f"Error executing utility script '{script_path}': {e}", exc_info=True)
        finally:
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

    async def _handle_ollama_command_async(self, user_input_parts: list):
        if not self.ui_manager: logger.error("handle_ollama_command_async: UIManager not initialized."); return
        append_output_func = self.ui_manager.append_output
        logger.info(f"Handling /ollama command: {user_input_parts}")

        if len(user_input_parts) < 2: self._display_ollama_help(); return
        subcommand = user_input_parts[1].lower()

        if subcommand == "start":
            append_output_func("⚙️ Attempting to start Ollama service...", style_class='info')
            success = await self.ollama_manager_module.explicit_start_ollama_service(self.config, append_output_func)
            if success:
                append_output_func("✅ Ollama service start process initiated. Check status shortly.", style_class='success')
                await self.ollama_manager_module.ensure_ollama_service(self.config, append_output_func)
            else: append_output_func("❌ Ollama service start process failed.", style_class='error')
        elif subcommand == "stop":
            append_output_func("⚙️ Attempting to stop Ollama service...", style_class='info')
            success = await self.ollama_manager_module.explicit_stop_ollama_service(self.config, append_output_func)
            if success: append_output_func("✅ Ollama service stop process initiated.", style_class='success')
            else: append_output_func("❌ Ollama service stop process failed.", style_class='error')
        elif subcommand == "restart":
            append_output_func("⚙️ Attempting to restart Ollama service...", style_class='info')
            success = await self.ollama_manager_module.explicit_restart_ollama_service(self.config, append_output_func)
            if success:
                append_output_func("✅ Ollama service restart process initiated. Check status shortly.", style_class='success')
                await self.ollama_manager_module.ensure_ollama_service(self.config, append_output_func)
            else: append_output_func("❌ Ollama service restart process failed.", style_class='error')
        elif subcommand == "status": await self.ollama_manager_module.get_ollama_status_info(self.config, append_output_func)
        elif subcommand == "help": self._display_ollama_help()
        else: append_output_func(f"❌ Unknown /ollama subcommand: '{subcommand}'.", style_class='error'); logger.warning(f"Unknown /ollama subcommand: {subcommand}")

    async def handle_built_in_command(self, user_input: str) -> bool:
        """
        Handles built-in shell commands like /help, /exit, /update, /utils, /ollama.
        Returns True if a built-in command was handled, False otherwise.
        """
        user_input_stripped = user_input.strip()
        logger.info(f"ShellEngine.handle_built_in_command received: '{user_input_stripped}'")

        if user_input_stripped.lower() in {"/help", "help"}:
            self._display_general_help()
            return True
        elif user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
            self.ui_manager.append_output("Exiting micro_X Shell 🚪", style_class='info')
            logger.info("Exit command received from built-in handler.")
            if self.main_exit_app_ref:
                self.main_exit_app_ref()
            else:
                app_instance = self.ui_manager.get_app_instance()
                if app_instance and app_instance.is_running:
                    app_instance.exit()
            return True
        elif user_input_stripped.lower() == "/update":
            await self._handle_update_command()
            return True
        elif user_input_stripped.startswith("/utils"):
            await self._handle_utils_command_async(user_input_stripped)
            return True
        elif user_input_stripped.startswith("/ollama"):
            try:
                parts = user_input_stripped.split()
                await self._handle_ollama_command_async(parts)
            except Exception as e:
                self.ui_manager.append_output(f"❌ Error processing /ollama command: {e}", style_class='error')
                logger.error(f"Error in /ollama command '{user_input_stripped}': {e}", exc_info=True)
            return True

        return False # Not a built-in command handled by this method

    # --- Phase 2.1: New methods for core command processing ---

    # This function is the core command processing pipeline.
    # It will be moved to ShellEngine as a primary method.
    async def process_command(self, command_str_original: str, original_user_input_for_display: str,
                              ai_raw_candidate: str | None = None,
                              original_direct_input_if_different: str | None = None,
                              forced_category: str | None = None,
                              is_ai_generated: bool = False):
        if not self.ui_manager:
            logger.error("process_command: UIManager not initialized.")
            return
        # shell_engine_instance is now 'self' in this method
        # if not self: logger.error("process_command: ShellEngine not initialized."); return # Defensive check, 'self' is always true

        append_output_func = self.ui_manager.append_output
        confirmation_result = None

        # AI Command Confirmation Flow (handled by UIManager)
        if is_ai_generated and not forced_category:
            logger.info(f"AI generated command '{command_str_original}'. Initiating confirmation flow via UIManager.")
            confirmation_result = await self.ui_manager.prompt_for_command_confirmation(
                command_str_original,
                original_user_input_for_display,
                # Pass the main normal handler which is the submit_user_input for ShellEngine
                # This needs to be a reference to the main normal_input_accept_handler in main.py,
                # which will eventually call ShellEngine.submit_user_input.
                # Since UIManager calls a ref, we need to pass the original ref from main.py
                self.main_restore_normal_input_ref # This is a reference to main's restore_normal_input_handler
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
                self.category_manager_module.add_command_to_category(command_str_original, chosen_category_from_confirmation) # Update call
                forced_category = chosen_category_from_confirmation
            elif action == 'execute':
                append_output_func(f"✅ User confirmed execution of: {confirmed_command}", style_class='success')
                command_str_original = confirmed_command
            elif action == 'cancel':
                append_output_func(f"❌ Execution of '{command_str_original}' cancelled.", style_class='info')
                logger.info(f"User cancelled execution of AI command: {command_str_original}")
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref() # Update call
                return
            else: # Includes None if future was cancelled or unexpected action
                if action is not None : # Only log error if action was something unexpected, not just None from cancellation
                    append_output_func(f"Internal error or unexpected action in confirmation flow ({action}). Aborting.", style_class='error')
                    logger.error(f"Internal error in confirmation flow. Action: {action}")
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref() # Update call
                return

        category = forced_category
        command_for_classification = command_str_original
        command_to_be_added_if_new = command_for_classification

        # Command Categorization Flow (if not forced and unknown)
        if not category:
            logger.debug(f"process_command: Classifying command_for_classification: '{command_for_classification}' (is_ai_generated: {is_ai_generated})")
            category = self.category_manager_module.classify_command(command_for_classification) # Update call
            logger.debug(f"process_command: classify_command returned: '{category}' for command '{command_for_classification}'")

            if category == self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL: # Update call
                logger.info(f"Command '{command_for_classification}' uncategorized. Starting interactive flow via UIManager.")
                categorization_result = await self.ui_manager.start_categorization_flow(
                    command_for_classification,
                    ai_raw_candidate,
                    original_direct_input_if_different
                )

                action_cat = categorization_result.get('action')
                if action_cat == 'cancel_execution':
                    append_output_func(f"Execution of '{command_for_classification}' cancelled.", style_class='info')
                    logger.info(f"Execution of '{command_for_classification}' cancelled by user during categorization.")
                    return
                elif action_cat == 'categorize_and_execute':
                    command_to_be_added_if_new = categorization_result['command']
                    chosen_cat_for_json = categorization_result['category']
                    self.category_manager_module.add_command_to_category(command_to_be_added_if_new, chosen_cat_for_json) # Update call
                    category = chosen_cat_for_json
                    logger.info(f"Command '{command_to_be_added_if_new}' categorized as '{category}'.")
                    if command_to_be_added_if_new != command_str_original:
                        logger.info(f"Using '{command_to_be_added_if_new}' for execution.")
                        command_str_original = command_to_be_added_if_new
                else: # Includes 'execute_as_default' or other outcomes
                    category = self.config['behavior']['default_category_for_unclassified']
                    append_output_func(f"Executing '{command_for_classification}' as default '{category}'.", style_class='info')
                    logger.info(f"Command '{command_for_classification}' executed with default category '{category}'.")

        # Expand, Sanitize, and Execute
        # These calls will use shell_engine_instance methods
        command_to_execute_expanded = self.expand_shell_variables(command_str_original)
        if command_str_original != command_to_execute_expanded:
            logger.info(f"Expanded command: '{command_to_execute_expanded}' (original: '{command_str_original}')")
            if command_to_execute_expanded != command_for_classification and command_to_execute_expanded != command_to_be_added_if_new:
                append_output_func(f"Expanded for execution: {command_to_execute_expanded}", style_class='info')

        command_to_execute_sanitized = self.sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
        if not command_to_execute_sanitized:
            append_output_func(f"Command '{command_to_execute_expanded}' blocked.", style_class='security-warning')
            logger.warning(f"Command '{command_to_execute_expanded}' blocked.")
            if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref() # Update call
            return

        logger.info(f"Final command: '{command_to_execute_sanitized}', Category: '{category}'")
        exec_message_prefix = "Executing"
        if forced_category:
            if confirmation_result and confirmation_result.get('action') == 'execute_and_categorize':
                exec_message_prefix = f"Executing (user categorized as {category})"
            else:
                exec_message_prefix = "Forced execution"

        append_output_func(f"▶️ {exec_message_prefix} ({category} - {self.category_manager_module.CATEGORY_DESCRIPTIONS.get(category, 'Unknown')}): {command_to_execute_sanitized}", style_class='executing') # Update call

        # execute_shell_command and execute_command_in_tmux will be shell_engine_instance methods
        if category == "simple":
            await self.execute_shell_command(command_to_execute_sanitized, original_user_input_for_display)
        else:
            await self.execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category)

        # Restore normal input if no other flow is active (UIManager might handle this more centrally later)
        if self.ui_manager and not self.ui_manager.categorization_flow_active and not self.ui_manager.confirmation_flow_active and not self.ui_manager.is_in_edit_mode:
            if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref() # Update call


    async def submit_user_input(self, user_input: str):
        """
        Processes a user's input, orchestrating AI validation, translation,
        categorization flows, and command execution.
        This is the main entry point for user commands to the ShellEngine.
        """
        if not self.ui_manager:
            logger.error("submit_user_input: UIManager not initialized.")
            return

        user_input_stripped = user_input.strip()
        logger.info(f"ShellEngine.submit_user_input received: '{user_input_stripped}'")
        if not user_input_stripped:
            return

        current_app_inst = self.ui_manager.get_app_instance()

        # `cd` command handling
        if user_input_stripped == "cd" or user_input_stripped.startswith("cd "):
            logger.info(f"ShellEngine handling 'cd' command directly: {user_input_stripped}")
            await self.handle_cd_command(user_input_stripped)
            return

        # AI query handling
        if user_input_stripped.startswith("/ai "):
            ollama_is_ready = await self.ollama_manager_module.is_ollama_server_running()
            if not ollama_is_ready:
                self.ui_manager.append_output("⚠️ Ollama service is not available.", style_class='warning')
                self.ui_manager.append_output("    Try '/ollama status' or '/ollama start'.", style_class='info')
                logger.warning("Attempted /ai command while Ollama service is not ready.")
                return

            human_query = user_input_stripped[len("/ai "):].strip()
            if not human_query:
                self.ui_manager.append_output("⚠️ AI query empty.", style_class='warning')
                return

            self.ui_manager.append_output(f"🤖 AI Query: {human_query}", style_class='ai-query')
            self.ui_manager.append_output(f"🧠 Thinking...", style_class='ai-thinking')
            if current_app_inst and current_app_inst.is_running:
                current_app_inst.invalidate()

            linux_command, ai_raw_candidate = await self.ai_handler_module.get_validated_ai_command(human_query, self.config, self.ui_manager.append_output, self.ui_manager.get_app_instance)
            if linux_command:
                self.ui_manager.append_output(f"🤖 AI Suggests (validated): {linux_command}", style_class='ai-response')
                await self.process_command(linux_command, f"/ai {human_query} -> {linux_command}", ai_raw_candidate, None, is_ai_generated=True)
            else:
                self.ui_manager.append_output("🤔 AI could not produce a validated command.", style_class='warning')
            return

        # /command subsystem handling
        if user_input_stripped.startswith("/command"):
            command_action = self.category_manager_module.handle_command_subsystem_input(user_input_stripped)
            if isinstance(command_action, dict) and command_action.get('action') == 'force_run':
                cmd_to_run = command_action['command']
                forced_cat = command_action['category']
                display_input = f"/command run {forced_cat} \"{cmd_to_run}\""
                self.ui_manager.append_output(f"⚡ Forcing execution of '{cmd_to_run}' as '{forced_cat}'...", style_class='info')
                await self.process_command(cmd_to_run, display_input, None, None, forced_category=forced_cat, is_ai_generated=False)
            return

        # Direct command processing
        logger.debug(f"submit_user_input: Classifying direct command: '{user_input_stripped}'")
        category = self.category_manager_module.classify_command(user_input_stripped)
        logger.debug(f"submit_user_input: classify_command returned: '{category}' for command '{user_input_stripped}'")

        if category != self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL:
            logger.debug(f"Direct input '{user_input_stripped}' is known: '{category}'.")
            await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
        else:
            logger.debug(f"Direct input '{user_input_stripped}' unknown. Validating with AI.")
            ollama_is_ready = await self.ollama_manager_module.is_ollama_server_running()
            if not ollama_is_ready:
                self.ui_manager.append_output(f"⚠️ Ollama service not available for validation.", style_class='warning')
                self.ui_manager.append_output(f"    Attempting direct categorization or try '/ollama status' or '/ollama start'.", style_class='info')
                logger.warning(f"Ollama service not ready. Skipping AI validation for '{user_input_stripped}'.")
                await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
                return

            self.ui_manager.append_output(f"🔎 Validating '{user_input_stripped}' with AI...", style_class='info')
            if current_app_inst and current_app_inst.is_running:
                current_app_inst.invalidate()
            is_cmd_ai_says = await self.ai_handler_module.is_valid_linux_command_according_to_ai(user_input_stripped, self.config)

            # Heuristic logic for phrase vs command (still in ShellEngine)
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
                self.ui_manager.append_output(f"✅ AI believes '{user_input_stripped}' is direct command. Categorizing.", style_class='success')
                logger.info(f"Validator AI confirmed '{user_input_stripped}' as command (not phrase).")
                await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
            else:
                log_msg = ""
                ui_msg = ""
                ui_style = 'ai-thinking'
                if is_cmd_ai_says is False:
                    log_msg = f"Validator AI suggests '{user_input_stripped}' not command."
                    ui_msg = f"💬 AI suggests '{user_input_stripped}' not direct command. Trying as NL query..."
                elif is_cmd_ai_says is True and user_input_looks_like_phrase:
                    log_msg = f"Validator AI confirmed '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."
                    ui_msg = f"💬 AI validated '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."
                else: # is_cmd_ai_says is None (inconclusive)
                    log_msg = f"Validator AI for '{user_input_stripped}' inconclusive."
                    ui_msg = f"⚠️ AI validation for '{user_input_stripped}' inconclusive. Trying as NL query..."
                    ui_style = 'warning'

                logger.info(f"{log_msg} Treating as natural language.")
                self.ui_manager.append_output(ui_msg, style_class=ui_style)
                if current_app_inst and current_app_inst.is_running:
                    current_app_inst.invalidate()

                ollama_is_ready_for_translation = await self.ollama_manager_module.is_ollama_server_running()
                if not ollama_is_ready_for_translation:
                    self.ui_manager.append_output("⚠️ Ollama service not available for translation.", style_class='warning')
                    self.ui_manager.append_output("    Try '/ollama status' or '/ollama start'.", style_class='info')
                    logger.warning("Ollama service not ready. Skipping NL translation.")
                    await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
                    return

                linux_command, ai_raw_candidate = await self.ai_handler_module.get_validated_ai_command(user_input_stripped, self.config, self.ui_manager.append_output, self.ui_manager.get_app_instance)
                if linux_command:
                    self.ui_manager.append_output(f"🤖 AI Translated & Validated to: {linux_command}", style_class='ai-response')
                    original_direct_for_prompt = user_input_stripped if linux_command != user_input_stripped else None
                    await self.process_command(linux_command, f"'{user_input_stripped}' -> {linux_command}", ai_raw_candidate, original_direct_for_prompt, is_ai_generated=True)
                else:
                    self.ui_manager.append_output(f"🤔 AI could not produce validated command for '{user_input_stripped}'. Trying original as direct command.", style_class='warning')
                    logger.info(f"Validated AI translation failed for '{user_input_stripped}'.")
                    await self.process_command(user_input_stripped, user_input_stripped, ai_raw_candidate, None, is_ai_generated=False)
