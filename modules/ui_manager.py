# modules/ui_manager.py
import logging
import os
import asyncio

from prompt_toolkit import Application # Keep this import for type hinting if needed elsewhere
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Window, Layout
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.history import FileHistory

from modules.category_manager import CATEGORY_MAP as CM_CATEGORY_MAP, CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS
from modules.ai_handler import explain_linux_command_with_ai


logger = logging.getLogger(__name__)

class UIManager:
    """The main class for managing the application's UI.
    
    Manages the entire `prompt_toolkit` Text User Interface (TUI),
    including input/output fields, keybindings, styling, and coordinating complex,
    multi-step interactive user flows like command categorization and confirmation.
    """
    def __init__(self, config: dict, shell_engine_instance=None):
        """Initializes the UIManager with the application configuration.

        The Application instance itself is set later via `ui_manager_instance.app = app_instance`.
        
        Args:
            config: The application configuration.
        """
        self.config = config
        self.shell_engine_instance = shell_engine_instance
        self.app = None # This will be set by main.py
        self.output_field = None
        self.input_field = None
        self.key_help_field = None
        self.root_container = None
        self.layout = None
        self.style = None
        self.auto_scroll = True
        self.output_buffer = []
        self.max_output_buffer_lines = config.get('ui', {}).get('max_output_buffer_lines', 500) # Default to 500 lines

        self.categorization_flow_active = False
        self.categorization_flow_state = {}

        self.confirmation_flow_active = False
        self.confirmation_flow_state = {}

        self.hung_task_flow_active = False
        self.hung_task_flow_state = {}

        self.api_input_flow_active = False
        self.api_input_flow_state = {}

        self.is_in_edit_mode = False

        self.current_prompt_text = ""

        self.status_bar_control = FormattedTextControl("")

        self.kb = KeyBindings()
        self._register_keybindings()

        self.main_exit_app_ref = None
        self.main_restore_normal_input_ref = None

        self.initial_prompt_settled = False
        self.last_output_was_separator = False
        self.startup_separator_added = False

        logger.debug("UIManager initialized with config and keybindings.")

    def _register_keybindings(self):
        @self.kb.add('c-c')
        @self.kb.add('c-d')
        def _handle_exit(event):
            logger.info("Exit keybinding triggered.")
            if self.main_exit_app_ref:
                self.main_exit_app_ref()
            else:
                event.app.exit()

        @self.kb.add('escape')
        def _handle_cancel(event):
            if self.hung_task_flow_active:
                self.append_output("\n⚠️ Hung task prompt cancelled.", style_class='warning')
                if 'future' in self.hung_task_flow_state and not self.hung_task_flow_state['future'].done():
                    self.hung_task_flow_state['future'].set_result({'action': 'cancel'})
                event.app.invalidate()
            elif self.api_input_flow_active:
                self.append_output("\n⚠️ API input request cancelled.", style_class='warning')
                if 'future' in self.api_input_flow_state and not self.api_input_flow_state['future'].done():
                    self.api_input_flow_state['future'].set_result("") # Return empty string on cancel
                event.app.invalidate()
            elif self.categorization_flow_active:
                self.append_output("\n⚠️ Categorization cancelled by user.", style_class='warning')
                logger.info("Categorization flow cancelled by Escape.")
                if 'future' in self.categorization_flow_state and \
                   self.categorization_flow_state.get('future') and \
                   not self.categorization_flow_state['future'].done():
                    self.categorization_flow_state['future'].set_result({'action': 'cancel_execution'})
                event.app.invalidate()
            elif self.confirmation_flow_active:
                self.append_output("\n⚠️ Command confirmation cancelled by user.", style_class='warning')
                logger.info("Confirmation flow cancelled by Escape.")
                if 'future' in self.confirmation_flow_state and \
                   self.confirmation_flow_state.get('future') and \
                   not self.confirmation_flow_state['future'].done():
                    self.confirmation_flow_state['future'].set_result({'action': 'cancel'})
                event.app.invalidate()
            elif self.is_in_edit_mode:
                self.append_output("\n⌨️ Command editing cancelled.", style_class='info')
                logger.info("Command edit mode cancelled by Escape.")
                self.is_in_edit_mode = False
                if self.main_restore_normal_input_ref:
                    self.main_restore_normal_input_ref()
                event.app.invalidate()

        @self.kb.add('c-k')
        def _handle_kill_process(event):
            if self.shell_engine_instance and self.shell_engine_instance.current_process:
                logger.info("Ctrl+K pressed, killing current process.")
                asyncio.create_task(self.shell_engine_instance.kill_current_process())
            else:
                logger.info("Ctrl+K pressed, but no process to kill.")


        @self.kb.add('c-n')
        def _handle_newline(event):
            if not self.categorization_flow_active and \
               not self.confirmation_flow_active and \
               not self.api_input_flow_active and \
               not self.is_in_edit_mode:
                if self.input_field and self.input_field.multiline:
                    event.current_buffer.insert_text('\n')
            elif self.input_field and self.input_field.multiline and self.is_in_edit_mode: # Allow newline in edit mode too
                    event.current_buffer.insert_text('\n')


        @self.kb.add('enter')
        def _handle_enter(event):
            buff = event.current_buffer
            buff.validate_and_handle()

        @self.kb.add('tab')
        def _handle_tab(event):
            buff = event.current_buffer
            if buff.complete_state:
                event.app.current_buffer.complete_next()
            else:
                event.current_buffer.insert_text('    ')

        @self.kb.add('pageup')
        def _handle_pageup(event):
            if self.output_field and self.output_field.window.render_info:
                self.output_field.window._scroll_up()
                event.app.invalidate()

        @self.kb.add('pagedown')
        def _handle_pagedown(event):
            if self.output_field and self.output_field.window.render_info:
                self.output_field.window._scroll_down()
                event.app.invalidate()

        @self.kb.add('c-up')
        def _handle_ctrl_up(event):
            if not self.categorization_flow_active and not self.confirmation_flow_active and not self.api_input_flow_active:
                event.current_buffer.cursor_up(count=1)

        @self.kb.add('c-down')
        def _handle_ctrl_down(event):
            if not self.categorization_flow_active and not self.confirmation_flow_active and not self.api_input_flow_active:
                event.current_buffer.cursor_down(count=1)

        @self.kb.add('up')
        def _handle_up_arrow(event):
            if self.categorization_flow_active or self.confirmation_flow_active or self.api_input_flow_active:
                pass # Do not interfere with flow-specific input handling if any

            buff = event.current_buffer
            doc = buff.document
            if doc.cursor_position_row == 0: # Only go to history if at the first line of input
                if buff.history_backward():
                    buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                    event.app.invalidate()
            else: # Otherwise, just move cursor up within multiline input
                buff.cursor_up()

        @self.kb.add('down')
        def _handle_down_arrow(event):
            if self.categorization_flow_active or self.confirmation_flow_active or self.api_input_flow_active:
                pass # Do not interfere with flow-specific input handling if any

            buff = event.current_buffer
            doc = buff.document
            if doc.cursor_position_row == doc.line_count - 1: # Only go to history if at the last line
                if buff.history_forward():
                    buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                    event.app.invalidate()
            else: # Otherwise, just move cursor down
                buff.cursor_down()

        logger.debug("UIManager: Keybindings registered.")

    def get_key_bindings(self) -> KeyBindings:
        """Returns the configured keybindings for the application."""
        return self.kb

    def exit(self):
        """Tells the prompt_toolkit application to exit gracefully."""
        if self.app and hasattr(self.app, 'exit'):
            logger.info("UIManager: Calling app.exit() to terminate prompt_toolkit loop.")
            self.app.exit()
        else:
            logger.warning("UIManager: exit() called, but self.app is not set or has no exit method.")

    # --- Hung Task Flow ---
    async def prompt_for_hung_task(self, hung_command: str) -> dict:
        """Initiates a flow to ask the user how to handle a hung command."""
        logger.info(f"UIManager: Starting hung task flow for command: '{hung_command}'")
        self.hung_task_flow_active = True
        self.hung_task_flow_state = {
            'future': asyncio.Future()
        }

        self._ask_hung_task_choice(hung_command)

        try:
            result = await self.hung_task_flow_state['future']
            return result
        finally:
            self.hung_task_flow_active = False
            logger.info("UIManager: Hung task flow ended.")

    def _ask_hung_task_choice(self, hung_command: str):
        self.append_output(f"\n⚠️ The command '{hung_command}' is taking a long time.", style_class='warning')
        self.append_output("   What would you like to do?", style_class='categorize-prompt')
        self.append_output("   [K]ill the command | [I]gnore and continue waiting | [C]ancel your new command", style_class='categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Hung Task] Choice (K/I/C): ",
            accept_handler_func=self._handle_hung_task_response,
            is_confirmation=True # Re-use confirmation flag to lock scrolling etc.
        )

    def _handle_hung_task_response(self, buff):
        response = buff.text.strip().lower()
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
            self.append_output("Invalid choice. Please enter K, I, or C.", style_class='error')
            # No need to re-ask here, the prompt is still visible. The handler will just be called again.

    # --- Caution Confirmation Flow ---
    async def prompt_for_caution_confirmation(self, command_to_confirm: str) -> dict:
        """Initiates a simple Yes/No confirmation for potentially sensitive commands."""
        logger.info(f"UIManager: Starting caution confirmation for '{command_to_confirm}'.")
        self.confirmation_flow_active = True
        self.confirmation_flow_state = {
            'command_to_confirm': command_to_confirm,
            'future': asyncio.Future()
        }

        self.append_output(f"\n⚠️ CAUTION: The command '{command_to_confirm.split()[0]}' can have significant effects.", style_class='security-warning')
        self.append_output(f"   Full command: '{command_to_confirm}'", style_class='security-warning')
        self.append_output("   Are you sure you want to proceed?", style_class='security-warning')

        self.set_flow_input_mode(
            prompt_text="[Confirm Execution] (yes/no): ",
            accept_handler_func=self._handle_caution_confirmation_response,
            is_confirmation=True
        )

        try:
            result = await self.confirmation_flow_state['future']
            logger.info(f"UIManager: Caution flow future resolved with: {result}")
            return result
        finally:
            self.confirmation_flow_active = False
            logger.info("UIManager: Caution flow ended.")

    def _handle_caution_confirmation_response(self, buff):
        response = buff.text.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        if not future_to_set or future_to_set.done():
            return

        if response in ['y', 'yes']:
            future_to_set.set_result({'proceed': True})
        elif response in ['n', 'no']:
            future_to_set.set_result({'proceed': False})
        else:
            self.append_output("Invalid choice. Please enter 'yes' or 'no'.", style_class='error')
            self.set_flow_input_mode(
                prompt_text="[Confirm Execution] (yes/no): ",
                accept_handler_func=self._handle_caution_confirmation_response,
                is_confirmation=True
            )

    # --- API Input Flow ---
    async def prompt_for_api_input(self, prompt: str) -> str:
        """Initiates a flow to get input from the user for an API request."""
        logger.info(f"UIManager: Starting API input flow with prompt: '{prompt}'")
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
            logger.info("UIManager: API input flow ended.")
            # Restore normal input handler after the flow is complete
            if self.main_restore_normal_input_ref:
                self.main_restore_normal_input_ref()

    def _handle_api_input_response(self, buff):
        user_input = buff.text.strip()
        future = self.api_input_flow_state.get('future')
        if not future or future.done():
            return
        
        future.set_result(user_input)

    # --- Categorization Flow Methods ---
    async def start_categorization_flow(self, command_initially_proposed: str,
                                        ai_raw_candidate: str | None,
                                        original_direct_input: str | None
                                        ):
        """Initiates the interactive flow for categorizing an unknown command.

        This is an async method that awaits user input through the UI.

        Args:
            command_initially_proposed: The command string to be categorized.
            ai_raw_candidate: The raw output from the AI.
            original_direct_input: The original user input if it was different.

        Returns:
            A dictionary containing the result, e.g.,
            {'action': 'categorize_and_execute', 'command': '...', 'category': '...'}. """
        self.categorization_flow_active = True
        self.confirmation_flow_active = False
        self.is_in_edit_mode = False
        self.categorization_flow_state = {
            'command_initially_proposed': command_initially_proposed,
            'ai_raw_candidate': ai_raw_candidate,
            'original_direct_input': original_direct_input,
            'command_to_add_final': command_initially_proposed,
            'step': 0.5,
            'future': asyncio.Future()
        }
        logger.info(f"UIManager: Starting categorization flow for '{command_initially_proposed}'. State initialized.")
        self._ask_step_0_5_confirm_command_base()

        try:
            result = await self.categorization_flow_state['future']
            logger.info(f"UIManager: Categorization flow future resolved with result: {result}")
            return result
        except asyncio.CancelledError:
            logger.warning("UIManager: Categorization flow future was cancelled.")
            if 'future' in self.categorization_flow_state and \
               self.categorization_flow_state.get('future') and \
               not self.categorization_flow_state['future'].done():
                    self.categorization_flow_state.get('future').set_result({'action': 'cancel_execution', 'reason': 'future_cancelled_externally'})
            if 'future' in self.categorization_flow_state and self.categorization_flow_state.get('future'):
                return await self.categorization_flow_state.get('future')
            return {'action': 'cancel_execution', 'reason': 'future_cancelled_externally_no_future_obj'}
        finally:
            logger.debug(f"UIManager: Categorization flow finally block. Active: {self.categorization_flow_active}")
            self.categorization_flow_active = False
            logger.info("UIManager: Categorization flow ended and self.categorization_flow_active set to False.")

    def _ask_step_0_5_confirm_command_base(self):
        append_output_func = self.append_output
        proposed = self.categorization_flow_state['command_initially_proposed']
        original = self.categorization_flow_state['original_direct_input']
        logger.debug(f"UIManager._ask_step_0_5: Proposed='{proposed}', Original='{original}'")

        if original and original.strip() != proposed.strip():
            append_output_func(f"\nSystem processed to: '{proposed}'\nOriginal input was: '{original}'", style_class='categorize-info')
            append_output_func(f"Which version to categorize?\n  1: Processed ('{proposed}')\n  2: Original ('{original}')\n  3: Modify/Enter new command\n  4: Cancel categorization", style_class='categorize-prompt')
            self.set_flow_input_mode(
                prompt_text="[Categorize] Choice (1-4): ",
                accept_handler_func=self._handle_step_0_5_response,
                is_categorization=True
            )
        else:
            logger.debug("UIManager._ask_step_0_5: No difference or no original, skipping to step 1.")
            self.categorization_flow_state['command_to_add_final'] = proposed
            self.categorization_flow_state['step'] = 1
            self._ask_step_1_main_action()

    def _handle_step_0_5_response(self, buff):
        append_output_func = self.append_output
        response = buff.text.strip()
        proposed = self.categorization_flow_state['command_initially_proposed']
        original = self.categorization_flow_state['original_direct_input']
        future_to_set = self.categorization_flow_state.get('future')
        logger.debug(f"UIManager._handle_step_0_5: Response='{response}'")

        valid_choice = False
        if response == '1':
            self.categorization_flow_state['command_to_add_final'] = proposed
            append_output_func(f"Using processed: '{proposed}'", style_class='categorize-info')
            self.categorization_flow_state['step'] = 1
            self._ask_step_1_main_action()
            valid_choice = True
        elif response == '2' and original:
            self.categorization_flow_state['command_to_add_final'] = original
            append_output_func(f"Using original: '{original}'", style_class='categorize-info')
            self.categorization_flow_state['step'] = 1
            self._ask_step_1_main_action()
            valid_choice = True
        elif response == '3':
            self.categorization_flow_state['step'] = 3.5
            self._ask_step_3_5_enter_custom_command_for_categorization()
            valid_choice = True
        elif response == '4':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel_execution'})
            valid_choice = True

        if not valid_choice:
            append_output_func("Invalid choice (1-4). Please try again.", style_class='error')
            self._ask_step_0_5_confirm_command_base()
            return

    def _ask_step_1_main_action(self):
        append_output_func = self.append_output
        cmd_display = self.categorization_flow_state['command_to_add_final']
        default_cat_name = self.config['behavior']['default_category_for_unclassified']
        logger.debug(f"UIManager._ask_step_1_main_action: Command for categorization: '{cmd_display}'")
        append_output_func(f"\nCommand to categorize: '{cmd_display}'", style_class='categorize-info')
        append_output_func(f"How to categorize this command?\n  1: simple             ({CM_CATEGORY_DESCRIPTIONS['simple']})\n  2: semi_interactive   ({CM_CATEGORY_DESCRIPTIONS['semi_interactive']})\n  3: interactive_tui    ({CM_CATEGORY_DESCRIPTIONS['interactive_tui']})\n  M: Modify command before categorizing\n  D: Execute as default '{default_cat_name}' (once, no save)\n  C: Cancel categorization & execution", style_class='categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] Action (1-3/M/D/C): ",
            accept_handler_func=self._handle_step_1_main_action_response,
            is_categorization=True
        )

    def _handle_step_1_main_action_response(self, buff):
        append_output_func = self.append_output
        response = buff.text.strip().lower()
        cmd_to_add = self.categorization_flow_state['command_to_add_final']
        future_to_set = self.categorization_flow_state.get('future')
        logger.debug(f"UIManager._handle_step_1_main_action_response: Response='{response}'")
        valid_choice = False

        if response in ['1', '2', '3']:
            chosen_category = CM_CATEGORY_MAP.get(response)
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category})
            valid_choice = True
        elif response == 'm':
            self.categorization_flow_state['step'] = 4
            self._ask_step_4_enter_modified_command(base_command=cmd_to_add)
            valid_choice = True
        elif response == 'd':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_as_default'})
            valid_choice = True
        elif response == 'c':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel_execution'})
            valid_choice = True

        if not valid_choice:
            append_output_func("Invalid choice. Please enter 1-3, M, D, or C.", style_class='error')
            self._ask_step_1_main_action()
            return

    def _ask_step_3_5_enter_custom_command_for_categorization(self):
        logger.debug("UIManager: Asking user to enter custom command for categorization.")
        self.append_output("\nEnter the new command string you want to categorize:", style_class='categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] New command: ",
            accept_handler_func=self._handle_step_3_5_response,
            is_categorization=True
        )

    def _handle_step_3_5_response(self, buff):
        logger.debug(f"UIManager: Handling custom command input: '{buff.text}'")
        custom_command = buff.text.strip()
        if not custom_command:
            self.append_output("⚠️ Command cannot be empty.", style_class='warning')
            self._ask_step_3_5_enter_custom_command_for_categorization()
            return
        self.categorization_flow_state['command_to_add_final'] = custom_command
        self.append_output(f"New command for categorization: '{custom_command}'", style_class='categorize-info')
        self.categorization_flow_state['step'] = 1
        self._ask_step_1_main_action()

    def _ask_step_4_enter_modified_command(self, base_command: str):
        logger.debug(f"UIManager: Asking user to modify command. Base: '{base_command}'")
        self.append_output(f"\nCurrent command: '{base_command}'\nEnter your modified command below:", style_class='categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] Modified Cmd: ",
            accept_handler_func=self._handle_step_4_modified_command_response,
            is_categorization=True
        )
        if self.input_field:
            self.input_field.buffer.text = base_command
            self.input_field.buffer.cursor_position = len(base_command)

    def _handle_step_4_modified_command_response(self, buff):
        logger.debug(f"UIManager: Handling modified command input: '{buff.text}'")
        modified_command = buff.text.strip()
        if not modified_command:
            self.append_output("⚠️ Modified command cannot be empty. Using previous.", style_class='warning')
        else:
            self.categorization_flow_state['command_to_add_final'] = modified_command
        self.categorization_flow_state['step'] = 4.5
        self._ask_step_4_5_category_for_modified()

    def _ask_step_4_5_category_for_modified(self):
        cmd_to_categorize = self.categorization_flow_state['command_to_add_final']
        logger.debug(f"UIManager: Asking category for modified/final command: '{cmd_to_categorize}'")
        self.append_output(f"\nCategory for command: '{cmd_to_categorize}'", style_class='categorize-info')
        self.append_output(f"  1: simple             ({CM_CATEGORY_DESCRIPTIONS['simple']})\n  2: semi_interactive   ({CM_CATEGORY_DESCRIPTIONS['semi_interactive']})\n  3: interactive_tui    ({CM_CATEGORY_DESCRIPTIONS['interactive_tui']})", style_class='categorize-prompt')
        self.set_flow_input_mode(
            prompt_text="[Categorize] Category (1-3): ",
            accept_handler_func=self._handle_step_4_5_response,
            is_categorization=True
        )

    def _handle_step_4_5_response(self, buff):
        logger.debug(f"UIManager: Handling category choice for modified command: '{buff.text}'")
        response = buff.text.strip()
        chosen_category = CM_CATEGORY_MAP.get(response)
        future_to_set = self.categorization_flow_state.get('future')
        cmd_to_add = self.categorization_flow_state['command_to_add_final']

        if chosen_category:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category})
        else:
            self.append_output("Invalid category. Please enter 1, 2, or 3.", style_class='error')
            self._ask_step_4_5_category_for_modified()
            return

    # --- Command Confirmation Flow Methods ---
    async def prompt_for_command_confirmation(self, command_to_confirm: str, display_source: str, normal_input_accept_handler_ref) -> dict:
        """Initiates the interactive flow for confirming an AI-generated command.

        This is an async method that awaits user input.

        Args:
            command_to_confirm: The command string to be confirmed.
            display_source: The source of the command (e.g., '/ai query').
            normal_input_accept_handler_ref: A reference to the normal input handler.

        Returns:
            A dictionary with the user's choice, e.g., {'action': 'execute'}. """
        logger.info(f"UIManager: Starting command confirmation flow for '{command_to_confirm}' from '{display_source}'.")
        self.confirmation_flow_active = True
        self.categorization_flow_active = False
        self.is_in_edit_mode = False
        self.confirmation_flow_state = {
            'command_to_confirm': command_to_confirm,
            'original_command': command_to_confirm,
            'display_source': display_source,
            'step': 'ask_main_choice',
            'future': asyncio.Future(),
            'normal_input_accept_handler_ref': normal_input_accept_handler_ref
        }

        self._ask_confirmation_main_choice()

        action_taken = None
        try:
            result = await self.confirmation_flow_state['future']
            action_taken = result.get('action')
            logger.info(f"UIManager: Confirmation flow future resolved with: {result}")
            return result
        except asyncio.CancelledError:
            logger.warning("UIManager: Confirmation flow future was cancelled.")
            if 'future' in self.confirmation_flow_state and \
               self.confirmation_flow_state.get('future') and \
               not self.confirmation_flow_state['future'].done():
                    self.confirmation_flow_state.get('future').set_result({'action': 'cancel', 'reason': 'future_cancelled_externally'})
            if 'future' in self.confirmation_flow_state and self.confirmation_flow_state.get('future'):
                return await self.confirmation_flow_state.get('future')
            return {'action': 'cancel', 'reason': 'future_cancelled_externally_no_future_obj'}
        finally:
            logger.debug(f"UIManager: Confirmation flow finally block. Active: {self.confirmation_flow_active}")
            self.confirmation_flow_active = False
            if action_taken == 'edit_mode_engaged':
                command_for_edit = self.confirmation_flow_state.get('command_to_confirm', '')
                accept_handler = self.confirmation_flow_state.get('normal_input_accept_handler_ref')
                if accept_handler:
                    self.set_edit_mode(accept_handler, command_for_edit)
                else:
                    logger.error("UIManager: normal_input_accept_handler_ref not available for edit mode.")
            logger.info("UIManager: Confirmation flow ended and self.confirmation_flow_active set to False.")


    def _ask_confirmation_main_choice(self):
        cmd = self.confirmation_flow_state['command_to_confirm']
        source = self.confirmation_flow_state['display_source']
        
        self.append_output(f"\n🤖 AI proposed command (from: {source}):", style_class='ai-query')
        self.append_output(f"    👉 {cmd}", style_class='executing')
        self.append_output("Action: [1] Yes (Exec, prompt if new) | [2] Simple & Run | [3] Semi-Interactive & Run | [4] TUI & Run | [5] Explain | [6] Modify | [7] Cancel?", style_class='categorize-prompt')

        self.set_flow_input_mode(
            prompt_text="[Confirm AI Cmd] Choice (1-7): ",
            accept_handler_func=self._handle_confirmation_main_choice_response,
            is_confirmation=True
        )

    def _handle_confirmation_main_choice_response(self, buff):
        response = buff.text.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        cmd_to_confirm = self.confirmation_flow_state['command_to_confirm']
        valid_choice_made = False

        logger.debug(f"UIManager: Confirmation main choice response: '{response}'")

        if response in ['1', 'y', 'yes']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response == '2':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'simple'})
            valid_choice_made = True
        elif response == '3':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'semi_interactive'})
            valid_choice_made = True
        elif response == '4':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'interactive_tui'})
            valid_choice_made = True
        elif response in ['5', 'e', 'explain']:
            self.confirmation_flow_state['step'] = 'explain'
            asyncio.create_task(self._handle_explain_command_async())
            valid_choice_made = True
        elif response in ['6', 'm', 'modify']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'edit_mode_engaged', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response in ['7', 'c', 'cancel', 'n', 'no']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel'})
            valid_choice_made = True

        if not valid_choice_made:
            self.append_output("Invalid choice. Please enter a number from 1 to 7.", style_class='error')
            self._ask_confirmation_main_choice()
            return

    async def _handle_explain_command_async(self):
        command_to_explain = self.confirmation_flow_state['command_to_confirm']
        self.append_output(f"\n🧠 Asking AI to explain: {command_to_explain}", style_class='ai-thinking')

        if self.app and hasattr(self.app, 'is_running') and self.app.is_running:
            self.app.invalidate()

        explanation = await explain_linux_command_with_ai(command_to_explain, self.config, self.append_output)

        if explanation:
            self.append_output("\n💡 AI Explanation:", style_class='info-header')
            self.append_output(explanation, style_class='info')
        else:
            self.append_output("⚠️ AI could not provide an explanation.", style_class='warning')

        self._ask_confirmation_after_explain()

    def _ask_confirmation_after_explain(self):
        cmd = self.confirmation_flow_state['command_to_confirm']
        self.append_output(f"\nCommand to consider: {cmd}", style_class='executing')
        self.append_output("Action: [1] Yes (Exec, prompt if new) | [2] Simple & Run | [3] Semi-Interactive & Run | [4] TUI & Run | [5] Modify | [6] Cancel?", style_class='categorize-prompt')

        self.set_flow_input_mode(
            prompt_text="[Confirm AI Cmd] Choice (1-6): ",
            accept_handler_func=self._handle_confirmation_after_explain_response,
            is_confirmation=True
        )

    def _handle_confirmation_after_explain_response(self, buff):
        response = buff.text.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        cmd_to_confirm = self.confirmation_flow_state['command_to_confirm']
        valid_choice_made = False
        logger.debug(f"UIManager: Confirmation after explain response: '{response}'")

        if response in ['1', 'y', 'yes']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response == '2':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'simple'})
            valid_choice_made = True
        elif response == '3':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'semi_interactive'})
            valid_choice_made = True
        elif response == '4':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'interactive_tui'})
            valid_choice_made = True
        elif response in ['5', 'm', 'modify']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'edit_mode_engaged', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response in ['6', 'c', 'cancel', 'n', 'no']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel'})
            valid_choice_made = True

        if not valid_choice_made:
            self.append_output("Invalid choice. Please enter a number from 1 to 6.", style_class='error')
            self._ask_confirmation_after_explain()
            return

    # --- Core UI Methods ---
    def get_app_instance(self):
        """Returns the application instance if set by the main program."""
        if not self.app:
            logger.debug("UIManager.get_app_instance: self.app is not yet set by the main application.")
        return self.app

    def _get_current_prompt(self) -> str:
        return self.current_prompt_text

    def initialize_ui_elements(self, initial_prompt_text: str, history: FileHistory, output_buffer_main: list) -> Layout:
        """Creates all the prompt_toolkit widgets and constructs the main UI layout.

        Args:
            initial_prompt_text: The text for the very first input prompt.
            history: The history object for the input field.
            output_buffer_main: A list of (style, text) tuples for initial output.

        Returns:
            The main prompt_toolkit Layout object for the application. """
        logger.info("UIManager: Initializing UI elements...")
        key_help_text_content = "Ctrl+N: Newline | Enter: Submit | Ctrl+C/D: Exit/Cancel | Tab: Complete/Indent | ↑/↓: History/Lines | PgUp/PgDn: Scroll"
        self.style = Style.from_dict({
            'output-field': 'bg:#282c34 #abb2bf', 'input-field': 'bg:#21252b #d19a66',
            'key-help': 'bg:#282c34 #5c6370', 'line': '#3e4451',
            'prompt': 'bg:#21252b #61afef', 'scrollbar.background': 'bg:#282c34',
            'scrollbar.button': 'bg:#3e4451', 'default': '#abb2bf',
            'status-bar': 'bg:#282c34 #abb2bf',
            'status-bar.thinking': 'bg:#282c34 #56b6c2',
            'welcome': 'bold #86c07c', 'info': '#61afef',
            'info-header': 'bold #61afef', 'info-subheader': 'underline #61afef',
            'info-item': '#abb2bf', 'info-item-empty': 'italic #5c6370',
            'success': '#98c379', 'error': '#e06c75',
            'warning': '#d19a66', 'security-critical': 'bold #e06c75 bg:#5c0000',
            'security-warning': '#e06c75', 'ai-query': '#c678dd',
            'ai-thinking': 'italic #56b6c2', 'ai-thinking-detail': 'italic #4b8e97',
            'ai-response': '#56b6c2', 'ai-unsafe': 'bold #e06c75',
            'executing': 'bold #61afef', 'categorize-info': '#abb2bf',
            'categorize-prompt': 'bold #d19a66', 'help-base': '#abb2bf',
            'help-title': 'bold underline #e5c07b', 'help-text': '#abb2bf',
            'help-header': 'bold #61afef', 'help-command': '#c678dd',
            'help-description': '#abb2bf', 'help-example': 'italic #5c6370',
            'output-separator': '#5c6370',
            'startup-separator': 'bold #86c07c'
        })
        self.output_buffer = list(output_buffer_main)
        # Log initial buffer content if any
        for style, content in self.output_buffer:
            logger.info(f"UI_OUTPUT_INITIAL_BUFFER: {content.strip()}")


        self.output_field = TextArea(
            text="".join([text_content for _, text_content in self.output_buffer]),
            style='class:output-field', scrollbar=True, focusable=False,
            wrap_lines=True, read_only=True
        )
        self.current_prompt_text = initial_prompt_text
        self.input_field = TextArea(
            prompt=self._get_current_prompt,
            style='class:input-field',
            multiline=self.config.get('behavior', {}).get('input_field_height', 3) > 1,
            wrap_lines=False, history=history,
            height=self.config.get('behavior', {}).get('input_field_height', 3)
        )
        self.key_help_field = Window(
            content=FormattedTextControl(key_help_text_content),
            height=1, style='class:key-help'
        )
        self.status_bar = Window(
            content=self.status_bar_control,
            height=1,
            style='class:status-bar'
        )
        layout_components = [
            self.output_field, 
            self.status_bar,
            Window(height=1, char='─', style='class:line'),
            self.input_field, 
            self.key_help_field
        ]
        self.root_container = HSplit(layout_components)
        self.layout = Layout(self.root_container, focused_element=self.input_field)
        if self.output_field and self.output_field.buffer:
            self.output_field.buffer.on_cursor_position_changed += self._on_output_cursor_pos_changed
        logger.info("UIManager: UI elements fully initialized.")
        return self.layout

    def update_status_bar(self, text: str, style: str = 'class:status-bar'):
        self.status_bar_control.text = text
        self.status_bar.style = style
        if self.app:
            self.app.invalidate()

    def _on_output_cursor_pos_changed(self, _=None):
        if self.categorization_flow_active or self.confirmation_flow_active or self.api_input_flow_active or self.is_in_edit_mode:
            if self.output_field and self.output_field.buffer:
                self.output_field.buffer.cursor_position = len(self.output_field.buffer.text)
            return
        if not (self.output_field and self.output_field.window and self.output_field.window.render_info):
            return
        doc = self.output_field.buffer.document
        render_info = self.output_field.window.render_info
        
        if not render_info: return
        if doc.line_count <= render_info.window_height:
            if not self.auto_scroll: self.auto_scroll = True
            return
        is_scrolled_up = doc.cursor_position_row < (doc.line_count - render_info.window_height + 1)
        if is_scrolled_up:
            if self.auto_scroll: self.auto_scroll = False
        else:
            if not self.auto_scroll: self.auto_scroll = True

    def append_output(self, text: str, style_class: str = 'default', internal_call: bool = False):
        """The primary method for adding text to the main output field."""
        # Log the text that is about to be appended to the UI output field
        # Strip trailing newline for cleaner logs, as append_output ensures it later.
        logger.info(f"UI_OUTPUT: {text.rstrip()}")

        if not self.output_field:
            logger.warning("UIManager.append_output called, but output_field is not initialized. Buffering message.")
            if not text.endswith('\n'): text += '\n'
            self.output_buffer.append((style_class, text))
            return

        if not text.endswith('\n'): text += '\n'
        
        self.output_buffer.append((style_class, text))

        # --- NEW LOGIC: Enforce buffer size limit ---
        if len(self.output_buffer) > self.max_output_buffer_lines:
            # Remove from the beginning of the buffer to maintain size
            # A simple heuristic might be to remove a block of lines, or just one-by-one.
            # Removing a block (e.g., 10% of max_output_buffer_lines) when over limit
            # can be more efficient than removing one-by-one frequently.
            lines_to_remove = len(self.output_buffer) - self.max_output_buffer_lines + (self.max_output_buffer_lines // 10)
            self.output_buffer = self.output_buffer[lines_to_remove:]
            logger.debug(f"Output buffer trimmed. New size: {len(self.output_buffer)} lines.")
        # --- END NEW LOGIC ---

        plain_text_output = "".join([content for _, content in self.output_buffer])
        
        buffer = self.output_field.buffer
        current_cursor_pos = buffer.cursor_position # Store cursor position before updating document
        
        # This line is the core of the re-rendering.
        buffer.set_document(Document(plain_text_output, cursor_position=len(plain_text_output)), bypass_readonly=True)
        
        if self.auto_scroll or self.categorization_flow_active or self.confirmation_flow_active or self.api_input_flow_active or self.is_in_edit_mode:
            buffer.cursor_position = len(plain_text_output)
        else:
            # Restore previous cursor position if not auto-scrolling
            buffer.cursor_position = min(current_cursor_pos, len(plain_text_output))

        if not internal_call:
            self.last_output_was_separator = False

        if self.app: 
            if hasattr(self.app, 'invalidate'):
                try:
                    if hasattr(self.app, 'is_running') and self.app.is_running:
                        logger.debug("UIManager.append_output: Invalidating running app.")
                        self.app.invalidate()
                    elif not hasattr(self.app, 'is_running'): 
                        logger.debug("UIManager.append_output: self.app is set but no is_running, attempting invalidate.")
                        self.app.invalidate()
                    else: 
                        logger.debug("UIManager.append_output: self.app is set but not running. Invalidation skipped.")
                except Exception as e:
                    logger.error(f"Error during app invalidation: {e}", exc_info=True)
            else:
                logger.debug("UIManager.append_output: self.app object present but lacks invalidate method.")
        else:
            logger.debug("UIManager.append_output: self.app not set. Invalidation skipped.")


    def add_interaction_separator(self):
        if not self.config.get("ui", {}).get("enable_output_separator", True):
            return
        if self.last_output_was_separator:
            logger.debug("Skipping interaction separator: last output was already a separator.")
            return
        if not self.output_buffer:
            logger.debug("Skipping interaction separator: output buffer is empty.")
            return

        separator_char = self.config.get("ui", {}).get("output_separator_character", "─")
        separator_length = self.config.get("ui", {}).get("output_separator_length", 30)
        separator_string = separator_char * separator_length
        
        add_leading_newline = True
        if self.output_buffer:
            last_text_content = self.output_buffer[-1][1]
            if last_text_content.strip() == "" or last_text_content.endswith("\n\n"):
                add_leading_newline = False
        
        full_separator_text = f"\n{separator_string}\n\n" if add_leading_newline else f"{separator_string}\n"
        
        logger.debug(f"Adding interaction separator: '{separator_string}'")
        self.append_output(full_separator_text, style_class='output-separator', internal_call=True)
        self.last_output_was_separator = True

    def add_startup_separator(self):
        """Adds a visual separator after startup messages if enabled."""
        if not self.config.get("ui", {}).get("enable_startup_separator", True):
            return
        if self.startup_separator_added:
            logger.debug("Skipping startup separator: already added.")
            return
        
        separator_string = self.config.get("ui", {}).get("startup_separator_string", "🚀 micro_X Initialized & Ready 🚀")
        
        add_leading_newline = True
        if self.output_buffer:
            last_text_content = self.output_buffer[-1][1]
            if last_text_content.strip() == "" or last_text_content.endswith("\n\n"):
                add_leading_newline = False

        full_separator_text = f"\n{separator_string}\n" if add_leading_newline else f"{separator_string}\n"

        logger.debug(f"Adding startup separator: '{separator_string}'")
        self.append_output(full_separator_text, style_class='startup-separator', internal_call=True)
        self.startup_separator_added = True
        self.last_output_was_separator = True


    def update_input_prompt(self, current_directory_path: str):
        """Updates the text of the input prompt, typically with the current directory."""
        if not self.input_field: return
        home_dir = os.path.expanduser("~")
        max_prompt_len = self.config.get('ui', {}).get('max_prompt_length', 20)
        dir_for_prompt: str
        if current_directory_path == home_dir: dir_for_prompt = "~"
        elif current_directory_path.startswith(home_dir + os.sep):
            relative_path = current_directory_path[len(home_dir)+1:]
            full_rel_prompt = "~/" + relative_path
            if len(full_rel_prompt) <= max_prompt_len: dir_for_prompt = full_rel_prompt
            else:
                chars_to_keep_at_end = max_prompt_len - (len("~/") + 3) 
                dir_for_prompt = "~/" + "..." + relative_path[-chars_to_keep_at_end:] if chars_to_keep_at_end > 0 else "~/..."
        else:
            path_basename = os.path.basename(current_directory_path)
            if len(path_basename) <= max_prompt_len: dir_for_prompt = path_basename
            else:
                chars_to_keep_at_end = max_prompt_len - 3 
                dir_for_prompt = "..." + path_basename[-chars_to_keep_at_end:] if chars_to_keep_at_end > 0 else "..."
        self.current_prompt_text = f"({dir_for_prompt}) > "
        if self.app and hasattr(self.app, 'invalidate'): 
            if self.layout and self.input_field: self.app.layout.focus(self.input_field)
            self.app.invalidate()

    def set_normal_input_mode(self, accept_handler_func: callable, current_directory_path: str):
        """Resets the UI to the default state for normal command input."""
        logger.debug("UIManager: Setting normal input mode.")
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.is_in_edit_mode = False
        self.update_input_prompt(current_directory_path)
        if self.input_field:
            self.input_field.multiline = self.config.get('behavior', {}).get('input_field_height', 3) > 1
            self.input_field.buffer.accept_handler = accept_handler_func
            self.input_field.buffer.reset()
            if self.app and hasattr(self.app, 'invalidate'):
                if self.layout: self.app.layout.focus(self.input_field)
                self.app.invalidate()

    def set_flow_input_mode(self, prompt_text: str, accept_handler_func: callable, is_categorization: bool = False, is_confirmation: bool = False, is_api_input: bool = False):
        """Sets the UI for a special input flow (categorization, confirmation, or API)."""
        logger.debug(f"UIManager: Setting flow input mode. Prompt: '{prompt_text}'")
        if is_categorization:
            self.categorization_flow_active = True
            self.confirmation_flow_active = False
            self.api_input_flow_active = False
            self.is_in_edit_mode = False
            self.append_output("ℹ️ Interaction active. Scrolling disabled until flow completes.", style_class='info', internal_call=True)
        elif is_confirmation:
            self.confirmation_flow_active = True
            self.categorization_flow_active = False
            self.api_input_flow_active = False
            self.is_in_edit_mode = False
            self.append_output("ℹ️ Interaction active. Scrolling disabled until flow completes.", style_class='info', internal_call=True)
        elif is_api_input:
            self.api_input_flow_active = True
            self.categorization_flow_active = False
            self.confirmation_flow_active = False
            self.is_in_edit_mode = False
            self.append_output("ℹ️ Script is requesting input. Scrolling disabled.", style_class='info', internal_call=True)

        self.current_prompt_text = prompt_text
        if self.input_field:
            self.input_field.multiline = False 
            self.input_field.buffer.accept_handler = accept_handler_func
            self.input_field.buffer.reset()
            if self.app and hasattr(self.app, 'invalidate'):
                if self.layout: self.app.layout.focus(self.input_field)
                self.app.invalidate()

    def set_edit_mode(self, accept_handler_func: callable, command_to_edit: str):
        """Sets the UI to allow editing a command, populating the input field."""
        logger.debug(f"UIManager: Setting edit mode. Command: '{command_to_edit}'")
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.is_in_edit_mode = True
        self.current_prompt_text = "[Edit Command]> "
        self.append_output("ℹ️ Edit mode active. Scrolling disabled until command submitted/cancelled.", style_class='info', internal_call=True) # Added hint
        if self.input_field:
            self.input_field.multiline = self.config.get('behavior', {}).get('input_field_height', 3) > 1
            self.input_field.buffer.accept_handler = accept_handler_func
            self.input_field.buffer.document = Document(
                text=command_to_edit,
                cursor_position=len(command_to_edit)
            )
            logger.info(f"UIManager: Input buffer set to '{command_to_edit}' for editing.")
            if self.app and hasattr(self.app, 'invalidate'):
                if self.layout: self.app.layout.focus(self.input_field)
                self.app.invalidate()