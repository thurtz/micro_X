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
            logger.warning(f"ShellEngine inferred PROJECT_ROOT as {self.PROJECT_ROOT}. If incorrect, pass explicitly or improve detection.")

        self.REQUIREMENTS_FILENAME = "requirements.txt"
        self.REQUIREMENTS_FILE_PATH = os.path.join(self.PROJECT_ROOT, self.REQUIREMENTS_FILENAME)
        self.UTILS_DIR_NAME = "utils"
        self.UTILS_DIR_PATH = os.path.join(self.PROJECT_ROOT, self.UTILS_DIR_NAME)
        self.USER_CONFIG_FILE_PATH = os.path.join(self.PROJECT_ROOT, "config", "user_config.json")

        logger.info(f"ShellEngine initialized. Developer Mode: {self.is_developer_mode}")
        if self.git_context_manager_instance:
            logger.info(f"GitContextManager instance received by ShellEngine.")
        if self.main_normal_input_accept_handler_ref:
            logger.info("ShellEngine received main_normal_input_accept_handler_ref.")
        else:
            logger.warning("ShellEngine did NOT receive main_normal_input_accept_handler_ref. Edit mode might not work correctly.")


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
        dangerous_patterns = [
            r'\brm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/(?!(?:tmp|var/tmp)\b)\S*',
            r'\brm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\s*(?:$|\.\.?\s*$|\*(?:\s.*|$))',
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
            output_prefix = f"Output from '{original_user_input_display}':\n"
            if stdout:
                append_output_func(f"{output_prefix}{stdout.decode(errors='replace').strip()}")
            if stderr:
                append_output_func(f"Stderr from '{original_user_input_display}':\n{stderr.decode(errors='replace').strip()}", style_class='warning')
            if not stdout and not stderr and process.returncode == 0:
                append_output_func(f"{output_prefix}(No output)", style_class='info')
            
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

    def _get_file_hash(self, filepath):
        """Calculates SHA256 hash of a file."""
        if not os.path.exists(filepath): return None
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
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
            branch_process_result = await asyncio.to_thread(subprocess.run,
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.PROJECT_ROOT, capture_output=True, text=True, check=True, errors='replace'
            )
            current_branch = branch_process_result.stdout.strip()
            self.ui_manager.append_output(f"ℹ️ On branch: '{current_branch}'. Fetching updates from 'origin/{current_branch}'...", style_class='info')
            logger.info(f"Current git branch: {current_branch}")
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

            pull_process_result = await asyncio.to_thread(subprocess.run,
                ['git', 'pull', 'origin', current_branch],
                cwd=self.PROJECT_ROOT, capture_output=True, text=True, errors='replace'
            )
            if pull_process_result.returncode == 0:
                self.ui_manager.append_output(f"✅ Git pull successful.\nOutput:\n{pull_process_result.stdout.strip()}", style_class='success')
                logger.info(f"Git pull output: {pull_process_result.stdout.strip()}")
                if "Already up to date." in pull_process_result.stdout:
                    self.ui_manager.append_output("✅ micro_X is up to date.", style_class='success')
                else:
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
        except FileNotFoundError:
            self.ui_manager.append_output("❌ Update failed: 'git' command not found.", style_class='error')
            logger.error("Update failed: git not found (unexpected).")
        except Exception as e:
            self.ui_manager.append_output(f"❌ Unexpected error during update: {e}", style_class='error')
            logger.error(f"Unexpected update error: {e}", exc_info=True)
        finally:
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate()

    async def _handle_config_command(self, user_input_parts: list):
        """Handles the /config command for runtime configuration management."""
        append_output_func = self.ui_manager.append_output
        cmd_help = (
            "ℹ️ /config usage:\n"
            "  list                         - Show current models and their specific AI options.\n"
            "  get <key.path>               - Get a config value (e.g., ai_models.primary_translator.options.temperature).\n"
            "  set <key.path> <value>       - Set a config value (e.g., set ai_models.validator.options.temperature 0.1).\n"
            "  save                         - Save current AI model configurations to user_config.json.\n"
            "  help                         - Show this help message."
        )

        if len(user_input_parts) < 2 or user_input_parts[1].lower() == 'help':
            append_output_func(cmd_help, style_class='help-base')
            return

        subcommand = user_input_parts[1].lower()

        if subcommand == 'list':
            ai_models_config = self.config.get("ai_models", {})
            append_output_func("Current AI Model Configurations:", style_class='info-header')
            if ai_models_config:
                for role, settings in ai_models_config.items():
                    append_output_func(f"\n🔹 {role}:", style_class='info-subheader')
                    # *** FIX: Handle both old string format and new dict format ***
                    if isinstance(settings, dict):
                        model_name = settings.get('model', 'N/A')
                        options = settings.get('options')
                        append_output_func(f"  - model: {model_name}", style_class='info-item')
                        if options:
                            append_output_func(f"  - options:", style_class='info-item')
                            for key, val in options.items():
                                append_output_func(f"    - {key}: {json.dumps(val)}", style_class='info-item')
                        else:
                            append_output_func(f"  - options: (Using Ollama model defaults)", style_class='info-item-empty')
                    elif isinstance(settings, str):
                        model_name = settings
                        append_output_func(f"  - model: {model_name}", style_class='info-item')
                        append_output_func(f"  - options: (Using Ollama model defaults)", style_class='info-item-empty')
                    else:
                        append_output_func(f"  (Invalid configuration for this role)", style_class='error')
            else:
                append_output_func("  (No AI models configured)", style_class='warning')

        elif subcommand == 'get':
            if len(user_input_parts) != 3:
                append_output_func("❌ Usage: /config get <key.path>", style_class='error'); return
            key_path = user_input_parts[2]
            value = _get_nested_config(self.config, key_path)
            if value is not None:
                append_output_func(f"{key_path}: {json.dumps(value, indent=2)}", style_class='info')
            else:
                append_output_func(f"❌ Key '{key_path}' not found.", style_class='error')

        elif subcommand == 'set':
            if len(user_input_parts) < 4:
                append_output_func("❌ Usage: /config set <key.path> <value>", style_class='error'); return
            key_path, new_value_str = user_input_parts[2], ' '.join(user_input_parts[3:])
            if not (key_path.startswith("ai_models.") and (".model" in key_path or ".options." in key_path)):
                 append_output_func("❌ For safety, only model names and options can be set at runtime.", style_class='error'); return
            try: typed_value = int(new_value_str)
            except ValueError:
                try: typed_value = float(new_value_str)
                except ValueError:
                    if new_value_str.lower() == 'true': typed_value = True
                    elif new_value_str.lower() == 'false': typed_value = False
                    else: typed_value = new_value_str
            success, error_msg = _set_nested_config(self.config, key_path, typed_value)
            if success: append_output_func(f"✅ Set '{key_path}' to {json.dumps(typed_value)}. (Not saved yet)", style_class='success')
            else: append_output_func(f"❌ {error_msg}", style_class='error')

        elif subcommand == 'save':
            user_config = {}
            try:
                if os.path.exists(self.USER_CONFIG_FILE_PATH):
                    with open(self.USER_CONFIG_FILE_PATH, 'r') as f: user_config = json.load(f)
            except Exception as e:
                append_output_func(f"❌ Could not read user_config.json: {e}", style_class='error'); return
            user_config["ai_models"] = self.config.get("ai_models", {})
            try:
                with open(self.USER_CONFIG_FILE_PATH, 'w') as f: json.dump(user_config, f, indent=2)
                append_output_func(f"✅ AI model configurations saved to {self.USER_CONFIG_FILE_PATH}", style_class='success')
            except Exception as e:
                append_output_func(f"❌ Failed to write to user_config.json: {e}", style_class='error')
        else:
            append_output_func(f"❌ Unknown /config subcommand: '{subcommand}'\n{cmd_help}", style_class='error')

    def _display_general_help(self):
        """Displays the general help message in the UI."""
        if not self.ui_manager: logger.error("display_general_help: UIManager not initialized."); return
        help_text_styled = [
            ('class:help-title', "micro_X AI-Enhanced Shell - Help\n\n"),
            ('class:help-text', "Welcome to micro_X! An intelligent shell that blends traditional command execution with AI capabilities.\n"),
            ('class:help-header', "\nAvailable Commands:\n"),
            ('class:help-command', "  /ai <query>              "), ('class:help-description', "- Translate natural language <query> into a Linux command.\n"),
            ('class:help-example', "                           Example: /ai list all text files in current folder\n"),
            ('class:help-command', "  /command <subcommand>    "), ('class:help-description', "- Manage command categorizations (simple, semi_interactive, interactive_tui).\n"),
            ('class:help-example', "                           Type '/command help' for detailed options.\n"),
            ('class:help-command', "  /config <subcommand>     "), ('class:help-description', "- Manage runtime AI configuration (e.g., temperature).\n"),
            ('class:help-example', "                           Type '/config help' for detailed options.\n"),
            ('class:help-command', "  /ollama <subcommand>     "), ('class:help-description', "- Manage the Ollama service (start, stop, restart, status).\n"),
            ('class:help-example', "                           Type '/ollama help' for detailed options.\n"),
            ('class:help-command', "  /utils <script> [args]   "), ('class:help-description', "- Run a utility script from the 'utils' directory.\n"),
            ('class:help-example', "                           Type '/utils list' or '/utils <script_name> help' for details.\n"),
            ('class:help-command', "  /update                  "), ('class:help-description', "- Check for and download updates for micro_X from its repository.\n"),
            ('class:help-command', "  /help                    "), ('class:help-description', "- Display this help message.\n"),
            ('class:help-command', "  exit | quit              "), ('class:help-description', "- Exit the micro_X shell.\n"),
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
            ("class:help-command", "  /ollama start      "), ("class:help-description", "- Attempts to start the managed Ollama service if not already running.\n"),
            ("class:help-command", "  /ollama stop       "), ("class:help-description", "- Attempts to stop the managed Ollama service.\n"),
            ("class:help-command", "  /ollama restart    "), ("class:help-description", "- Attempts to restart the managed Ollama service.\n"),
            ("class:help-command", "  /ollama status     "), ("class:help-description", "- Shows the current status of the Ollama service and managed session.\n"),
            ("class:help-command", "  /ollama help       "), ("class:help-description", "- Displays this help message.\n"),
            ("class:help-text", "\nNote: These commands primarily interact with an Ollama instance managed by micro_X in a tmux session. ")
        ]
        help_output_string = "".join([text for _, text in help_text])
        self.ui_manager.append_output(help_output_string, style_class='help-base')
        logger.info("Displayed Ollama command help.")

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
        
        script_name_no_ext = subcommand_or_script_name
        script_filename = f"{script_name_no_ext}.py"
        script_path = os.path.join(self.UTILS_DIR_PATH, script_filename)

        if not os.path.isfile(script_path):
            self.ui_manager.append_output(f"❌ Utility script not found: {script_filename} in '{self.UTILS_DIR_NAME}' directory.", style_class='error'); logger.warning(f"Utility script not found: {script_path}")
            self.ui_manager.append_output(utils_help_message, style_class='info')
            if current_app_inst and current_app_inst.is_running: current_app_inst.invalidate(); return
        
        args_for_script = parts[2:]
        command_to_execute_list = [sys.executable, script_path]
        
        if script_name_no_ext == "config_manager" and self.git_context_manager_instance:
            current_branch = await self.git_context_manager_instance.get_current_branch()
            if current_branch:
                command_to_execute_list.extend(["--branch", current_branch])
            else:
                logger.warning("Could not determine current branch for config_manager utility.")
                command_to_execute_list.extend(["--branch", "unknown"])
        
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
            
            if process.returncode != 0 and not is_help_request:
                self.ui_manager.append_output(f"⚠️ Utility '{script_filename}' exited with code {process.returncode}.", style_class='warning')
                logger.warning(f"Utility script '{script_path}' exited with code {process.returncode}. Args: {args_for_script}")
            elif not is_help_request and not process.stderr :
                self.ui_manager.append_output(f"✅ Utility '{script_filename}' completed.", style_class='success')
            
            if not is_help_request:
                logger.info(f"Utility script '{script_path}' completed with code {process.returncode}. Args: {args_for_script}")

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
        user_input_stripped = user_input.strip()
        logger.info(f"ShellEngine.handle_built_in_command received: '{user_input_stripped}'")
        if user_input_stripped.lower() in {"/help", "help"}:
            self._display_general_help(); return True
        elif user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
            self.ui_manager.append_output("Exiting micro_X Shell 🚪", style_class='info')
            logger.info("Exit command received from built-in handler.")
            if self.main_exit_app_ref: self.main_exit_app_ref()
            else:
                app_instance = self.ui_manager.get_app_instance()
                if app_instance and app_instance.is_running: app_instance.exit()
            return True
        elif user_input_stripped.lower() == "/update":
            await self._handle_update_command(); return True
        elif user_input_stripped.startswith("/utils"):
            await self._handle_utils_command_async(user_input_stripped); return True
        elif user_input_stripped.startswith("/ollama"):
            try:
                parts = user_input_stripped.split()
                await self._handle_ollama_command_async(parts)
            except Exception as e:
                self.ui_manager.append_output(f"❌ Error processing /ollama command: {e}", style_class='error')
                logger.error(f"Error in /ollama command '{user_input_stripped}': {e}", exc_info=True)
            return True
        elif user_input_stripped.startswith("/command"):
            logger.info(f"Handling /command subsystem input: {user_input_stripped}")
            if not self.category_manager_module:
                logger.error("Category Manager module not available.")
                self.ui_manager.append_output("❌ Internal Error: Command subsystem not available.", style_class='error')
                return True
            action_result = self.category_manager_module.handle_command_subsystem_input(user_input_stripped)
            if isinstance(action_result, dict) and action_result.get('action') == 'force_run':
                await self.process_command(action_result['command'], user_input_stripped, forced_category=action_result['category'])
            return True
        elif user_input_stripped.startswith("/config"):
            await self._handle_config_command(user_input_stripped.split()); return True
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

            exec_message_prefix = "Executing"
            if forced_category:
                if confirmation_result and confirmation_result.get('action') == 'execute_and_categorize':
                    exec_message_prefix = f"Executing (user categorized as {category})"
                else: exec_message_prefix = "Forced execution"
            
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