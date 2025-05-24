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

# Imports from other project modules will be added as needed.
# For now, we might need ui_manager for append_output in sanitize_and_validate
# from .ui_manager import UIManager # This will be an instance passed in
from modules.output_analyzer import is_tui_like_output # Imported for tmux execution

logger = logging.getLogger(__name__)

class ShellEngine:
    def __init__(self, config, ui_manager, category_manager_module=None, ai_handler_module=None, main_module_globals=None):
        """
        Initializes the ShellEngine.

        Args:
            config (dict): The application configuration.
            ui_manager (UIManager): An instance of the UIManager.
            category_manager_module: Reference to the category_manager module or relevant functions.
            ai_handler_module: Reference to the ai_handler module or relevant functions.
            main_module_globals (dict, optional): A dictionary for accessing specific globals from main.py
                                                  if direct passing is complex (e.g., for callbacks like
                                                  normal_input_accept_handler, restore_normal_input_handler).
                                                  Ideally, these are passed more directly or handled via UIManager.
        """
        self.config = config
        self.ui_manager = ui_manager
        self.category_manager_module = category_manager_module # Store for later use
        self.ai_handler_module = ai_handler_module # Store for later use
        self.main_module_globals = main_module_globals if main_module_globals else {}

        self.current_directory = os.getcwd()
        # Other state attributes will be added as functions are moved.
        # For example, references to specific functions from category_manager or ai_handler
        # if not passing the whole module.

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
            if self.ui_manager.main_restore_normal_input_ref:
                self.ui_manager.main_restore_normal_input_ref()


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


            else:  # "interactive_tui"
                # For interactive_tui, we typically want to attach to the new window or let tmux handle it.
                # `tmux new-window` without -d will switch to the new window if run from within tmux.
                # If micro_X itself is run in tmux (via micro_X.sh), this is good.
                # If micro_X is run directly, `tmux new-window` will create it in the default server,
                # and the user might need to switch to it manually if their terminal doesn't auto-switch.
                tmux_cmd_list = ["tmux", "new-window", "-n", window_name, command_to_execute]
                logger.info(f"Launching interactive_tui tmux: {' '.join(tmux_cmd_list)}")
                append_output_func(f"⚡ Launching interactive command in tmux (window: {window_name}). micro_X will wait for it to complete or be detached.", style_class='info')
                if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()

                # For interactive TUI, we run and wait for it to complete.
                # This might block the asyncio event loop if not handled carefully.
                # Using subprocess.run in a thread is safer for blocking calls.
                process = await asyncio.to_thread(
                    subprocess.run,
                    tmux_cmd_list,
                    cwd=self.current_directory,
                    check=False # We'll check returncode manually
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
