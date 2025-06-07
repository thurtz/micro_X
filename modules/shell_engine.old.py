# modules/shell_engine.py
import asyncio
import os
import shlex
import subprocess
import uuid
import re
import logging
# import time # No longer directly used in ShellEngine methods shown
import shutil
import sys
import hashlib
from typing import Optional

from modules.output_analyzer import is_tui_like_output
# These are passed as module references now, no direct import needed here for their functions
# from modules import ollama_manager
# from modules import category_manager
# from modules import ai_handler

logger = logging.getLogger(__name__)

class ShellEngine:
    def __init__(self, config, ui_manager,
                 category_manager_module=None,
                 ai_handler_module=None,
                 ollama_manager_module=None,
                 main_exit_app_ref=None,
                 main_restore_normal_input_ref=None, # For restoring UI after flows
                 main_normal_input_accept_handler_ref=None, # For normal input submission
                 is_developer_mode: bool = False,
                 git_context_manager_instance=None
                 ):
        """
        Initializes the ShellEngine.

        Args:
            config (dict): The application configuration.
            ui_manager (UIManager): An instance of the UIManager.
            category_manager_module: Reference to the category_manager module.
            ai_handler_module: Reference to the ai_handler module.
            ollama_manager_module: Reference to the ollama_manager module.
            main_exit_app_ref (callable): Callback to main.py's exit function.
            main_restore_normal_input_ref (callable): Callback to main.py's UI restoration function.
            main_normal_input_accept_handler_ref (callable): Callback to main.py's normal input processing function.
            is_developer_mode (bool): Flag indicating if developer mode is active.
            git_context_manager_instance (GitContextManager): Instance of GitContextManager.
        """
        self.config = config
        self.ui_manager = ui_manager
        self.category_manager_module = category_manager_module
        self.ai_handler_module = ai_handler_module
        self.ollama_manager_module = ollama_manager_module
        self.main_exit_app_ref = main_exit_app_ref
        self.main_restore_normal_input_ref = main_restore_normal_input_ref
        self.main_normal_input_accept_handler_ref = main_normal_input_accept_handler_ref # Store this

        self.is_developer_mode = is_developer_mode
        self.git_context_manager_instance = git_context_manager_instance

        self.current_directory = os.getcwd()
        
        module_file_path = os.path.abspath(__file__)
        modules_dir_path = os.path.dirname(module_file_path)
        self.PROJECT_ROOT = os.path.dirname(modules_dir_path)
        # A simple check for project root, can be made more robust
        if not (os.path.exists(os.path.join(self.PROJECT_ROOT, "main.py")) or \
                os.path.exists(os.path.join(self.PROJECT_ROOT, ".git"))):
            logger.warning(f"ShellEngine inferred PROJECT_ROOT as {self.PROJECT_ROOT}. If incorrect, pass explicitly or improve detection.")


        self.REQUIREMENTS_FILENAME = "requirements.txt"
        self.REQUIREMENTS_FILE_PATH = os.path.join(self.PROJECT_ROOT, self.REQUIREMENTS_FILENAME)
        self.UTILS_DIR_NAME = "utils"
        self.UTILS_DIR_PATH = os.path.join(self.PROJECT_ROOT, self.UTILS_DIR_NAME)

        logger.info(f"ShellEngine initialized. Developer Mode: {self.is_developer_mode}")
        if self.git_context_manager_instance:
            logger.info(f"GitContextManager instance received by ShellEngine.")
        if self.main_normal_input_accept_handler_ref:
            logger.info("ShellEngine received main_normal_input_accept_handler_ref.")
        else:
            logger.warning("ShellEngine did NOT receive main_normal_input_accept_handler_ref. Edit mode might not work correctly.")


    def expand_shell_variables(self, command_string: str) -> str:
        # Using a unique placeholder for $PWD to avoid issues if other variables contain 'PWD'
        pwd_placeholder = f"__MICRO_X_PWD_PLACEHOLDER_{uuid.uuid4().hex}__"
        # Replace $PWD and ${PWD} with the placeholder
        temp_command_string = re.sub(r'\$PWD(?![a-zA-Z0-9_])', pwd_placeholder, command_string)
        temp_command_string = re.sub(r'\$\{PWD\}', pwd_placeholder, temp_command_string)
        # Expand other environment variables
        expanded_string = os.path.expandvars(temp_command_string)
        # Replace the placeholder with the actual current directory
        expanded_string = expanded_string.replace(pwd_placeholder, self.current_directory)
        if command_string != expanded_string:
            logger.debug(f"Expanded shell variables: '{command_string}' -> '{expanded_string}' (PWD: '{self.current_directory}')")
        return expanded_string

    def sanitize_and_validate(self, command: str, original_input_for_log: str) -> Optional[str]:
        """
        Performs basic sanitization and validation of commands.
        Returns the command if safe, None if blocked.
        """
        # List of regex patterns for potentially dangerous commands
        dangerous_patterns = [
            r'\brm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/(?!(?:tmp|var/tmp)\b)\S*', # rm -rf / (but not /tmp or /var/tmp)
            r'\brm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\s*(?:$|\.\.?\s*$|\*(?:\s.*|$))', # rm -rf / or rm -f / or rm -f / .. etc.
            r'\bmkfs\b', # Formatting commands
            r'\bdd\b\s+if=/dev/random', # Writing random data with dd
            r'\bdd\b\s+if=/dev/zero',    # Writing zeros with dd
            r'\b(shutdown|reboot|halt|poweroff)\b', # System shutdown/reboot commands
            r'>\s*/dev/sd[a-z]+', # Redirecting output to a raw disk device
            r':\(\)\{:\|:&};:', # Fork bomb
            r'\b(wget|curl)\s+.*\s*\|\s*(sh|bash|python|perl)\b' # Downloading and piping to a shell/interpreter
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                logger.warning(f"DANGEROUS command blocked (matched pattern '{pattern}'): '{command}' (original input: '{original_input_for_log}')")
                self.ui_manager.append_output(f"🛡️ Command blocked for security: {command}", style_class='security-critical')
                return None
        return command

    async def handle_cd_command(self, full_cd_command: str):
        """Handles the 'cd' command to change the current directory."""
        if not self.ui_manager:
            logger.error("ShellEngine.handle_cd_command: UIManager not initialized.")
            return
        append_output_func = self.ui_manager.append_output
        try:
            parts = full_cd_command.split(" ", 1)
            target_dir_str = parts[1].strip() if len(parts) > 1 else "~"
            
            # Expand environment variables and ~
            expanded_dir_arg = os.path.expanduser(os.path.expandvars(target_dir_str))
            
            # Construct absolute path
            if os.path.isabs(expanded_dir_arg):
                new_dir_abs = expanded_dir_arg
            else:
                new_dir_abs = os.path.abspath(os.path.join(self.current_directory, expanded_dir_arg))

            if os.path.isdir(new_dir_abs):
                self.current_directory = new_dir_abs
                self.ui_manager.update_input_prompt(self.current_directory) # Update UI prompt
                append_output_func(f"📂 Changed directory to: {self.current_directory}", style_class='info')
                logger.info(f"Directory changed to: {self.current_directory}")
            else:
                append_output_func(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.", style_class='error')
                logger.warning(f"Failed cd to '{new_dir_abs}'. Target '{target_dir_str}' does not exist or is not a directory.")
        except Exception as e:
            append_output_func(f"❌ Error processing 'cd' command: {e}", style_class='error')
            logger.exception(f"Error in handle_cd_command for '{full_cd_command}'")
        finally:
            # Ensure normal input mode is restored if it was changed by a flow
            if self.main_restore_normal_input_ref:
                self.main_restore_normal_input_ref()


    async def execute_shell_command(self, command_to_execute: str, original_user_input_display: str):
        """Executes a simple shell command directly."""
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
            if not stdout and not stderr and process.returncode == 0: # No output but success
                append_output_func(f"{output_prefix}(No output)", style_class='info')
            
            if process.returncode != 0:
                logger.warning(f"Command '{command_to_execute}' exited with code {process.returncode}")
                if not stderr: # If no stderr, still indicate non-zero exit
                    append_output_func(f"⚠️ Command '{original_user_input_display}' exited with code {process.returncode}.", style_class='warning')

        except FileNotFoundError: # If shell itself or command is not found
            append_output_func(f"❌ Shell (bash) or command not found for: {command_to_execute}", style_class='error')
            logger.error(f"Shell (bash) or command not found for: {command_to_execute}")
        except Exception as e:
            append_output_func(f"❌ Error executing '{command_to_execute}': {e}", style_class='error')
            logger.exception(f"Error executing shell command: {e}")

    async def execute_command_in_tmux(self, command_to_execute: str, original_user_input_display: str, category: str):
        """Executes a command in a new tmux window, based on category."""
        if not self.ui_manager:
            logger.error("ShellEngine.execute_command_in_tmux: UIManager not available.")
            return
        append_output_func = self.ui_manager.append_output
        logger.info(f"Executing tmux command ({category}): '{command_to_execute}' in '{self.current_directory}'")
        try:
            unique_id = str(uuid.uuid4())[:8] # For unique window/log names
            window_name = f"micro_x_{unique_id}"

            if shutil.which("tmux") is None:
                append_output_func("❌ Error: tmux not found. Cannot execute command in tmux.", style_class='error')
                logger.error("tmux not found for tmux execution.")
                return

            # Get configuration values with defaults
            tmux_poll_timeout = self.config.get('timeouts', {}).get('tmux_poll_seconds', 300)
            tmux_sleep_after = self.config.get('timeouts', {}).get('tmux_semi_interactive_sleep_seconds', 1)
            tmux_log_base = self.config.get('paths', {}).get('tmux_log_base_path', '/tmp')


            if category == "semi_interactive":
                os.makedirs(tmux_log_base, exist_ok=True)
                log_path = os.path.join(tmux_log_base, f"micro_x_output_{unique_id}.log")
                
                # Properly escape the command for execution within bash -c '...'
                # This handles single quotes within command_to_execute by replacing ' with '\'"'"'
                replacement_for_single_quote = "'\"'\"'" 
                escaped_command_str = command_to_execute.replace("'", replacement_for_single_quote)
                
                # Wrapped command: execute original, tee output to log, then sleep briefly
                wrapped_command = f"bash -c '{escaped_command_str}' |& tee {shlex.quote(log_path)}; sleep {tmux_sleep_after}"
                
                tmux_cmd_list_launch = ["tmux", "new-window", "-n", window_name, wrapped_command]
                logger.info(f"Launching semi_interactive tmux: {' '.join(tmux_cmd_list_launch)} (log: {log_path})")

                process_launch = await asyncio.create_subprocess_exec(
                    *tmux_cmd_list_launch, cwd=self.current_directory,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout_launch, stderr_launch = await process_launch.communicate()

                if process_launch.returncode != 0:
                    err_msg = stderr_launch.decode(errors='replace').strip() if stderr_launch else "Unknown tmux error"
                    append_output_func(f"❌ Error launching semi-interactive tmux session '{window_name}': {err_msg}", style_class='error')
                    logger.error(f"Failed to launch semi-interactive tmux: {err_msg}")
                    return

                append_output_func(f"⚡ Launched semi-interactive command in tmux (window: {window_name}). Waiting for output (max {tmux_poll_timeout}s)...", style_class='info')
                if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()
                
                start_time = asyncio.get_event_loop().time()
                output_captured_from_log = False
                window_closed_or_cmd_done = False

                while asyncio.get_event_loop().time() - start_time < tmux_poll_timeout:
                    await asyncio.sleep(1) # Poll every second
                    try:
                        # Check if the tmux window still exists
                        check_proc = await asyncio.create_subprocess_exec(
                            "tmux", "list-windows", "-F", "#{window_name}",
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        stdout_check, _ = await check_proc.communicate()
                        if window_name not in stdout_check.decode(errors='replace'):
                            logger.info(f"Tmux window '{window_name}' for semi-interactive command closed or finished.")
                            window_closed_or_cmd_done = True; break
                    except Exception as tmux_err:
                        logger.warning(f"Error checking tmux windows for '{window_name}': {tmux_err}")
                        window_closed_or_cmd_done = True; break # Assume closed on error

                if not window_closed_or_cmd_done: # Timed out
                    append_output_func(f"⚠️ Tmux window '{window_name}' poll timed out. Output might be incomplete or window still running.", style_class='warning')
                    logger.warning(f"Tmux poll for '{window_name}' timed out.")

                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f: output_content = f.read().strip()
                        
                        # Get TUI detection thresholds from config
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
                        try: os.remove(log_path)
                        except OSError as e_del: logger.error(f"Error deleting tmux log {log_path}: {e_del}")
                elif window_closed_or_cmd_done: # Window closed, no log file found
                        append_output_func(f"Output from '{original_user_input_display}': (Tmux window closed, no log found)", style_class='info')

                if not output_captured_from_log and not window_closed_or_cmd_done: # Timeout and no log
                    append_output_func(f"Output from '{original_user_input_display}': (Tmux window may still be running or timed out without output)", style_class='warning')

            else: # "interactive_tui"
                tmux_cmd_list = ["tmux", "new-window", "-n", window_name, command_to_execute]
                logger.info(f"Launching interactive_tui tmux: {' '.join(tmux_cmd_list)}")
                append_output_func(f"⚡ Launching interactive command in tmux (window: {window_name}). micro_X will wait for it to complete or be detached.", style_class='info')
                if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()

                # For interactive_tui, we run tmux in the foreground of this logic block
                # but it's still async from the main UI loop's perspective.
                process = await asyncio.to_thread(
                    subprocess.run, tmux_cmd_list, cwd=self.current_directory, check=False
                )
                if process.returncode == 0:
                    append_output_func(f"✅ Interactive tmux session for '{original_user_input_display}' ended.", style_class='success')
                else:
                    err_msg = f"exited with code {process.returncode}"
                    append_output_func(f"❌ Error or non-zero exit in tmux session '{window_name}': {err_msg}", style_class='error')
                    logger.error(f"Error reported by tmux run for cmd '{command_to_execute}': {err_msg}")

        except FileNotFoundError: # If tmux itself is not found
            append_output_func("❌ Error: tmux not found.", style_class='error')
            logger.error("tmux not found during tmux interaction.")
        except subprocess.CalledProcessError as e: # For check=True errors if used
            append_output_func(f"❌ Error interacting with tmux: {e.stderr or e}", style_class='error')
            logger.exception(f"CalledProcessError during tmux interaction: {e}")
        except Exception as e:
            append_output_func(f"❌ Unexpected error interacting with tmux: {e}", style_class='error')
            logger.exception(f"Unexpected error during tmux interaction: {e}")

    def _get_file_hash(self, filepath):
        """Calculates SHA256 hash of a file."""
        if not os.path.exists(filepath): return None
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192): # Read in chunks
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {filepath}: {e}", exc_info=True)
            return None


    async def _handle_update_command(self):
        """Handles the /update command to pull changes from git."""
        if not self.ui_manager: logger.error("handle_update_command: UIManager not initialized."); return
        self.ui_manager.append_output("🔄 Checking for updates...", style_class='info')
        logger.info("Update command received.")
        current_app_inst = self.ui_manager.get_app_instance()
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

        if not shutil.which("git"):
            self.ui_manager.append_output("❌ Update failed: 'git' not found in PATH.", style_class='error')
            logger.error("Update failed: git not found."); return

        original_req_hash = self._get_file_hash(self.REQUIREMENTS_FILE_PATH)
        requirements_changed = False
        try:
            # Get current branch
            branch_process_result = await asyncio.to_thread(subprocess.run, 
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                cwd=self.PROJECT_ROOT, capture_output=True, text=True, check=True, errors='replace'
            )
            current_branch = branch_process_result.stdout.strip()
            self.ui_manager.append_output(f"ℹ️ On branch: '{current_branch}'. Fetching updates from 'origin/{current_branch}'...", style_class='info')
            logger.info(f"Current git branch: {current_branch}")
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

            # Pull changes
            pull_process_result = await asyncio.to_thread(subprocess.run, 
                ['git', 'pull', 'origin', current_branch], 
                cwd=self.PROJECT_ROOT, capture_output=True, text=True, errors='replace' # check=False to inspect output
            )
            if pull_process_result.returncode == 0:
                self.ui_manager.append_output(f"✅ Git pull successful.\nOutput:\n{pull_process_result.stdout.strip()}", style_class='success')
                logger.info(f"Git pull output: {pull_process_result.stdout.strip()}")
                if "Already up to date." in pull_process_result.stdout:
                    self.ui_manager.append_output("✅ micro_X is up to date.", style_class='success')
                else: # Changes were pulled
                    self.ui_manager.append_output("✅ Updates downloaded.", style_class='success')
                    new_req_hash = self._get_file_hash(self.REQUIREMENTS_FILE_PATH)
                    if original_req_hash != new_req_hash:
                        requirements_changed = True
                        self.ui_manager.append_output("⚠️ requirements.txt changed.", style_class='warning')
                        logger.info("requirements.txt changed.")
                    self.ui_manager.append_output("💡 Restart micro_X for changes to take effect.", style_class='info')
                    if requirements_changed:
                        self.ui_manager.append_output(f"💡 After restart, consider updating dependencies if not handled automatically:\n  cd \"{self.PROJECT_ROOT}\"\n  source .venv/bin/activate\n  pip install -r {self.REQUIREMENTS_FILENAME}", style_class='info')
            else:
                self.ui_manager.append_output(f"❌ Git pull failed.\nError:\n{pull_process_result.stderr.strip()}", style_class='error')
                logger.error(f"Git pull failed. Stderr: {pull_process_result.stderr.strip()}")
        except subprocess.CalledProcessError as e:
            self.ui_manager.append_output(f"❌ Update failed: git error during branch detection.\n{e.stderr}", style_class='error')
            logger.error(f"Update git error (branch detection): {e}", exc_info=True)
        except FileNotFoundError: # Should be caught by shutil.which earlier
            self.ui_manager.append_output("❌ Update failed: 'git' command not found.", style_class='error')
            logger.error("Update failed: git not found (unexpected).")
        except Exception as e:
            self.ui_manager.append_output(f"❌ Unexpected error during update: {e}", style_class='error')
            logger.error(f"Unexpected update error: {e}", exc_info=True)
        finally:
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()


    def _display_general_help(self):
        """Displays the general help message in the UI."""
        if not self.ui_manager: logger.error("display_general_help: UIManager not initialized."); return
        help_text_styled = [
            ('class:help-title', "micro_X AI-Enhanced Shell - Help\n\n"),
            ('class:help-text', "Welcome to micro_X! An intelligent shell that blends traditional command execution with AI capabilities.\n"),
            ('class:help-header', "\nAvailable Commands:\n"),
            ('class:help-command', "  /ai <query>            "), ('class:help-description', "- Translate natural language <query> into a Linux command.\n"),
            ('class:help-example', "                           Example: /ai list all text files in current folder\n"),
            ('class:help-command', "  /command <subcommand>  "), ('class:help-description', "- Manage command categorizations (simple, semi_interactive, interactive_tui).\n"),
            ('class:help-example', "                           Type '/command help' for detailed options.\n"),
            ('class:help-command', "  /ollama <subcommand>   "), ('class:help-description', "- Manage the Ollama service (start, stop, restart, status).\n"),
            ('class:help-example', "                           Type '/ollama help' for detailed options.\n"),
            ('class:help-command', "  /utils <script> [args] "), ('class:help-description', "- Run a utility script from the 'utils' directory.\n"),
            ('class:help-example', "                           Type '/utils list' or '/utils <script_name> help' for details.\n"), # Updated
            ('class:help-command', "  /update                "), ('class:help-description', "- Check for and download updates for micro_X from its repository.\n"),
            ('class:help-command', "  /help                  "), ('class:help-description', "- Display this help message.\n"),
            ('class:help-command', "  exit | quit            "), ('class:help-description', "- Exit the micro_X shell.\n"),
            ('class:help-header', "\nDirect Commands:\n"),
            ('class:help-text', "  You can type standard Linux commands directly (e.g., 'ls -l', 'cd my_folder').\n"),
            ('class:help-text', "  Unknown commands will trigger an interactive categorization flow.\n"),
            ('class:help-text', "  AI-generated commands will prompt for confirmation (with categorization options) before execution.\n"),
            ('class:help-header', "\nKeybindings:\n"),
            ('class:help-text', "  Common keybindings are displayed at the bottom of the screen.\n"),
            ('class:help-text', "  Ctrl+C / Ctrl+D: Exit micro_X or cancel current categorization/confirmation/edit.\n"),
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
        """Displays help for the /ollama command."""
        if not self.ui_manager: logger.error("display_ollama_help: UIManager not initialized."); return
        help_text = [
            ("class:help-title", "Ollama Service Management - Help\n"),
            ("class:help-text", "Use these commands to manage the Ollama service used by micro_X.\n"),
            ("class:help-header", "\nAvailable /ollama Subcommands:\n"),
            ("class:help-command", "  /ollama start        "), ("class:help-description", "- Attempts to start the managed Ollama service if not already running.\n"),
            ("class:help-command", "  /ollama stop         "), ("class:help-description", "- Attempts to stop the managed Ollama service.\n"),
            ("class:help-command", "  /ollama restart      "), ("class:help-description", "- Attempts to restart the managed Ollama service.\n"), # Corrected quote here
            ("class:help-command", "  /ollama status       "), ("class:help-description", "- Shows the current status of the Ollama service and managed session.\n"),
            ("class:help-command", "  /ollama help         "), ("class:help-description", "- Displays this help message.\n"),
            ("class:help-text", "\nNote: These commands primarily interact with an Ollama instance managed by micro_X in a tmux session. ")
        ]
        help_output_string = "".join([text for _, text in help_text])
        self.ui_manager.append_output(help_output_string, style_class='help-base')
        logger.info("Displayed Ollama command help.")

    async def _handle_utils_command_async(self, full_command_str: str):
        """Handles the /utils command to run scripts from the utils directory."""
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
        
        utils_help_message = "ℹ️ Usage: /utils <script_name> [args... | help | -h | --help] | list"
        if len(parts) < 2:
            self.ui_manager.append_output(utils_help_message, style_class='info')
            logger.debug("Insufficient arguments for /utils command.")
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
        
        subcommand_or_script_name = parts[1]
        
        if subcommand_or_script_name.lower() == "list":
            try:
                if not os.path.exists(self.UTILS_DIR_PATH) or not os.path.isdir(self.UTILS_DIR_PATH):
                    self.ui_manager.append_output(f"❌ Utility directory '{self.UTILS_DIR_NAME}' not found at '{self.UTILS_DIR_PATH}'.", style_class='error'); logger.error(f"Utility directory not found: {self.UTILS_DIR_PATH}")
                    if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
                available_scripts = [f[:-3] for f in os.listdir(self.UTILS_DIR_PATH) if os.path.isfile(os.path.join(self.UTILS_DIR_PATH, f)) and f.endswith(".py") and f != "__init__.py"]
                if available_scripts:
                    self.ui_manager.append_output("Available utility scripts (run with /utils <script_name> [args... | help]):", style_class='info')
                    for script_name_no_ext in sorted(available_scripts): self.ui_manager.append_output(f"  - {script_name_no_ext}", style_class='info')
                else: self.ui_manager.append_output(f"No executable Python utility scripts found in '{self.UTILS_DIR_NAME}'.", style_class='info')
                logger.info(f"Listed utils scripts: {available_scripts}")
            except Exception as e: self.ui_manager.append_output(f"❌ Error listing utility scripts: {e}", style_class='error'); logger.error(f"Error listing utility scripts: {e}", exc_info=True)
            finally:
                if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
        
        # If not 'list', then subcommand_or_script_name is treated as a script name
        script_name_no_ext = subcommand_or_script_name
        script_filename = f"{script_name_no_ext}.py"
        script_path = os.path.join(self.UTILS_DIR_PATH, script_filename)

        if not os.path.isfile(script_path):
            self.ui_manager.append_output(f"❌ Utility script not found: {script_filename} in '{self.UTILS_DIR_NAME}' directory.", style_class='error'); logger.warning(f"Utility script not found: {script_path}")
            self.ui_manager.append_output(utils_help_message, style_class='info')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
        
        args_for_script = parts[2:]
        command_to_execute_list = [sys.executable, script_path]
        
        # --- MODIFICATION START: Add --branch argument for config_manager ---
        if script_name_no_ext == "config_manager" and self.git_context_manager_instance:
            current_branch = await self.git_context_manager_instance.get_current_branch()
            if current_branch:
                command_to_execute_list.extend(["--branch", current_branch])
            else:
                # Fallback if branch cannot be determined, though config_manager.py has its own default
                logger.warning("Could not determine current branch for config_manager utility.")
                command_to_execute_list.extend(["--branch", "unknown"]) # Or let config_manager.py use its default
        # --- MODIFICATION END ---
        
        is_help_request = False
        if args_for_script and args_for_script[0].lower() in ["help", "-h", "--help"]:
            is_help_request = True
            command_to_execute_list.append("--help")
        else:
            command_to_execute_list.extend(args_for_script)

        command_str_for_display = f"{sys.executable} {script_path} {' '.join(args_for_script if not is_help_request else ['--help'])}"
        
        if is_help_request:
            self.ui_manager.append_output(f"📜 Requesting help for utility: {script_name_no_ext}", style_class='info')
        else:
            self.ui_manager.append_output(f"🚀 Executing utility: {command_str_for_display}\n    (Working directory: {self.PROJECT_ROOT})", style_class='info')
        
        logger.info(f"Executing utility script: {command_to_execute_list} with cwd={self.PROJECT_ROOT}")
        if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()
        
        try:
            process = await asyncio.to_thread(subprocess.run, command_to_execute_list, capture_output=True, text=True, cwd=self.PROJECT_ROOT, check=False, errors='replace')
            output_prefix = f"Output from '{script_filename}':\n"; has_output = False
            if process.stdout: self.ui_manager.append_output(f"{output_prefix}{process.stdout.strip()}"); has_output = True
            if process.stderr: self.ui_manager.append_output(f"Stderr from '{script_filename}':\n{process.stderr.strip()}", style_class='warning'); has_output = True
            
            if not has_output and process.returncode == 0 and not is_help_request: 
                self.ui_manager.append_output(f"{output_prefix}(No output)", style_class='info')
            
            if process.returncode != 0 and not is_help_request: # Don't show error for non-zero exit if it was a help request (argparse exits > 0 for --help)
                self.ui_manager.append_output(f"⚠️ Utility '{script_filename}' exited with code {process.returncode}.", style_class='warning')
                logger.warning(f"Utility script '{script_path}' exited with code {process.returncode}. Args: {args_for_script}")
            elif not is_help_request and not process.stderr : # Only show success if not help and no stderr
                self.ui_manager.append_output(f"✅ Utility '{script_filename}' completed.", style_class='success')
            
            if not is_help_request: # Log completion only if not a help request
                logger.info(f"Utility script '{script_path}' completed with code {process.returncode}. Args: {args_for_script}")

        except FileNotFoundError: self.ui_manager.append_output(f"❌ Error: Python interpreter ('{sys.executable}') or script ('{script_filename}') not found.", style_class='error'); logger.error(f"FileNotFoundError executing utility: {command_to_execute_list}", exc_info=True)
        except Exception as e: self.ui_manager.append_output(f"❌ Unexpected error executing utility '{script_filename}': {e}", style_class='error'); logger.error(f"Error executing utility script '{script_path}': {e}", exc_info=True)
        finally:
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()


    async def _handle_ollama_command_async(self, user_input_parts: list):
        """Handles /ollama subcommands by calling the OllamaManager module."""
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
                # Optionally re-check status after a moment
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
        Handles built-in commands like /help, exit, /update, /utils, /ollama, and /command.
        Returns True if the command was handled, False otherwise.
        """
        user_input_stripped = user_input.strip()
        logger.info(f"ShellEngine.handle_built_in_command received: '{user_input_stripped}'")

        if user_input_stripped.lower() in {"/help", "help"}:
            self._display_general_help()
            return True
        elif user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
            self.ui_manager.append_output("Exiting micro_X Shell 🚪", style_class='info')
            logger.info("Exit command received from built-in handler.")
            if self.main_exit_app_ref: self.main_exit_app_ref()
            else: # Fallback if ref not set, though it should be
                app_instance = self.ui_manager.get_app_instance()
                if app_instance and app_instance.is_running: app_instance.exit()
            return True
        elif user_input_stripped.lower() == "/update":
            await self._handle_update_command()
            return True
        elif user_input_stripped.startswith("/utils"): # No space needed after /utils for this check
            await self._handle_utils_command_async(user_input_stripped)
            return True
        elif user_input_stripped.startswith("/ollama"): # No space needed after /ollama
            try:
                parts = user_input_stripped.split() # Simple split for /ollama commands
                await self._handle_ollama_command_async(parts)
            except Exception as e:
                self.ui_manager.append_output(f"❌ Error processing /ollama command: {e}", style_class='error')
                logger.error(f"Error in /ollama command '{user_input_stripped}': {e}", exc_info=True)
            return True
        elif user_input_stripped.startswith("/command"): # Check for /command prefix
            logger.info(f"Handling /command subsystem input: {user_input_stripped}")
            if not self.category_manager_module:
                logger.error("Category Manager module not available to handle /command.")
                self.ui_manager.append_output("❌ Internal Error: Command subsystem not available.", style_class='error')
                return True # Still handled, albeit with an error

            action_result = self.category_manager_module.handle_command_subsystem_input(user_input_stripped)
            
            if isinstance(action_result, dict) and action_result.get('action') == 'force_run':
                command_to_run = action_result['command']
                forced_category = action_result['category']
                logger.info(f"/command run: Forcing execution of '{command_to_run}' as '{forced_category}'")
                # process_command is async, and so is handle_built_in_command
                await self.process_command(
                    command_str_original=command_to_run,
                    original_user_input_for_display=user_input_stripped, # Use the full /command run ... string
                    forced_category=forced_category,
                    is_ai_generated=False # It's a user-directed force run
                )
            # If action_result is None, category_manager handled it (e.g., printed help/list, or error)
            # and no further ShellEngine action is needed beyond what category_manager did.
            return True # Command was handled by the /command subsystem
            
        return False # Not a built-in command handled here

    async def process_command(self, command_str_original: str, original_user_input_for_display: str,
                              ai_raw_candidate: Optional[str] = None,
                              original_direct_input_if_different: Optional[str] = None,
                              forced_category: Optional[str] = None,
                              is_ai_generated: bool = False):
        """
        Processes a command for execution, including categorization and AI confirmation if needed.
        """
        if not self.ui_manager: logger.error("process_command: UIManager not initialized."); return
        append_output_func = self.ui_manager.append_output
        confirmation_result = None

        try: # Add a try block to ensure finally is always reached for UI restoration
            if is_ai_generated and not forced_category:
                logger.info(f"AI generated command '{command_str_original}'. Initiating confirmation flow via UIManager.")
                if not self.main_normal_input_accept_handler_ref:
                    logger.error("CRITICAL: main_normal_input_accept_handler_ref is None in ShellEngine. Cannot proceed with AI command confirmation's modify option correctly.")
                    append_output_func("❌ Internal Error: Cannot handle command modification. Please restart.", style_class='error')
                    return # Exit this processing if critical handler is missing

                confirmation_result = await self.ui_manager.prompt_for_command_confirmation(
                    command_str_original,
                    original_user_input_for_display,
                    self.main_normal_input_accept_handler_ref 
                )
                action = confirmation_result.get('action')
                confirmed_command = confirmation_result.get('command', command_str_original) 
                chosen_category_from_confirmation = confirmation_result.get('category')

                if action == 'edit_mode_engaged':
                    append_output_func("⌨️ Command loaded into input field for editing. Press Enter to submit.", style_class='info')
                    return 

                if action == 'execute_and_categorize' and chosen_category_from_confirmation:
                    append_output_func(f"✅ User confirmed execution of: {confirmed_command} (as {chosen_category_from_confirmation})", style_class='success')
                    command_str_original = confirmed_command 
                    logger.info(f"User chose to run '{command_str_original}' and categorize as '{chosen_category_from_confirmation}'.")
                    self.category_manager_module.add_command_to_category(command_str_original, chosen_category_from_confirmation)
                    forced_category = chosen_category_from_confirmation
                elif action == 'execute':
                    append_output_func(f"✅ User confirmed execution of: {confirmed_command}", style_class='success')
                    command_str_original = confirmed_command 
                elif action == 'cancel':
                    append_output_func(f"❌ Execution of '{command_str_original}' cancelled.", style_class='info')
                    logger.info(f"User cancelled execution of AI command: {command_str_original}")
                    return
                else: 
                    if action is not None : 
                        append_output_func(f"Internal error or unexpected action in confirmation flow ({action}). Aborting.", style_class='error')
                        logger.error(f"Internal error in confirmation flow. Action: {action}")
                    return
            
            category = forced_category
            command_for_classification = command_str_original 
            command_to_be_added_if_new = command_for_classification 

            if not category: 
                logger.debug(f"process_command: Classifying command_for_classification: '{command_for_classification}' (is_ai_generated: {is_ai_generated})")
                category = self.category_manager_module.classify_command(command_for_classification)
                logger.debug(f"process_command: classify_command returned: '{category}' for command '{command_for_classification}'")

                if category == self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL:
                    logger.info(f"Command '{command_for_classification}' uncategorized. Starting interactive flow via UIManager.")
                    if not self.main_normal_input_accept_handler_ref: 
                        logger.error("CRITICAL: main_normal_input_accept_handler_ref is None in ShellEngine. Cannot proceed with categorization's modify option correctly.")
                        append_output_func("❌ Internal Error: Cannot handle command modification during categorization. Please restart.", style_class='error')
                        return

                    categorization_result = await self.ui_manager.start_categorization_flow(
                        command_for_classification, ai_raw_candidate, original_direct_input_if_different
                    )
                    action_cat = categorization_result.get('action')
                    if action_cat == 'cancel_execution':
                        append_output_func(f"Execution of '{command_for_classification}' cancelled.", style_class='info')
                        logger.info(f"Execution of '{command_for_classification}' cancelled by user during categorization.")
                        return
                    elif action_cat == 'categorize_and_execute':
                        command_to_be_added_if_new = categorization_result['command'] 
                        chosen_cat_for_json = categorization_result['category']
                        self.category_manager_module.add_command_to_category(command_to_be_added_if_new, chosen_cat_for_json)
                        category = chosen_cat_for_json
                        logger.info(f"Command '{command_to_be_added_if_new}' categorized as '{category}'.")
                        if command_to_be_added_if_new != command_str_original: 
                            logger.info(f"Using '{command_to_be_added_if_new}' for execution instead of original '{command_str_original}'.")
                            command_str_original = command_to_be_added_if_new 
                    else: 
                        category = self.config['behavior']['default_category_for_unclassified']
                        append_output_func(f"Executing '{command_for_classification}' as default '{category}'.", style_class='info')
                        logger.info(f"Command '{command_for_classification}' executed with default category '{category}'.")

            command_to_execute_expanded = self.expand_shell_variables(command_str_original)
            if command_str_original != command_to_execute_expanded:
                logger.info(f"Expanded command: '{command_to_execute_expanded}' (original: '{command_str_original}')")
                if command_to_execute_expanded != command_for_classification and command_to_execute_expanded != command_to_be_added_if_new:
                    append_output_func(f"Expanded for execution: {command_to_execute_expanded}", style_class='info')

            command_to_execute_sanitized = self.sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
            if not command_to_execute_sanitized:
                append_output_func(f"Command '{command_to_execute_expanded}' blocked.", style_class='security-warning')
                logger.warning(f"Command '{command_to_execute_expanded}' blocked by sanitizer.")
                return

            logger.info(f"Final command for execution: '{command_to_execute_sanitized}', Category: '{category}'")
            
            exec_message_prefix = "Executing"
            if forced_category:
                if confirmation_result and confirmation_result.get('action') == 'execute_and_categorize':
                    exec_message_prefix = f"Executing (user categorized as {category})"
                else: 
                    exec_message_prefix = "Forced execution"
            
            append_output_func(f"▶️ {exec_message_prefix} ({category} - {self.category_manager_module.CATEGORY_DESCRIPTIONS.get(category, 'Unknown')}): {command_to_execute_sanitized}", style_class='executing')

            if category == "simple":
                await self.execute_shell_command(command_to_execute_sanitized, original_user_input_for_display)
            else: 
                await self.execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category)
        
        finally:
            # This finally block ensures that normal input mode is restored if no other UI flow
            # (like categorization or confirmation, or edit mode) is currently active.
            # The explicit call in main.normal_input_accept_handler's _handle_input.finally
            # is more targeted for restoring after an edit mode submission.
            if self.ui_manager and \
               not self.ui_manager.categorization_flow_active and \
               not self.ui_manager.confirmation_flow_active and \
               not self.ui_manager.is_in_edit_mode: # Check if UIManager has already been reset
                if self.main_restore_normal_input_ref:
                    logger.debug("process_command.finally: Restoring normal input as no other flow is active.")
                    self.main_restore_normal_input_ref()


    async def submit_user_input(self, user_input: str, from_edit_mode: bool = False):
        """
        Primary entry point for processing user input from the shell.
        Distinguishes between /ai commands, direct commands, and /command subsystem.
        The 'from_edit_mode' flag indicates if the input came from the user editing an AI suggestion.
        """
        if not self.ui_manager: 
            logger.error("submit_user_input: UIManager not initialized."); return

        user_input_stripped = user_input.strip()
        logger.info(f"ShellEngine.submit_user_input received: '{user_input_stripped}', from_edit_mode: {from_edit_mode}")
        if not user_input_stripped: 
            if self.main_restore_normal_input_ref and from_edit_mode : self.main_restore_normal_input_ref() # Restore if empty from edit
            return

        current_app_inst = self.ui_manager.get_app_instance()

        # Handle /ai commands: These should always go through AI processing, even if from_edit_mode
        # if the user explicitly types /ai again.
        if user_input_stripped.startswith("/ai "):
            ollama_is_ready = await self.ollama_manager_module.is_ollama_server_running()
            if not ollama_is_ready:
                self.ui_manager.append_output("⚠️ Ollama service is not available.", style_class='warning')
                self.ui_manager.append_output("   Try '/ollama status' or '/ollama start'.", style_class='info')
                logger.warning("Attempted /ai command while Ollama service is not ready.")
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()
                return

            human_query = user_input_stripped[len("/ai "):].strip()
            if not human_query: 
                self.ui_manager.append_output("⚠️ AI query empty.", style_class='warning')
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()
                return
            
            self.ui_manager.append_output(f"🤖 AI Query: {human_query}", style_class='ai-query')
            self.ui_manager.append_output(f"🧠 Thinking...", style_class='ai-thinking')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

            linux_command, ai_raw_candidate = await self.ai_handler_module.get_validated_ai_command(
                human_query, self.config, self.ui_manager.append_output, self.ui_manager.get_app_instance
            )
            if linux_command:
                self.ui_manager.append_output(f"🤖 AI Suggests (validated): {linux_command}", style_class='ai-response')
                display_source = f"'/ai {human_query}' -> {linux_command}"
                await self.process_command(linux_command, display_source, ai_raw_candidate, None, is_ai_generated=True)
            else:
                self.ui_manager.append_output("🤔 AI could not produce a validated command.", style_class='warning')
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref() 
            return # End processing for /ai command

        # Built-in commands (like cd, /command, /help, etc.) are handled by main.normal_input_accept_handler
        # calling ShellEngine.handle_built_in_command *before* calling this submit_user_input method.
        # So, if we reach here, it means it was NOT a built-in command handled by that initial check
        # (unless it's /ai, which is explicitly handled above in this method).

        # If input is from edit mode (and not /ai, which was handled above), process it directly as a command.
        # Other built-ins would have been caught by handle_built_in_command before submit_user_input was called.
        if from_edit_mode:
            logger.info(f"Input '{user_input_stripped}' is from edit mode and not an /ai command. Processing directly.")
            await self.process_command(user_input_stripped, user_input_stripped, 
                                       ai_raw_candidate=None, 
                                       original_direct_input_if_different=None, 
                                       is_ai_generated=False) # is_ai_generated is False because user edited it.
            # UI restoration for edit mode is handled by main.normal_input_accept_handler's finally block.
            return

        # --- Logic for fresh input (not from_edit_mode, not /ai, not other built-in like /command, /help etc.) ---
        logger.debug(f"submit_user_input: Processing fresh direct command: '{user_input_stripped}'")
        
        # This input is not /ai, not from edit mode, and was not caught by handle_built_in_command.
        # This is where a direct OS command (e.g., "ls -l") or an unknown command/phrase would land.
        
        category = self.category_manager_module.classify_command(user_input_stripped)
        logger.debug(f"submit_user_input: classify_command returned: '{category}' for command '{user_input_stripped}'")

        if category != self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL:
            # Command is known and categorized (e.g., "ls -l" is in default_command_categories.json)
            logger.debug(f"Fresh direct input '{user_input_stripped}' is known: '{category}'.")
            await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
        else: # Command is unknown, try AI validation / NL translation
            logger.debug(f"Fresh direct input '{user_input_stripped}' unknown. Validating with AI.")
            ollama_is_ready = await self.ollama_manager_module.is_ollama_server_running()
            if not ollama_is_ready:
                self.ui_manager.append_output(f"⚠️ Ollama service not available for validation.", style_class='warning')
                self.ui_manager.append_output(f"   Attempting direct categorization or try '/ollama status' or '/ollama start'.", style_class='info')
                logger.warning(f"Ollama service not ready. Skipping AI validation for '{user_input_stripped}'.")
                # Proceed to process_command, which will trigger categorization flow for unknown command
                await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
                return

            self.ui_manager.append_output(f"🔎 Validating '{user_input_stripped}' with AI...", style_class='info')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()
            
            is_cmd_ai_says = await self.ai_handler_module.is_valid_linux_command_according_to_ai(user_input_stripped, self.config)
            
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
            if is_problematic_leading_dollar: user_input_looks_like_phrase = True
            elif not has_space: user_input_looks_like_phrase = False 
            elif is_command_syntax_present: user_input_looks_like_phrase = False
            else: user_input_looks_like_phrase = True 

            logger.debug(f"Input: '{user_input_stripped}', Validator AI: {is_cmd_ai_says}, Heuristic phrase: {user_input_looks_like_phrase}")

            if is_cmd_ai_says is True and not user_input_looks_like_phrase:
                self.ui_manager.append_output(f"✅ AI believes '{user_input_stripped}' is direct command. Categorizing.", style_class='success')
                logger.info(f"Validator AI confirmed '{user_input_stripped}' as command (not phrase).")
                await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
            else: 
                log_msg = ""; ui_msg = ""; ui_style = 'ai-thinking'
                if is_cmd_ai_says is False:
                    log_msg = f"Validator AI suggests '{user_input_stripped}' not command."; ui_msg = f"💬 AI suggests '{user_input_stripped}' not direct command. Trying as NL query..."
                elif is_cmd_ai_says is True and user_input_looks_like_phrase: 
                    log_msg = f"Validator AI confirmed '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."; ui_msg = f"💬 AI validated '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."
                else: 
                    log_msg = f"Validator AI for '{user_input_stripped}' inconclusive."; ui_msg = f"⚠️ AI validation for '{user_input_stripped}' inconclusive. Trying as NL query..."; ui_style = 'warning'
                
                logger.info(f"{log_msg} Treating as natural language.")
                self.ui_manager.append_output(ui_msg, style_class=ui_style)
                if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

                ollama_is_ready_for_translation = await self.ollama_manager_module.is_ollama_server_running() 
                if not ollama_is_ready_for_translation:
                    self.ui_manager.append_output("⚠️ Ollama service not available for translation.", style_class='warning')
                    self.ui_manager.append_output("   Try '/ollama status' or '/ollama start'.", style_class='info')
                    logger.warning("Ollama service not ready. Skipping NL translation.")
                    await self.process_command(user_input_stripped, user_input_stripped, None, None, is_ai_generated=False)
                    return

                linux_command, ai_raw_candidate = await self.ai_handler_module.get_validated_ai_command(
                    user_input_stripped, self.config, self.ui_manager.append_output, self.ui_manager.get_app_instance
                )
                if linux_command:
                    self.ui_manager.append_output(f"🤖 AI Translated & Validated to: {linux_command}", style_class='ai-response')
                    display_source = f"'{user_input_stripped}' -> {linux_command}"
                    original_direct_for_prompt = user_input_stripped if linux_command != user_input_stripped else None
                    await self.process_command(linux_command, display_source, ai_raw_candidate, original_direct_for_prompt, is_ai_generated=True)
                else:
                    self.ui_manager.append_output(f"🤔 AI could not produce validated command for '{user_input_stripped}'. Trying original as direct command.", style_class='warning')
                    logger.info(f"Validated AI translation failed for '{user_input_stripped}'.")
                    await self.process_command(user_input_stripped, user_input_stripped, ai_raw_candidate, None, is_ai_generated=False)
