# --- API DOCUMENTATION for modules/shell_engine.py ---
#
# **Purpose:** Acts as the core orchestrator for the shell, processing user
# input, managing state (like the current directory), and dispatching commands
# for execution based on their category.
#
# **Public Classes:**
#
# class ShellEngine:
#     """The main class for shell logic."""
#
#     def __init__(self, config, ui_manager, category_manager_module, ai_handler_module,
#                  ollama_manager_module, main_exit_app_ref, main_restore_normal_input_ref,
#                  main_normal_input_accept_handler_ref, is_developer_mode, git_context_manager_instance):
#         """
#         Initializes the ShellEngine with all necessary dependencies and callbacks.
#
#         Args:
#             config (dict): The application configuration.
#             ui_manager (UIManager): The instance of the UI manager.
#             category_manager_module (module): A reference to the category_manager module.
#             ai_handler_module (module): A reference to the ai_handler module.
#             ollama_manager_module (module): A reference to the ollama_manager module.
#             main_exit_app_ref (callable): Callback to the main application exit function.
#             main_restore_normal_input_ref (callable): Callback to restore the UI to normal mode.
#             main_normal_input_accept_handler_ref (callable): Callback for normal input submission.
#             is_developer_mode (bool): Flag indicating if developer mode is active.
#             git_context_manager_instance (GitContextManager): Instance for Git operations.
#         """
#
#     async def handle_built_in_command(self, user_input: str) -> bool:
#         """
#         Handles built-in commands like /help, /exit, /update, /utils, /ollama, and /command.
#
#         This is the first check for any user input.
#
#         Returns:
#             bool: True if the command was a built-in and was handled, False otherwise.
#         """
#
#     async def submit_user_input(self, user_input: str, from_edit_mode: bool = False):
#         """
#         The main entry point for processing all user input that isn't a simple built-in.
#
#         It orchestrates the flow:
#         1. Handles `/ai` queries by calling the AI handler.
#         2. Processes direct command input from the user.
#         3. For unknown commands, it uses the AI validator and may treat the input
#            as a natural language query.
#         4. Ultimately calls `process_command` to execute.
#
#         Args:
#             user_input (str): The raw text from the user's input field.
#             from_edit_mode (bool): True if the input is a resubmission after
#                                    the user chose to modify an AI suggestion.
#         """
#
# **Key Global Constants/Variables:**
#   (None intended for direct external use)
#
# --- END API DOCUMENTATION ---
import asyncio
import os
import shlex
import subprocess
import tempfile
import uuid
import re
import logging
import shutil
import sys
import hashlib
import json
from typing import Optional

from modules.output_analyzer import is_tui_like_output

logger = logging.getLogger(__name__)

def _get_nested_config(config_dict, key_path):
    """Safely retrieves a value from a nested dict using a dot-separated path."""
    keys = key_path.split('.')
    value = config_dict
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None # Key path not found
    return value

def _set_nested_config(config_dict, key_path, new_value):
    """Safely sets a value in a nested dict using a dot-separated path."""
    keys = key_path.split('.')
    d = config_dict
    for key in keys[:-1]:
        if key in d and not isinstance(d[key], dict):
            return False, f"Path conflict: '{key}' is not a dictionary."
        d = d.setdefault(key, {})

    d[keys[-1]] = new_value
    return True, None # Success

class ShellEngine:
    def __init__(self, config, ui_manager,
                 category_manager_module=None,
                 ai_handler_module=None,
                 ollama_manager_module=None,
                 main_exit_app_ref=None,
                 main_restore_normal_input_ref=None,
                 main_normal_input_accept_handler_ref=None,
                 is_developer_mode: bool = False,
                 git_context_manager_instance=None
                 ):
        """
        Initializes the ShellEngine.
        """
        self.config = config
        self.ui_manager = ui_manager
        self.category_manager_module = category_manager_module
        self.ai_handler_module = ai_handler_module
        self.ollama_manager_module = ollama_manager_module
        self.main_exit_app_ref = main_exit_app_ref
        self.main_restore_normal_input_ref = main_restore_normal_input_ref
        self.main_normal_input_accept_handler_ref = main_normal_input_accept_handler_ref

        self.is_developer_mode = is_developer_mode
        self.git_context_manager_instance = git_context_manager_instance

        self.current_directory = os.getcwd()

        module_file_path = os.path.abspath(__file__)
        modules_dir_path = os.path.dirname(module_file_path)
        self.PROJECT_ROOT = os.path.dirname(modules_dir_path)
        if not (os.path.exists(os.path.join(self.PROJECT_ROOT, "main.py")) or \
                os.path.exists(os.path.join(self.PROJECT_ROOT, ".git"))):
            logger.warning(f"ShellEngine inferred PROJECT_ROOT as {self.PROJECT_ROOT}.\nIf incorrect, pass explicitly or improve detection.")

        self.REQUIREMENTS_FILENAME = "requirements.txt"
        self.REQUIREMENTS_FILE_PATH = os.path.join(self.PROJECT_ROOT, self.REQUIREMENTS_FILENAME)
        self.UTILS_DIR_NAME = "utils"
        self.UTILS_DIR_PATH = os.path.join(self.PROJECT_ROOT, self.UTILS_DIR_NAME)
        self.USER_SCRIPTS_DIR_NAME = "user_scripts"
        self.USER_SCRIPTS_DIR_PATH = os.path.join(self.PROJECT_ROOT, self.USER_SCRIPTS_DIR_NAME)
        self.USER_CONFIG_FILE_PATH = os.path.join(self.PROJECT_ROOT, "config", "user_config.json")
        self.DEFAULT_ALIASES_FILE_PATH = os.path.join(self.PROJECT_ROOT, "config", "default_aliases.json")
        self.USER_ALIASES_FILE_PATH = os.path.join(self.PROJECT_ROOT, "config", "user_aliases.json")
        self.aliases = self._load_and_merge_aliases()


        logger.info(f"ShellEngine initialized. Developer Mode: {self.is_developer_mode}")
        if self.git_context_manager_instance:
            logger.info(f"GitContextManager instance received by ShellEngine.")
        if self.main_normal_input_accept_handler_ref:
            logger.info("ShellEngine received main_normal_input_accept_handler_ref.")
        else:
            logger.warning("ShellEngine did NOT receive main_normal_input_accept_handler_ref. Edit mode might not work correctly.")

    def _load_single_alias_file(self, file_path):
        """Loads a single alias file."""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading alias file {os.path.basename(file_path)}: {e}")
                self.ui_manager.append_output(f"⚠️ Could not load {os.path.basename(file_path)}: {e}", style_class='warning')
        return {}

    def _load_and_merge_aliases(self):
        """Loads default and user aliases, with user aliases taking precedence."""
        default_aliases = self._load_single_alias_file(self.DEFAULT_ALIASES_FILE_PATH)
        user_aliases = self._load_single_alias_file(self.USER_ALIASES_FILE_PATH)
        merged_aliases = {**default_aliases, **user_aliases}
        logger.info(f"Loaded {len(default_aliases)} default and {len(user_aliases)} user aliases, resulting in {len(merged_aliases)} total active aliases.")
        return merged_aliases

    def _reload_aliases(self):
        """Reloads aliases from the file, typically after the alias utility is run."""
        self.aliases = self._load_and_merge_aliases()
        logger.info("Aliases reloaded.")


    def expand_shell_variables(self, command_string: str) -> str:
        pwd_placeholder = f"__MICRO_X_PWD_PLACEHOLDER_{uuid.uuid4().hex}__"
        temp_command_string = re.sub(r'\$PWD(?![a-zA-Z0-9_])', pwd_placeholder, command_string)
        temp_command_string = re.sub(r'\$\{PWD\}', pwd_placeholder, temp_command_string)
        expanded_string = os.path.expandvars(temp_command_string)
        expanded_string = expanded_string.replace(pwd_placeholder, self.current_directory)
        if command_string != expanded_string:
            logger.debug(f"Expanded shell variables: '{command_string}' -> '{expanded_string}' (PWD: '{self.current_directory}')")
        return expanded_string

    def sanitize_and_validate(self, command: str, original_input_for_log: str) -> Optional[str]:
        """
        Performs basic sanitization and validation of commands.
        Returns the command if safe, None if blocked.
        """
        dangerous_patterns = self.config.get("security", {}).get("dangerous_patterns", [])
        for pattern in dangerous_patterns:
            try:
                if re.search(pattern, command):
                    logger.warning(f"DANGEROUS command blocked (matched pattern '{pattern}'): '{command}' (original input: '{original_input_for_log}')")
                    self.ui_manager.append_output(f"🛡️ Command blocked by security pattern: {command}", style_class='security-critical')
                    return None
            except re.error as e:
                logger.error(f"Invalid regex pattern in security config: '{pattern}'. Error: {e}")
                self.ui_manager.append_output(f"⚠️ Invalid security regex pattern in config: '{pattern}'.", style_class='warning')
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

            expanded_dir_arg = os.path.expanduser(os.path.expandvars(target_dir_str))

            if os.path.isabs(expanded_dir_arg):
                new_dir_abs = expanded_dir_arg
            else:
                new_dir_abs = os.path.abspath(os.path.join(self.current_directory, expanded_dir_arg))

            if os.path.isdir(new_dir_abs):
                self.current_directory = new_dir_abs
                self.ui_manager.update_input_prompt(self.current_directory)
                append_output_func(f"📂 Changed directory to: {self.current_directory}", style_class='info')
                logger.info(f"Directory changed to: {self.current_directory}")
            else:
                append_output_func(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.", style_class='error')
                logger.warning(f"Failed cd to '{new_dir_abs}'. Target '{target_dir_str}' does not exist or is not a directory.")
        except Exception as e:
            append_output_func(f"❌ Error processing 'cd' command: {e}", style_class='error')
            logger.exception(f"Error in handle_cd_command for '{full_cd_command}'")
        finally:
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

            show_verbose_prefix = command_to_execute.strip() != original_user_input_display.strip()

            # --- START OF CHANGE ---
            if not show_verbose_prefix:
                # For direct simple commands, always print the prompt line first.
                append_output_func(f"$ {original_user_input_display}", style_class='executing')

            if stdout:
                if show_verbose_prefix:
                    # For AI/aliased commands, use the descriptive prefix
                    append_output_func(f"Output from '{original_user_input_display}':\n{stdout.decode(errors='replace').strip()}")
                else:
                    # For direct commands, the prompt is already printed, so just print the output.
                    append_output_func(stdout.decode(errors='replace').strip())
            # --- END OF CHANGE ---

            if stderr:
                append_output_func(f"Stderr from '{original_user_input_display}':\n{stderr.decode(errors='replace').strip()}", style_class='warning')
            
            if not stdout and not stderr and process.returncode == 0:
                if show_verbose_prefix:
                    append_output_func(f"Output from '{original_user_input_display}': (No output)", style_class='info')
                # If not show_verbose_prefix, the prompt was already printed, and we do nothing else, which is correct.
            
            if process.returncode != 0:
                logger.warning(f"Command '{command_to_execute}' exited with code {process.returncode}")
                if not stderr:
                    append_output_func(f"⚠️ Command '{original_user_input_display}' exited with code {process.returncode}.", style_class='warning')

        except FileNotFoundError:
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
            unique_id = str(uuid.uuid4())[:8]
            window_name = f"micro_x_{unique_id}"

            if shutil.which("tmux") is None:
                append_output_func("❌ Error: tmux not found. Cannot execute command in tmux.", style_class='error')
                logger.error("tmux not found for tmux execution.")
                return

            tmux_poll_timeout = self.config.get('timeouts', {}).get('tmux_poll_seconds', 300)
            tmux_sleep_after = self.config.get('timeouts', {}).get('tmux_semi_interactive_sleep_seconds', 1)

            if category == "semi_interactive":
                with tempfile.NamedTemporaryFile(mode='w+', delete=True, encoding='utf-8', errors='ignore') as temp_log_file:
                    log_path = temp_log_file.name
                    logger.debug(f"Using platform-agnostic temporary file for tmux log: {log_path}")

                    # Use shlex.quote for robust command escaping
                    escaped_command_str = shlex.quote(command_to_execute)

                    # The command for tmux to run in a shell. It executes the user's command,
                    # tees stdout/stderr to a log, and sleeps briefly to ensure the pane is visible.
                    wrapped_command = f"bash -c {escaped_command_str} |& tee {shlex.quote(log_path)}; sleep {tmux_sleep_after}"
                    #wrapped_command = f"bash -c 'source ~/.bashrc && {command_to_execute}' |& tee {shlex.quote(log_path)}; sleep {tmux_sleep_after}"

                    tmux_cmd_list_launch = ["tmux", "new-window", "-n", window_name, wrapped_command]
                    logger.info(f"Launching semi_interactive tmux: {' '.join(tmux_cmd_list_launch)} (log: {log_path})")

                    process_launch = await asyncio.create_subprocess_exec(
                        *tmux_cmd_list_launch, cwd=self.current_directory,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    _, stderr_launch = await process_launch.communicate()

                    if process_launch.returncode != 0:
                        err_msg = stderr_launch.decode(errors='replace').strip() if stderr_launch else "Unknown tmux error"
                        append_output_func(f"❌ Error launching semi-interactive tmux session '{window_name}': {err_msg}", style_class='error')
                        logger.error(f"Failed to launch semi-interactive tmux: {err_msg}")
                        return

                    append_output_func(f"⚡ Launched semi-interactive command in tmux (window: {window_name}). Waiting for output (max {tmux_poll_timeout}s)...", style_class='info')
                    if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()

                    start_time = asyncio.get_event_loop().time()
                    window_closed_or_cmd_done = False

                    while asyncio.get_event_loop().time() - start_time < tmux_poll_timeout:
                        await asyncio.sleep(1)
                        try:
                            check_proc = await asyncio.create_subprocess_exec(
                                "tmux", "list-windows", "-F", "#{window_name}",
                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                            )
                            stdout_check, _ = await check_proc.communicate()
                            if window_name not in stdout_check.decode(errors='replace'):
                                logger.info(f"Tmux window '{window_name}' closed or finished.")
                                window_closed_or_cmd_done = True; break
                        except Exception as tmux_err:
                            logger.warning(f"Error checking tmux windows: {tmux_err}")
                            window_closed_or_cmd_done = True; break

                    if not window_closed_or_cmd_done:
                        append_output_func(f"⚠️ Tmux window '{window_name}' poll timed out. Output might be incomplete or window still running.", style_class='warning')
                        logger.warning(f"Tmux poll for '{window_name}' timed out.")

                    temp_log_file.seek(0)
                    output_content = temp_log_file.read().strip()

                    tui_line_threshold = self.config.get('behavior', {}).get('tui_detection_line_threshold_pct', 30.0)
                    tui_char_threshold = self.config.get('behavior', {}).get('tui_detection_char_threshold_pct', 3.0)

                    if output_content and is_tui_like_output(output_content, tui_line_threshold, tui_char_threshold):
                        logger.info(f"Output from '{original_user_input_display}' (semi-interactive) detected as TUI-like.")
                        suggestion_command = f'/command move "{command_to_execute}" interactive_tui'
                        append_output_func(f"Output from '{original_user_input_display}':\n[Semi-interactive TUI-like output not displayed directly.]\n💡 Tip: Try: {suggestion_command}", style_class='info')
                    elif output_content:
                        append_output_func(f"Output from '{original_user_input_display}':\n{output_content}")
                    elif window_closed_or_cmd_done:
                        append_output_func(f"Output from '{original_user_input_display}': (No output captured)", style_class='info')

            else: # "interactive_tui"
                # For interactive commands, wrap in 'bash -c' to handle complex commands consistently.
                tmux_cmd_list = ["tmux", "new-window", "-n", window_name, "bash", "-c", command_to_execute]
                #tmux_cmd_list = ["tmux", "new-window", "-n", window_name, "bash", "-c", f"source ~/.bashrc && {command_to_execute}"]
                logger.info(f"Launching interactive_tui tmux: {' '.join(shlex.quote(s) for s in tmux_cmd_list)}")
                append_output_func(f"⚡ Launching interactive command in tmux (window: {window_name}). micro_X will wait for it to complete or be detached.", style_class='info')
                if self.ui_manager.get_app_instance(): self.ui_manager.get_app_instance().invalidate()

                process = await asyncio.to_thread(
                    subprocess.run, tmux_cmd_list, cwd=self.current_directory, check=False
                )
                if process.returncode == 0:
                    append_output_func(f"✅ Interactive tmux session for '{original_user_input_display}' ended.", style_class='success')
                else:
                    err_msg = f"exited with code {process.returncode}"
                    append_output_func(f"❌ Error or non-zero exit in tmux session '{window_name}': {err_msg}", style_class='error')
                    logger.error(f"Error reported by tmux run for cmd '{command_to_execute}': {err_msg}")

        except FileNotFoundError:
            append_output_func("❌ Error: tmux not found.", style_class='error')
            logger.error("tmux not found during tmux interaction.")
        except subprocess.CalledProcessError as e:
            append_output_func(f"❌ Error interacting with tmux: {e.stderr or e}", style_class='error')
            logger.exception(f"CalledProcessError during tmux interaction: {e}")
        except Exception as e:
            append_output_func(f"❌ Unexpected error interacting with tmux: {e}", style_class='error')
            logger.exception(f"Unexpected error during tmux interaction: {e}")

    async def _handle_script_command_async(self, full_command_str: str, script_dir_path: str, script_dir_name: str, command_name: str):
        """Generic handler for executing scripts from a specified directory (e.g., utils or user_scripts)."""
        if not self.ui_manager:
            logger.error(f"Cannot handle /{command_name}: UIManager not initialized.")
            return

        logger.info(f"Handling /{command_name} command: {full_command_str}")

        try:
            parts = shlex.split(full_command_str)
        except ValueError as e:
            self.ui_manager.append_output(f"❌ Error parsing /{command_name} command: {e}", style_class='error')
            logger.warning(f"shlex error for /{command_name} '{full_command_str}': {e}")
            return

        help_message = f"ℹ️ Usage: /{command_name} <script_name> [args... | help | -h | --help] | list"
        if len(parts) < 2:
            self.ui_manager.append_output(help_message, style_class='info')
            return

        subcommand = parts[1]

        # --- UNIFIED LISTING LOGIC ---
        if subcommand.lower() == "list":
            # Always run the list_scripts.py utility from the utils directory
            list_script_path = os.path.join(self.UTILS_DIR_PATH, "list_scripts.py")
            if not os.path.isfile(list_script_path):
                self.ui_manager.append_output("❌ Error: The 'list_scripts.py' utility is missing.", style_class='error')
                return

            # Formulate the command to run the unified lister
            list_command_str = f"/utils list_scripts"
            # Re-enter the command handling logic with the new command
            await self._handle_utils_command_async(list_command_str)
            return
        # --- END UNIFIED LISTING LOGIC ---

        script_path = os.path.join(script_dir_path, f"{subcommand}.py")
        if not os.path.isfile(script_path):
            self.ui_manager.append_output(f"❌ Script not found: {subcommand}.py in '{script_dir_name}'.", style_class='error')
            return

        args_for_script = parts[2:]
        command_to_execute = [sys.executable, script_path] + args_for_script

        self.ui_manager.append_output(f"🚀 Executing script: {' '.join(command_to_execute)}", style_class='info')
        try:
            process = await asyncio.to_thread(
                subprocess.run, command_to_execute, capture_output=True, text=True, cwd=self.PROJECT_ROOT, check=False
            )
            if process.stdout:
                self.ui_manager.append_output(f"Output from '{subcommand}.py':\n{process.stdout.strip()}")
            if process.stderr:
                self.ui_manager.append_output(f"Stderr from '{subcommand}.py':\n{process.stderr.strip()}", style_class='warning')
            if process.returncode != 0:
                self.ui_manager.append_output(f"⚠️ Script '{subcommand}.py' exited with code {process.returncode}.", style_class='warning')
            else:
                self.ui_manager.append_output(f"✅ Script '{subcommand}.py' completed.", style_class='success')

            if subcommand == 'alias':
                self._reload_aliases()
        except Exception as e:
            self.ui_manager.append_output(f"❌ Failed to execute script: {e}", style_class='error')

    async def _handle_utils_command_async(self, full_command_str: str):
        await self._handle_script_command_async(full_command_str, self.UTILS_DIR_PATH, self.UTILS_DIR_NAME, "utils")

    async def _handle_user_script_command_async(self, full_command_str: str):
        await self._handle_script_command_async(full_command_str, self.USER_SCRIPTS_DIR_PATH, self.USER_SCRIPTS_DIR_NAME, "run")

    async def handle_built_in_command(self, user_input: str) -> bool:
        user_input_stripped = user_input.strip()

        # --- ALIAS EXPANSION ---
        try:
            input_parts = shlex.split(user_input_stripped)
            alias_name = input_parts[0] if input_parts else ""
            if alias_name in self.aliases:
                expanded_command = self.aliases[alias_name]
                remaining_args = input_parts[1:]
                # Simple append, for more complex logic (e.g., placeholders) this would need enhancement
                final_command = f"{expanded_command} {' '.join(shlex.quote(arg) for arg in remaining_args)}".strip()

                self.ui_manager.append_output(f"↪️ Alias expanded: '{alias_name}' -> '{final_command}'", style_class='info')
                user_input_stripped = final_command

                # --- FIX START: Immediate execution for categorized aliases ---
                # After expanding an alias, immediately check if the result is a known, categorized command.
                # If it is, we can execute it directly and bypass the "unknown command" logic (AI validation).
                category = self.category_manager_module.classify_command(final_command)
                if category != self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL:
                    logger.info(f"Alias '{alias_name}' expanded to categorized command '{final_command}'. Executing directly.")
                    # We use the original user input (the alias itself) for display purposes.
                    await self.process_command(final_command, user_input.strip())
                    return True # IMPORTANT: Return True to signify the command was fully handled.
                # --- FIX END ---

        except ValueError:
            # shlex failed, proceed with original input
            pass
        # --- END ALIAS EXPANSION ---

        logger.info(f"ShellEngine.handle_built_in_command received: '{user_input_stripped}'")
        if user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
            self.ui_manager.append_output("Exiting micro_X Shell 🚪", style_class='info')
            logger.info("Exit command received from built-in handler.")
            if self.main_exit_app_ref: self.main_exit_app_ref()
            else:
                app_instance = self.ui_manager.get_app_instance()
                if app_instance and app_instance.is_running: app_instance.exit()
            return True
        elif user_input_stripped.startswith("/utils"):
            await self._handle_utils_command_async(user_input_stripped); return True
        elif user_input_stripped.startswith("/run"):
            await self._handle_user_script_command_async(user_input_stripped); return True
        # --- REMOVED /update and /ollama direct handling ---
        return False

    async def process_command(self, command_str_original: str, original_user_input_for_display: str,
                              ai_raw_candidate: Optional[str] = None,
                              original_direct_input_if_different: Optional[str] = None,
                              forced_category: Optional[str] = None,
                              is_ai_generated: bool = False):
        if not self.ui_manager: logger.error("process_command: UIManager not initialized."); return
        append_output_func = self.ui_manager.append_output
        confirmation_result = None
        try:
            if is_ai_generated and not forced_category:
                confirmation_result = await self.ui_manager.prompt_for_command_confirmation(command_str_original, original_user_input_for_display, self.main_normal_input_accept_handler_ref)
                action = confirmation_result.get('action')
                if action == 'edit_mode_engaged': return
                elif action == 'execute_and_categorize':
                    command_str_original = confirmation_result.get('command', command_str_original)
                    forced_category = confirmation_result.get('category')
                    self.category_manager_module.add_command_to_category(command_str_original, forced_category)
                elif action == 'execute': command_str_original = confirmation_result.get('command', command_str_original)
                elif action == 'cancel': self.ui_manager.append_output(f"❌ Execution of '{command_str_original}' cancelled.", style_class='info'); return
                else: return

            category = forced_category or self.category_manager_module.classify_command(command_str_original)
            if category == self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL:
                categorization_result = await self.ui_manager.start_categorization_flow(command_str_original, ai_raw_candidate, original_direct_input_if_different)
                action_cat = categorization_result.get('action')
                if action_cat == 'cancel_execution':
                    append_output_func(f"Execution of '{command_str_original}' cancelled.", style_class='info'); return
                elif action_cat == 'categorize_and_execute':
                    command_str_original = categorization_result['command']
                    category = categorization_result['category']
                    self.category_manager_module.add_command_to_category(command_str_original, category)
                else: category = self.config['behavior']['default_category_for_unclassified']

            command_to_execute_expanded = self.expand_shell_variables(command_str_original)
            command_to_execute_sanitized = self.sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
            if not command_to_execute_sanitized: return

            # --- NEW: Caution Confirmation Step ---
            warn_on_commands = self.config.get("security", {}).get("warn_on_commands", [])
            command_base = command_to_execute_sanitized.split()[0]
            if command_base in warn_on_commands:
                caution_result = await self.ui_manager.prompt_for_caution_confirmation(command_to_execute_sanitized)
                if not caution_result.get('proceed', False):
                    self.ui_manager.append_output(f"🛡️ Execution of '{command_to_execute_sanitized}' cancelled by user.", style_class='info')
                    return
            # --- END: Caution Confirmation Step ---

            self.ui_manager.add_interaction_separator()

            exec_message_prefix = "Executing"
            if forced_category:
                if confirmation_result and confirmation_result.get('action') == 'execute_and_categorize':
                    exec_message_prefix = f"Executing (user categorized as {category})"
                else: exec_message_prefix = "Forced execution"

            # Conditionally display the "Executing" message to create a cleaner, shell-like output for simple, direct commands.
            is_direct_simple_command = (category == "simple" and not is_ai_generated and not forced_category)

            if not is_direct_simple_command:
                append_output_func(f"▶️ {exec_message_prefix} ({category} - {self.category_manager_module.CATEGORY_DESCRIPTIONS.get(category, 'Unknown')}): {command_to_execute_sanitized}", style_class='executing')

            if category == "simple": await self.execute_shell_command(command_to_execute_sanitized, original_user_input_for_display)
            else: await self.execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category)
        finally:
            if self.ui_manager and not self.ui_manager.categorization_flow_active and not self.ui_manager.confirmation_flow_active and not self.ui_manager.is_in_edit_mode:
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()

    async def submit_user_input(self, user_input: str, from_edit_mode: bool = False):
        if not self.ui_manager: logger.error("submit_user_input: UIManager not initialized."); return
        user_input_stripped = user_input.strip()
        if not user_input_stripped:
            if self.main_restore_normal_input_ref and from_edit_mode: self.main_restore_normal_input_ref()
            return

        current_app_inst = self.ui_manager.get_app_instance()
        if user_input_stripped.startswith("/ai "):
            if not await self.ollama_manager_module.is_ollama_server_running():
                self.ui_manager.append_output("⚠️ Ollama service is not available.", style_class='warning'); return
            human_query = user_input_stripped[len("/ai "):].strip()
            if not human_query: self.ui_manager.append_output("⚠️ AI query empty.", style_class='warning'); return
            self.ui_manager.append_output(f"🤖 AI Query: {human_query}", style_class='ai-query')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()
            linux_command, ai_raw_candidate = await self.ai_handler_module.get_validated_ai_command(human_query, self.config, self.ui_manager.append_output, self.ui_manager.get_app_instance)
            if linux_command: await self.process_command(linux_command, f"'/ai {human_query}'", ai_raw_candidate, None, is_ai_generated=True)
            else:
                self.ui_manager.append_output("🤔 AI could not produce a validated command.", style_class='warning')
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()
            return

        if from_edit_mode:
            await self.process_command(user_input_stripped, user_input_stripped); return

        category = self.category_manager_module.classify_command(user_input_stripped)
        if category != self.category_manager_module.UNKNOWN_CATEGORY_SENTINEL:
            await self.process_command(user_input_stripped, user_input_stripped)
        else:
            if not await self.ollama_manager_module.is_ollama_server_running():
                await self.process_command(user_input_stripped, user_input_stripped); return
            self.ui_manager.append_output(f"🔎 Validating '{user_input_stripped}' with AI...", style_class='info')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()
            is_cmd_ai_says = await self.ai_handler_module.is_valid_linux_command_according_to_ai(user_input_stripped, self.config)
            is_command_syntax_present = '--' in user_input_stripped or bool(re.search(r'(?:^|\s)-\w', user_input_stripped))
            if is_cmd_ai_says is True and not (' ' in user_input_stripped and not is_command_syntax_present):
                await self.process_command(user_input_stripped, user_input_stripped)
            else:
                self.ui_manager.append_output("Trying as NL query...", style_class='ai-thinking')
                linux_command, ai_raw_candidate = await self.ai_handler_module.get_validated_ai_command(user_input_stripped, self.config, self.ui_manager.append_output, self.ui_manager.get_app_instance)
                if linux_command:
                    await self.process_command(linux_command, f"'{user_input_stripped}'", ai_raw_candidate, user_input_stripped, is_ai_generated=True)
                else:
                    self.ui_manager.append_output("🤔 AI failed. Trying original as direct command.", style_class='warning')
                    await self.process_command(user_input_stripped, user_input_stripped, ai_raw_candidate)
