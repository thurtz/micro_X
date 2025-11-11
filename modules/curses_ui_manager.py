# modules/curses_ui_manager.py

import curses
import os
import asyncio
import logging
import sys
from typing import Optional, List, Tuple, Callable
from prompt_toolkit.history import FileHistory
from modules.ai_handler import explain_linux_command_with_ai
from modules.category_manager import (
    CATEGORY_MAP as CM_CATEGORY_MAP,
    CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS,
)

logger = logging.getLogger(__name__)


class CursesUIManager:
    """
    A curses-based UI Manager.
    
    This class aims to replicate the core functionality of the prompt_toolkit
    UIManager for a consistent user experience in environments where
    prompt_toolkit is not available.
    """

    def __init__(self, config: dict, shell_engine_instance=None):
        """Initializes the CursesUIManager.

        Args:
            config: The application configuration.
            shell_engine_instance: An instance of the ShellEngine.
        """
        self.config = config
        self.shell_engine_instance = shell_engine_instance
        self.output_buffer: List[Tuple[str, str]] = []
        self.input_text = ""
        self.current_prompt_text = ""
        self.app = None
        self.stdscr = None
        self.input_handler_callback = None
        self.input_loop_task = None
        self.input_history: Optional[FileHistory] = None
        self.history_index: int = 0
        self.is_in_edit_mode = False
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.hung_task_flow_active = False
        self.api_input_flow_active = False
        self.categorization_flow_state = {}
        self.confirmation_flow_state = {}
        self.hung_task_flow_state = {}
        self.api_input_flow_state = {}
        self.last_output_was_separator = False
        self.startup_separator_added = False
        self.initial_prompt_settled = False
        self.main_exit_app_ref: Optional[Callable] = None
        self.main_restore_normal_input_ref: Optional[Callable] = None
        self.normal_input_accept_handler_ref: Optional[Callable] = None
        self.is_running = False
        logger.info("CursesUIManager initialized.")

    def initialize_ui_elements(
        self,
        initial_prompt_text: str,
        history: FileHistory,
        output_buffer_main: Optional[list] = None,
        shell_engine_instance=None,
    ):
        """Initializes the curses screen and UI elements.

        Args:
            initial_prompt_text: The initial text for the prompt.
            history: The history object for the input field.
            output_buffer_main: A list of (style, text) tuples for initial output.
            shell_engine_instance: An instance of the ShellEngine.

        Returns:
            The curses screen object.
        """
        self.shell_engine_instance = shell_engine_instance if shell_engine_instance else self.shell_engine_instance
        self.input_history = history
        try:
            self.stdscr = curses.initscr()
            curses.start_color()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            self.stdscr.nodelay(True)
        except Exception as e:
            logger.critical(f"Failed to initialize curses: {e}")
            sys.exit(1)
        self.current_prompt_text = initial_prompt_text
        if output_buffer_main:
            self.output_buffer = output_buffer_main
        self.app = self.stdscr
        logger.info("Curses UI elements initialized and non-blocking mode enabled.")
        return self.stdscr

    def get_key_bindings(self):
        """Returns None as keybindings are handled directly in the input loop."""
        return None

    def append_output(self, text: str, style_class: str = 'default', internal_call: bool = False):
        """Appends text to the output buffer and redraws the screen."""
        if not text.endswith('\n'):
            text += '\n'
        self.output_buffer.append((style_class, text))
        self._redraw()

    def update_input_prompt(self, current_directory_path: str):
        """Updates the input prompt with the current directory."""
        home_dir = os.path.expanduser("~")
        dir_for_prompt = current_directory_path
        if current_directory_path.startswith(home_dir):
            dir_for_prompt = "~" + current_directory_path[len(home_dir):]
        self.current_prompt_text = f"({dir_for_prompt}) > "
        self._redraw()

    def set_normal_input_mode(self, accept_handler_func=None, current_directory_path: str=''):
        """Sets the UI to the normal input mode."""
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.hung_task_flow_active = False
        self.is_in_edit_mode = False
        self.input_text = ""
        self.input_handler_callback = accept_handler_func
        if current_directory_path:
            self.update_input_prompt(current_directory_path)
        else:
            self._redraw()

    def set_flow_input_mode(self, prompt_text: str, accept_handler_func, is_categorization: bool = False, is_confirmation: bool = False, is_api_input: bool = False):
        """Sets the UI to a special flow input mode."""
        self.categorization_flow_active = is_categorization
        self.confirmation_flow_active = is_confirmation
        self.api_input_flow_active = is_api_input
        self.is_in_edit_mode = False
        self.input_text = ""
        self.input_handler_callback = accept_handler_func
        self.current_prompt_text = prompt_text
        self._redraw()

    def set_edit_mode(self, accept_handler_func, command_to_edit: str):
        """Sets the UI to edit mode."""
        self.is_in_edit_mode = True
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.input_text = command_to_edit
        self.input_handler_callback = accept_handler_func
        self.current_prompt_text = "[Edit Command]> "
        self._redraw()

    def get_app_instance(self):
        """Returns the curses screen object."""
        return self

    def add_interaction_separator(self):
        """Adds a separator to the output."""
        self.append_output(f"\n{self.config.get('ui', {}).get('output_separator_character', '─') * 30}\n")

    def add_startup_separator(self):
        """Adds a startup separator to the output."""
        self.append_output(f"\n{self.config.get('ui', {}).get('startup_separator_string', '--- STARTUP ---')}\n")

    def exit(self):
        """Cleans up the curses environment and exits."""
        logger.info("CursesUIManager: exit() called.")
        self.is_running = False
        if self.input_loop_task and not self.input_loop_task.done():
            self.input_loop_task.cancel()
            logger.info("CursesUIManager: Input loop task cancelled.")
        if self.stdscr:
            self.stdscr.keypad(False)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
            logger.info("CursesUIManager: curses.endwin() called and terminal restored.")

    def invalidate(self):
        """Redraws the screen."""
        self._redraw()

    async def run_async(self):
        """Runs the main asynchronous input loop."""
        logger.info("CursesUIManager.run_async() started.")
        self.is_running = True
        self.input_loop_task = asyncio.create_task(self._input_task())
        try:
            await self.input_loop_task
        except asyncio.CancelledError:
            logger.info("Curses input task cancelled. Exiting run_async.")
        finally:
            self.exit()

    def _redraw(self):
        if not self.stdscr:
            return
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        output_start_line = max(0, len(self.output_buffer) - (height - 2))
        current_y = 0
        for i, (style, text) in enumerate(self.output_buffer[output_start_line:]):
            lines = text.splitlines()
            for line in lines:
                if current_y < height - 2:
                    self.stdscr.addstr(current_y, 0, line[:width-1])
                current_y += 1
        prompt_str = self.current_prompt_text
        input_str = self.input_text
        self.stdscr.addstr(height - 1, 0, prompt_str + input_str[:width-len(prompt_str)-1])
        cursor_x = len(prompt_str) + len(input_str)
        self.stdscr.move(height - 1, min(cursor_x, width - 1))
        self.stdscr.refresh()

    async def _input_task(self):
        while self.is_running:
            try:
                key = self.stdscr.getch()
                if key == -1:
                    await asyncio.sleep(0.05)
                    continue

                if key in [curses.KEY_ENTER, 10, 13]:
                    if self.categorization_flow_active or self.confirmation_flow_active or self.is_in_edit_mode or self.hung_task_flow_active or self.api_input_flow_active:
                        if self.input_handler_callback:
                            self.input_handler_callback(self.input_text)
                            await asyncio.sleep(0.001)
                    else:
                        if self.shell_engine_instance:
                            if not await self.shell_engine_instance.handle_built_in_command(self.input_text):
                                await self.shell_engine_instance.submit_user_input(self.input_text)
                            await asyncio.sleep(0.001)
                    self.input_text = ""
                elif key == 27: # escape
                    if self.hung_task_flow_active:
                        self.append_output("\n⚠️ Hung task prompt cancelled.", 'warning')
                        if 'future' in self.hung_task_flow_state and not self.hung_task_flow_state['future'].done():
                            self.hung_task_flow_state['future'].set_result({'action': 'cancel'})
                    elif self.api_input_flow_active:
                        self.append_output("\n⚠️ API input request cancelled.", 'warning')
                        if 'future' in self.api_input_flow_state and not self.api_input_flow_state['future'].done():
                            self.api_input_flow_state['future'].set_result("") # Return empty string on cancel
                    elif self.categorization_flow_active:
                        self.append_output("\n⚠️ Categorization cancelled by user.", 'warning')
                        logger.info("Categorization flow cancelled by Escape.")
                        if 'future' in self.categorization_flow_state and \
                           self.categorization_flow_state.get('future') and \
                           not self.categorization_flow_state['future'].done():
                            self.categorization_flow_state['future'].set_result({'action': 'cancel_execution'})
                    elif self.confirmation_flow_active:
                        self.append_output("\n⚠️ Command confirmation cancelled by user.", 'warning')
                        logger.info("Confirmation flow cancelled by Escape.")
                        if 'future' in self.confirmation_flow_state and \
                           self.confirmation_flow_state.get('future') and \
                           not self.confirmation_flow_state['future'].done():
                            self.confirmation_flow_state['future'].set_result({'action': 'cancel'})
                    elif self.is_in_edit_mode:
                        self.append_output("\n⌨️ Command editing cancelled.", 'info')
                        logger.info("Command edit mode cancelled by Escape.")
                        self.is_in_edit_mode = False
                        if self.main_restore_normal_input_ref:
                            self.main_restore_normal_input_ref()
                elif key in [3, 4]: # ctrl+c, ctrl+d
                    if self.main_exit_app_ref:
                        self.main_exit_app_ref()
                    else:
                        self.exit()
                elif key == 11: # ctrl+k
                    if self.shell_engine_instance and self.shell_engine_instance.current_process:
                        logger.info("Ctrl+K pressed, killing current process.")
                        asyncio.create_task(self.shell_engine_instance.kill_current_process())
                    else:
                        logger.info("Ctrl+K pressed, but no process to kill.")
                elif key == curses.KEY_BACKSPACE or key == 127:
                    self.input_text = self.input_text[:-1]
                elif key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]:
                    pass
                else:
                    self.input_text += chr(key)
                self._redraw()
            except curses.error:
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Error in curses input task: {e}")
                self.exit()

    async def prompt_for_hung_task(self, hung_command: str) -> dict:
        """Initiates a flow to ask the user how to handle a hung command."""
        logger.info(f"CursesUIManager: Starting hung task flow for command: '{hung_command}'")
        self.hung_task_flow_active = True
        self.hung_task_flow_state = {
            'future': asyncio.Future()
        }
        self._ask_hung_task_choice(hung_command)
        try:
            return await self.hung_task_flow_state['future']
        finally:
            self.hung_task_flow_active = False
            logger.info("CursesUIManager: Hung task flow ended.")

    def _ask_hung_task_choice(self, hung_command: str):
        self.append_output(f"\n⚠️ The command '{hung_command}' is taking a long time.", 'warning')
        self.append_output("   What would you like to do?", 'categorize-prompt')
        self.append_output("   [K]ill the command | [I]gnore and continue waiting | [C]ancel your new command", 'categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Hung Task] Choice (K/I/C): ",
            accept_handler_func=self._handle_hung_task_response,
            is_confirmation=True
        )

    def _handle_hung_task_response(self, response_text: str):
        response = response_text.strip().lower()
        future = self.hung_task_flow_state.get('future')
        if not future or future.done():
            return

        if response in ['k', 'kill']:
            future.set_result({'action': 'kill'})
        elif response in ['i', 'ignore']:
            future.set_result({'action': 'ignore'})
        elif response in ['c', 'cancel']:
            future.set_result({'action': 'cancel'})
        else:
            self.append_output("Invalid choice. Please enter K, I, or C.", 'error')

    async def prompt_for_api_input(self, prompt: str) -> str:
        """Initiates a flow to get input from the user for an API request."""
        logger.info(f"CursesUIManager: Starting API input flow with prompt: '{prompt}'")
        self.api_input_flow_active = True
        self.api_input_flow_state = {
            'future': asyncio.Future()
        }

        # Append the prompt to the output field so the user sees the question.
        self.append_output(prompt, style_class='categorize-prompt')

        self.set_flow_input_mode(
            prompt_text="> ", # Use a generic prompt for the input line
            accept_handler_func=self._handle_api_input_response,
            is_api_input=True
        )

        try:
            result = await self.api_input_flow_state['future']
            # Also append the user's answer to the output to make it part of the history
            self.append_output(result)
            return result
        finally:
            self.api_input_flow_active = False
            logger.info("CursesUIManager: API input flow ended.")
            if self.main_restore_normal_input_ref:
                self.main_restore_normal_input_ref()

    def _handle_api_input_response(self, user_input: str):
        future = self.api_input_flow_state.get('future')
        if not future or future.done():
            return
        
        future.set_result(user_input)

    async def prompt_for_command_confirmation(
        self,
        command_to_confirm: str,
        display_source: str,
        normal_input_accept_handler_ref,
    ) -> dict:
        """Initiates the interactive flow for confirming an AI-generated command."""
        self.confirmation_flow_active = True
        self.categorization_flow_active = False
        self.is_in_edit_mode = False
        self.normal_input_accept_handler_ref = normal_input_accept_handler_ref
        self.confirmation_flow_state = {
            'command_to_confirm': command_to_confirm,
            'display_source': display_source,
            'step': 'ask_main_choice',
            'future': asyncio.Future(),
        }
        self._ask_confirmation_main_choice()
        try:
            result = await self.confirmation_flow_state['future']
            if result.get('action') == 'edit_mode_engaged':
                self.set_edit_mode(self.normal_input_accept_handler_ref, result.get('command', ''))
            return result
        finally:
            self.confirmation_flow_active = False

    def _ask_confirmation_main_choice(self):
        cmd = self.confirmation_flow_state['command_to_confirm']
        source = self.confirmation_flow_state['display_source']
        self.append_output(f"\n🤖 AI proposed command (from: {source}):", 'ai-query')
        self.append_output(f"    👉 {cmd}", 'executing')
        self.append_output(
            "Action: [Y]es (Exec, prompt if new) | [Ys] Simple & Run | [Ym] Semi-Interactive & Run | [Yi] TUI & Run | [E]xplain | [M]odify | [C]ancel?",
            'categorize-prompt'
        )
        self.set_flow_input_mode(
            prompt_text="[Confirm AI Cmd] Choice (Y/Ys/Ym/Yi/E/M/C): ",
            accept_handler_func=self._handle_confirmation_main_choice_response,
            is_confirmation=True
        )

    def _handle_confirmation_main_choice_response(self, buff):
        response = buff.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        cmd_to_confirm = self.confirmation_flow_state['command_to_confirm']
        if not future_to_set or future_to_set.done():
            return
        if response in ['y', 'yes']:
            future_to_set.set_result({'action': 'execute', 'command': cmd_to_confirm})
        elif response == 'ys':
            future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'simple'})
        elif response == 'ym':
            future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'semi_interactive'})
        elif response == 'yi':
            future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'interactive_tui'})
        elif response in ['e', 'explain']:
            self.confirmation_flow_state['step'] = 'explain'
            self.input_text = ""
            asyncio.create_task(self._handle_explain_command_async())
        elif response in ['m', 'modify']:
            future_to_set.set_result({'action': 'edit_mode_engaged', 'command': cmd_to_confirm})
        elif response in ['c', 'cancel', 'n', 'no']:
            future_to_set.set_result({'action': 'cancel'})
        else:
            self.append_output("Invalid choice. Please enter Y, Ys, Ym, Yi, E, M, or C.", 'error')
            self._ask_confirmation_main_choice()
            return
        self.input_text = ""

    async def _handle_explain_command_async(self):
        command_to_explain = self.confirmation_flow_state['command_to_confirm']
        self.append_output(f"\n🧠 Asking AI to explain: {command_to_explain}", 'ai-thinking')
        self.invalidate()
        explanation = await explain_linux_command_with_ai(command_to_explain, self.config, self.append_output)
        if explanation:
            self.append_output("\n💡 AI Explanation:", 'info-header')
            self.append_output(explanation, 'info')
        else:
            self.append_output("⚠️ AI could not provide an explanation.", 'warning')
        self._ask_confirmation_after_explain()

    def _ask_confirmation_after_explain(self):
        cmd = self.confirmation_flow_state['command_to_confirm']
        self.append_output(f"\nCommand to consider: {cmd}", 'executing')
        self.append_output(
            "Action: [Y]es (Exec, prompt if new) | [Ys] Simple & Run | [Ym] Semi-Interactive & Run | [Yi] TUI & Run | [M]odify | [C]ancel?",
            'categorize-prompt'
        )

    def _handle_confirmation_after_explain_response(self, buff):
        response = buff.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        cmd_to_confirm = self.confirmation_flow_state['command_to_confirm']
        if not future_to_set or future_to_set.done():
            return
        if response in ['y', 'yes']:
            future_to_set.set_result({'action': 'execute', 'command': cmd_to_confirm})
        elif response == 'ys':
            future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'simple'})
        elif response == 'ym':
            future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'semi_interactive'})
        elif response == 'yi':
            future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'interactive_tui'})
        elif response in ['m', 'modify']:
            future_to_set.set_result({'action': 'edit_mode_engaged', 'command': cmd_to_confirm})
        elif response in ['c', 'cancel', 'n', 'no']:
            future_to_set.set_result({'action': 'cancel'})
        else:
            self.append_output("Invalid choice. Please enter Y, Ys, Ym, Yi, M, or C.", 'error')
            self._ask_confirmation_after_explain()
            return
        self.input_text = ""

    async def start_categorization_flow(
        self,
        command_initially_proposed: str,
        ai_raw_candidate: Optional[str] = None,
        original_direct_input: Optional[str] = None,
    ) -> dict:
        """Initiates the interactive flow for categorizing an unknown command."""
        self.categorization_flow_active = True
        self.confirmation_flow_active = False
        self.is_in_edit_mode = False
        self.categorization_flow_state = {
            'command_initially_proposed': command_initially_proposed,
            'ai_raw_candidate': ai_raw_candidate,
            'original_direct_input': original_direct_input,
            'command_to_add_final': command_initially_proposed,
            'step': 1,
            'future': asyncio.Future(),
        }
        if original_direct_input and original_direct_input.strip() != command_initially_proposed.strip():
            self._ask_step_0_5_confirm_command_base()
        else:
            self._ask_step_1_main_action()
        try:
            return await self.categorization_flow_state['future']
        finally:
            self.categorization_flow_active = False
            self.input_text = ""

    def _ask_step_0_5_confirm_command_base(self):
        proposed = self.categorization_flow_state['command_initially_proposed']
        original = self.categorization_flow_state['original_direct_input']
        self.append_output(f"\nSystem processed to: '{proposed}'\nOriginal input was: '{original}'", 'categorize-info')
        self.append_output(f"Which version to categorize?\n  1: Processed ('{proposed}')\n  2: Original ('{original}')\n  3: Modify/Enter new command\n  4: Cancel categorization", 'categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] Choice (1-4): ",
            accept_handler_func=self._handle_step_0_5_response,
            is_categorization=True
        )

    def _handle_step_0_5_response(self, buff):
        response = buff.strip()
        proposed = self.categorization_flow_state['command_initially_proposed']
        original = self.categorization_flow_state['original_direct_input']
        future_to_set = self.categorization_flow_state.get('future')
        if response == '1':
            self.categorization_flow_state['command_to_add_final'] = proposed
            self.append_output(f"Using processed: '{proposed}'", 'categorize-info')
            self._ask_step_1_main_action()
        elif response == '2' and original:
            self.categorization_flow_state['command_to_add_final'] = original
            self.append_output(f"Using original: '{original}'", 'categorize-info')
            self._ask_step_1_main_action()
        elif response == '3':
            self.append_output("\nEnter the new command string you want to categorize:", 'categorize-prompt')
            self.set_flow_input_mode(
                prompt_text="[Categorize] New command: ",
                accept_handler_func=self._handle_step_3_5_response,
                is_categorization=True
            )
        elif response == '4':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel_execution'})
        else:
            self.append_output("Invalid choice (1-4). Please try again.", 'error')
            self._ask_step_0_5_confirm_command_base()

    def _handle_step_3_5_response(self, buff):
        custom_command = buff.strip()
        if not custom_command:
            self.append_output("⚠️ Command cannot be empty.", 'warning')
            self._ask_step_3_5_enter_custom_command_for_categorization()
            return
        self.categorization_flow_state['command_to_add_final'] = custom_command
        self.append_output(f"New command for categorization: '{custom_command}'", 'categorize-info')
        self._ask_step_1_main_action()

    def _ask_step_1_main_action(self):
        cmd_display = self.categorization_flow_state['command_to_add_final']
        default_cat_name = self.config['behavior']['default_category_for_unclassified']
        self.append_output(f"\nCommand to categorize: '{cmd_display}'", 'categorize-info')
        self.append_output(f"How to categorize this command?\n  1: simple | 2: semi_interactive | 3: interactive_tui\n  M: Modify command before categorizing\n  D: Execute as default '{default_cat_name}' (once, no save)\n  C: Cancel categorization & execution", 'categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] Action (1-3/M/D/C): ",
            accept_handler_func=self._handle_step_1_main_action_response,
            is_categorization=True
        )

    def _handle_step_1_main_action_response(self, buff):
        response = buff.strip().lower()
        cmd_to_add = self.categorization_flow_state['command_to_add_final']
        future_to_set = self.categorization_flow_state.get('future')
        if not future_to_set or future_to_set.done():
            return
        chosen_category = CM_CATEGORY_MAP.get(response)
        if chosen_category:
            future_to_set.set_result({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category})
        elif response == 'm':
            self.append_output(f"\nCurrent command: '{cmd_to_add}'\nEnter your modified command below:", 'categorize-prompt')
            self.set_flow_input_mode(
                prompt_text="[Categorize] Modified Cmd: ",
                accept_handler_func=self._handle_step_4_modified_command_response,
                is_categorization=True
            )
        elif response == 'd':
            future_to_set.set_result({'action': 'execute_as_default'})
        elif response == 'c':
            future_to_set.set_result({'action': 'cancel_execution'})
        else:
            self.append_output("Invalid choice. Please enter 1-3, M, D, or C.", 'error')
            self._ask_step_1_main_action()

    def _handle_step_4_modified_command_response(self, buff):
        modified_command = buff.strip()
        if not modified_command:
            self.append_output("⚠️ Modified command cannot be empty. Using previous.", 'warning')
        else:
            self.categorization_flow_state['command_to_add_final'] = modified_command
        self._ask_step_4_5_category_for_modified()

    def _ask_step_4_5_category_for_modified(self):
        cmd_to_categorize = self.categorization_flow_state['command_to_add_final']
        self.append_output(f"\nCategory for command: '{cmd_to_categorize}'", 'categorize-info')
        self.append_output(f"  1: simple | 2: semi_interactive | 3: interactive_tui", 'categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] Category (1-3): ",
            accept_handler_func=self._handle_step_4_5_response,
            is_categorization=True
        )

    def _handle_step_4_5_response(self, buff):
        response = buff.strip()
        chosen_category = CM_CATEGORY_MAP.get(response)
        future_to_set = self.categorization_flow_state.get('future')
        cmd_to_add = self.categorization_flow_state['command_to_add_final']
        if not future_to_set or future_to_set.done():
            return
        if chosen_category:
            future_to_set.set_result({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category})
        else:
            self.append_output("Invalid choice. Please enter 1, 2, or 3.", 'error')
            self._ask_step_4_5_category_for_modified()
            return
        self.input_text = ""