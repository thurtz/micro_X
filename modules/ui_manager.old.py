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
    def __init__(self, config):
        self.config = config
        self.app = None # This will be set by main.py
        self.output_field = None
        self.input_field = None
        self.key_help_field = None
        self.root_container = None
        self.layout = None
        self.style = None
        self.auto_scroll = True
        self.output_buffer = []

        self.categorization_flow_active = False
        self.categorization_flow_state = {}

        self.confirmation_flow_active = False
        self.confirmation_flow_state = {}

        self.is_in_edit_mode = False

        self.current_prompt_text = ""

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
        def _handle_exit_or_cancel(event):
            if self.categorization_flow_active:
                self.append_output("\n⚠️ Categorization cancelled by user.", style_class='warning')
                logger.info("Categorization flow cancelled by Ctrl+C/D.")
                if 'future' in self.categorization_flow_state and \
                   self.categorization_flow_state.get('future') and \
                   not self.categorization_flow_state['future'].done():
                    self.categorization_flow_state['future'].set_result({'action': 'cancel_execution'})
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()
                event.app.invalidate()
            elif self.confirmation_flow_active:
                self.append_output("\n⚠️ Command confirmation cancelled by user.", style_class='warning')
                logger.info("Confirmation flow cancelled by Ctrl+C/D.")
                if 'future' in self.confirmation_flow_state and \
                   self.confirmation_flow_state.get('future') and \
                   not self.confirmation_flow_state['future'].done():
                    self.confirmation_flow_state['future'].set_result({'action': 'cancel'})
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()
                event.app.invalidate()
            elif self.is_in_edit_mode:
                self.append_output("\n⌨️ Command editing cancelled.", style_class='info')
                logger.info("Command edit mode cancelled by Ctrl+C/D.")
                self.is_in_edit_mode = False
                if self.main_restore_normal_input_ref: self.main_restore_normal_input_ref()
                event.app.invalidate()
            else:
                logger.info("Exit keybinding triggered.")
                if self.main_exit_app_ref:
                    self.main_exit_app_ref()
                else:
                    event.app.exit()


        @self.kb.add('c-n')
        def _handle_newline(event):
            if not self.categorization_flow_active and \
               not self.confirmation_flow_active and \
               not self.is_in_edit_mode:
                if self.input_field and self.input_field.multiline:
                    event.current_buffer.insert_text('\n')
            elif self.input_field and self.input_field.multiline and self.is_in_edit_mode:
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
            if not self.categorization_flow_active and not self.confirmation_flow_active:
                event.current_buffer.cursor_up(count=1)

        @self.kb.add('c-down')
        def _handle_ctrl_down(event):
            if not self.categorization_flow_active and not self.confirmation_flow_active:
                event.current_buffer.cursor_down(count=1)

        @self.kb.add('up')
        def _handle_up_arrow(event):
            if self.categorization_flow_active or self.confirmation_flow_active:
                pass

            buff = event.current_buffer
            doc = buff.document
            if doc.cursor_position_row == 0:
                if buff.history_backward():
                    buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                    event.app.invalidate()
            else:
                buff.cursor_up()

        @self.kb.add('down')
        def _handle_down_arrow(event):
            if self.categorization_flow_active or self.confirmation_flow_active:
                pass

            buff = event.current_buffer
            doc = buff.document
            if doc.cursor_position_row == doc.line_count - 1:
                if buff.history_forward():
                    buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                    event.app.invalidate()
            else:
                buff.cursor_down()

        logger.debug("UIManager: Keybindings registered.")

    def get_key_bindings(self) -> KeyBindings:
        return self.kb

    # --- Categorization Flow Methods ---
    async def start_categorization_flow(self, command_initially_proposed: str,
                                        ai_raw_candidate: str | None,
                                        original_direct_input: str | None
                                        ):
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
               not self.confirmation_flow_state.get('future').done():
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
        self.append_output("Action: [Y]es (Exec, prompt if new) | [Ys] Simple & Run | [Ym] Semi-Interactive & Run | [Yi] TUI & Run | [E]xplain | [M]odify | [C]ancel?", style_class='categorize-prompt')

        self.set_flow_input_mode(
            prompt_text="[Confirm AI Cmd] Choice (Y/Ys/Ym/Yi/E/M/C): ",
            accept_handler_func=self._handle_confirmation_main_choice_response,
            is_confirmation=True
        )

    def _handle_confirmation_main_choice_response(self, buff):
        response = buff.text.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        cmd_to_confirm = self.confirmation_flow_state['command_to_confirm']
        valid_choice_made = False

        logger.debug(f"UIManager: Confirmation main choice response: '{response}'")

        if response in ['y', 'yes']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response == 'ys':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'simple'})
            valid_choice_made = True
        elif response == 'ym':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'semi_interactive'})
            valid_choice_made = True
        elif response == 'yi':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'interactive_tui'})
            valid_choice_made = True
        elif response in ['e', 'explain']:
            self.confirmation_flow_state['step'] = 'explain'
            asyncio.create_task(self._handle_explain_command_async())
            valid_choice_made = True
        elif response in ['m', 'modify']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'edit_mode_engaged', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response in ['c', 'cancel', 'n', 'no']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel'})
            valid_choice_made = True

        if not valid_choice_made:
            self.append_output("Invalid choice. Please enter Y, Ys, Ym, Yi, E, M, or C.", style_class='error')
            self._ask_confirmation_main_choice()
            return

    async def _handle_explain_command_async(self):
        command_to_explain = self.confirmation_flow_state['command_to_confirm']
        self.append_output(f"\n🧠 Asking AI to explain: {command_to_explain}", style_class='ai-thinking')

        # current_app_inst = self.get_app_instance() # Not needed here if only appending
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
        self.append_output("Action: [Y]es (Exec, prompt if new) | [Ys] Simple & Run | [Ym] Semi-Interactive & Run | [Yi] TUI & Run | [M]odify | [C]ancel?", style_class='categorize-prompt')

        self.set_flow_input_mode(
            prompt_text="[Confirm AI Cmd] Choice (Y/Ys/Ym/Yi/M/C): ",
            accept_handler_func=self._handle_confirmation_after_explain_response,
            is_confirmation=True
        )

    def _handle_confirmation_after_explain_response(self, buff):
        response = buff.text.strip().lower()
        future_to_set = self.confirmation_flow_state.get('future')
        cmd_to_confirm = self.confirmation_flow_state['command_to_confirm']
        valid_choice_made = False
        logger.debug(f"UIManager: Confirmation after explain response: '{response}'")

        if response in ['y', 'yes']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response == 'ys':
                 if future_to_set and not future_to_set.done():
                    future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'simple'})
                 valid_choice_made = True
        elif response == 'ym':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'semi_interactive'})
            valid_choice_made = True
        elif response == 'yi':
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'execute_and_categorize', 'command': cmd_to_confirm, 'category': 'interactive_tui'})
            valid_choice_made = True
        elif response in ['m', 'modify']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'edit_mode_engaged', 'command': cmd_to_confirm})
            valid_choice_made = True
        elif response in ['c', 'cancel', 'n', 'no']:
            if future_to_set and not future_to_set.done():
                future_to_set.set_result({'action': 'cancel'})
            valid_choice_made = True

        if not valid_choice_made:
            self.append_output("Invalid choice. Please enter Y, Ys, Ym, Yi, M, or C.", style_class='error')
            self._ask_confirmation_after_explain()
            return

    # --- Core UI Methods ---
    def get_app_instance(self):
        """Returns the application instance if set by the main program."""
        # self.app is set by main.py after Application is instantiated.
        if not self.app:
            logger.debug("UIManager.get_app_instance: self.app is not yet set by the main application.")
        return self.app

    def _get_current_prompt(self) -> str:
        return self.current_prompt_text

    def initialize_ui_elements(self, initial_prompt_text: str, history: FileHistory, output_buffer_main: list):
        logger.info("UIManager: Initializing UI elements...")
        key_help_text_content = "Ctrl+N: Newline | Enter: Submit | Ctrl+C/D: Exit/Cancel | Tab: Complete/Indent | ↑/↓: History/Lines | PgUp/PgDn: Scroll"
        self.style = Style.from_dict({
            'output-field': 'bg:#282c34 #abb2bf', 'input-field': 'bg:#21252b #d19a66',
            'key-help': 'bg:#282c34 #5c6370', 'line': '#3e4451',
            'prompt': 'bg:#21252b #61afef', 'scrollbar.background': 'bg:#282c34',
            'scrollbar.button': 'bg:#3e4451', 'default': '#abb2bf',
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
        layout_components = [
            self.output_field, Window(height=1, char='─', style='class:line'),
            self.input_field, self.key_help_field
        ]
        self.root_container = HSplit(layout_components)
        self.layout = Layout(self.root_container, focused_element=self.input_field)
        if self.output_field and self.output_field.buffer:
            self.output_field.buffer.on_cursor_position_changed += self._on_output_cursor_pos_changed
        logger.info("UIManager: UI elements fully initialized.")
        return self.layout

    def _on_output_cursor_pos_changed(self, _=None):
        if self.categorization_flow_active or self.confirmation_flow_active or self.is_in_edit_mode:
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
        if not self.output_field:
            logger.warning("UIManager.append_output called, but output_field is not initialized. Buffering message.")
            if not text.endswith('\n'): text += '\n'
            self.output_buffer.append((style_class, text))
            return

        if not text.endswith('\n'): text += '\n'
        self.output_buffer.append((style_class, text))
        plain_text_output = "".join([content for _, content in self.output_buffer])
        
        buffer = self.output_field.buffer
        current_cursor_pos = buffer.cursor_position
        buffer.set_document(Document(plain_text_output, cursor_position=len(plain_text_output)), bypass_readonly=True)
        
        if self.auto_scroll or self.categorization_flow_active or self.confirmation_flow_active or self.is_in_edit_mode:
            buffer.cursor_position = len(plain_text_output)
        else:
            buffer.cursor_position = min(current_cursor_pos, len(plain_text_output))

        if not internal_call:
            self.last_output_was_separator = False

        # Directly use self.app for invalidation, only if it's set and the app is running
        if self.app: # Check if self.app has been set by main.py
            # Check if app is running (prompt_toolkit apps might not have is_running until run_async)
            # A simple check for invalidate method existing is safer before run_async
            if hasattr(self.app, 'invalidate'):
                try:
                    if hasattr(self.app, 'is_running') and self.app.is_running:
                        logger.debug("UIManager.append_output: Invalidating running app.")
                        self.app.invalidate()
                    elif not hasattr(self.app, 'is_running'): # App object exists but might not have is_running yet
                        logger.debug("UIManager.append_output: self.app is set but no is_running, attempting invalidate.")
                        self.app.invalidate()
                    else: # App has is_running but it's false
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
        # current_app_instance = self.get_app_instance() # Not strictly needed here if only changing text
        if self.app and hasattr(self.app, 'invalidate'): # Check if app exists and can be invalidated
            if self.layout and self.input_field: self.app.layout.focus(self.input_field)
            self.app.invalidate()

    def set_normal_input_mode(self, accept_handler_func, current_directory_path: str):
        logger.debug("UIManager: Setting normal input mode.")
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.is_in_edit_mode = False
        self.update_input_prompt(current_directory_path)
        if self.input_field:
            self.input_field.multiline = self.config.get('behavior', {}).get('input_field_height', 3) > 1
            self.input_field.buffer.accept_handler = accept_handler_func
            self.input_field.buffer.reset()
            # current_app_instance = self.get_app_instance()
            if self.app and hasattr(self.app, 'invalidate'):
                if self.layout: self.app.layout.focus(self.input_field)
                self.app.invalidate()

    def set_flow_input_mode(self, prompt_text: str, accept_handler_func, is_categorization: bool = False, is_confirmation: bool = False):
        logger.debug(f"UIManager: Setting flow input mode. Prompt: '{prompt_text}'")
        if is_categorization:
            self.categorization_flow_active = True
            self.confirmation_flow_active = False
            self.is_in_edit_mode = False
        elif is_confirmation:
            self.confirmation_flow_active = True
            self.categorization_flow_active = False
            self.is_in_edit_mode = False

        self.current_prompt_text = prompt_text
        if self.input_field:
            self.input_field.multiline = False
            self.input_field.buffer.accept_handler = accept_handler_func
            self.input_field.buffer.reset()
            # current_app_instance = self.get_app_instance()
            if self.app and hasattr(self.app, 'invalidate'):
                if self.layout: self.app.layout.focus(self.input_field)
                self.app.invalidate()

    def set_edit_mode(self, accept_handler_func, command_to_edit: str):
        logger.debug(f"UIManager: Setting edit mode. Command: '{command_to_edit}'")
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.is_in_edit_mode = True
        self.current_prompt_text = "[Edit Command]> "
        if self.input_field:
            self.input_field.multiline = self.config.get('behavior', {}).get('input_field_height', 3) > 1
            self.input_field.buffer.accept_handler = accept_handler_func
            self.input_field.buffer.document = Document(
                text=command_to_edit,
                cursor_position=len(command_to_edit)
            )
            logger.info(f"UIManager: Input buffer set to '{command_to_edit}' for editing.")
            # current_app_instance = self.get_app_instance()
            if self.app and hasattr(self.app, 'invalidate'):
                if self.layout: self.app.layout.focus(self.input_field)
                self.app.invalidate()
