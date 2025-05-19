#!/usr/bin/env python

import asyncio
import logging
from prompt_toolkit import Application, HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea # Still needed for input_field
from prompt_toolkit.styles import Style
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText, to_formatted_text

logger = logging.getLogger(__name__)

class UIManager:
    """
    Manages the user interface for micro_X using prompt_toolkit.
    Handles UI elements, layout, styling, keybindings, and UI-specific flows.
    """
    def __init__(self, config, history_object, initial_welcome_message, key_help_text_content):
        """
        Initializes the UIManager.

        Args:
            config (dict): The application configuration.
            history_object (FileHistory): The command history object.
            initial_welcome_message (str): The message to display in the output area on startup.
            key_help_text_content (str): The text for the key help bar.
        """
        self.config = config
        self.history = history_object
        self.key_help_text_content = key_help_text_content

        # Internal state
        self._output_buffer = []  # Stores (style_class, text) tuples for the output area
        self._auto_scroll_output = True
        self.app_instance = None # Will be the prompt_toolkit Application instance

        # Callbacks to be set by main.py
        self._on_input_submit_callback = None # For normal input submission
        self._on_exit_request_callback = None # For Ctrl+C/D to exit app
        # self._on_cancel_active_flow_callback = None # This was in the plan, but Ctrl+C handler directly manages flow futures.

        # Flow specific state - UI manager needs to know if its own flow is active
        self._categorization_ui_flow_active = False
        self._categorization_ui_flow_state = {}
        self._confirmation_ui_flow_active = False
        self._confirmation_ui_flow_state = {}

        # Initialize UI elements
        self._init_ui_elements(initial_welcome_message)
        self._init_keybindings()
        self._init_layout()
        self._init_style()

        # Create the Application instance
        self.app_instance = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True
        )
        # Attach output scroll handler (if applicable, FormattedTextControl doesn't have a buffer.on_cursor_position_changed)
        # For FormattedTextControl, scrolling is typically managed by the Window it's in.
        # We'll manage auto-scroll by adjusting the content and letting the Window handle scrolling.

    def _init_ui_elements(self, initial_welcome_message):
        """Initializes the TextArea and Window widgets."""
        if initial_welcome_message:
            # Ensure welcome message ends with a newline for consistent formatting
            msg = initial_welcome_message if initial_welcome_message.endswith('\n') else initial_welcome_message + '\n'
            self._output_buffer.append(('class:welcome', msg))

        # --- MODIFICATION: Output field now uses FormattedTextControl ---
        self.output_text_control = FormattedTextControl(
            text=self._build_formatted_output(), # Initial text
            focusable=False,
            # scrollbar=True, # Scrollbar is a property of the Window containing the control
        )
        self.output_field = Window(
            content=self.output_text_control,
            wrap_lines=True, # Enable line wrapping for the window
            # scrollbar=True, # This makes the scrollbar visible
            # style='class:output-field' # Style can be applied here if needed, or rely on global
        )
        # --- END MODIFICATION ---

        self.input_field = TextArea(
            style='class:input-field', # Prompt style will be handled by prompt_style
            multiline=self.config.get('behavior', {}).get('input_field_height', 3) > 1,
            wrap_lines=False, # Typically False for command input
            history=self.history,
            height=self.config.get('behavior', {}).get('input_field_height', 3)
        )

        self.key_help_field = Window(
            content=FormattedTextControl(text=HTML(self.key_help_text_content)),
            height=1,
            style='class:key-help'
        )
        self.separator_line = Window(height=1, char='─', style='class:line')

    def _init_keybindings(self):
        """Initializes keybindings for the UI."""
        self.kb = KeyBindings()

        @self.kb.add('c-c', eager=True)
        @self.kb.add('c-d', eager=True)
        def _handle_exit_or_cancel(event):
            if self._categorization_ui_flow_active:
                logger.info("Ctrl+C/D: Categorization UI flow cancel requested.")
                if 'future' in self._categorization_ui_flow_state and \
                   not self._categorization_ui_flow_state['future'].done():
                    self._categorization_ui_flow_state['future'].set_result({'action': 'cancel_execution'})
                self._end_categorization_ui_flow(cancelled=True)
                self.invalidate()
            elif self._confirmation_ui_flow_active:
                logger.info("Ctrl+C/D: Confirmation UI flow cancel requested.")
                if 'future' in self._confirmation_ui_flow_state and \
                   not self._confirmation_ui_flow_state['future'].done():
                    self._confirmation_ui_flow_state['future'].set_result({'action': 'cancel'})
                self._end_confirmation_ui_flow(cancelled=True)
                self.invalidate()
            elif self._on_exit_request_callback:
                logger.info("Ctrl+C/D: Application exit requested.")
                self._on_exit_request_callback()
            else:
                logger.warning("Ctrl+C/D: Exit request callback not set, exiting app instance directly.")
                if self.app_instance:
                    self.app_instance.exit()
        
        @self.kb.add('c-n')
        def _handle_newline(event):
            if not self._categorization_ui_flow_active and not self._confirmation_ui_flow_active:
                if self.input_field.multiline: # Only allow newline if input field is multiline
                    event.current_buffer.insert_text('\n')

        @self.kb.add('enter')
        def _handle_enter(event):
            # This keybinding is for the main input field.
            # If a UI flow is active, its specific accept_handler (set temporarily on input_field.buffer)
            # will be triggered by PTTK's default Enter behavior on that buffer.
            if not self._categorization_ui_flow_active and not self._confirmation_ui_flow_active:
                if self.input_field.buffer.accept_handler:
                    self.input_field.buffer.validate_and_handle()
                else:
                    logger.warning("Enter pressed but no accept_handler set on main input_field.")
            # If a flow is active, its accept_handler on input_field.buffer handles Enter.

        @self.kb.add('tab')
        def _handle_tab(event):
            buff = event.current_buffer
            if buff.complete_state:
                buff.complete_next()
            else:
                buff.insert_text('    ')

        @self.kb.add('pageup')
        def _handle_pageup(event):
            # Scrolling for FormattedTextControl is handled by the Window.
            # The Window itself needs to be scrollable and have a way to scroll.
            # This might require custom scroll handling if PTTK's default Window scrolling isn't sufficient.
            # For now, we assume the Window containing output_text_control handles scrolling.
            # A common way is to adjust the 'vertical_scroll' attribute of the Window's render_info
            # or use built-in scroll methods if available on the Window instance.
            # prompt_toolkit.layout.Window has _scroll_up() and _scroll_down() private methods.
            if self.output_field and hasattr(self.output_field, '_scroll_up'):
                 self.output_field._scroll_up() # Use with caution as it's private
                 self.invalidate()
            else:
                logger.debug("PageUp: Output field or scroll method not available.")


        @self.kb.add('pagedown')
        def _handle_pagedown(event):
            if self.output_field and hasattr(self.output_field, '_scroll_down'):
                self.output_field._scroll_down() # Use with caution
                self.invalidate()
            else:
                logger.debug("PageDown: Output field or scroll method not available.")

        @self.kb.add('up')
        def _handle_up_arrow(event):
            if not self._categorization_ui_flow_active and not self._confirmation_ui_flow_active:
                buff = event.current_buffer
                doc = buff.document
                if doc.cursor_position_row == 0:
                    if buff.history_backward():
                        buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                        self.invalidate()
                else:
                    buff.cursor_up()
        
        @self.kb.add('down')
        def _handle_down_arrow(event):
            if not self._categorization_ui_flow_active and not self._confirmation_ui_flow_active:
                buff = event.current_buffer
                doc = buff.document
                if doc.cursor_position_row == doc.line_count - 1:
                    if buff.history_forward():
                        buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                        self.invalidate()
                else:
                    buff.cursor_down()

        @self.kb.add('c-up')
        def _handle_ctrl_up(event):
            if not self._categorization_ui_flow_active and not self._confirmation_ui_flow_active:
                event.current_buffer.cursor_up(count=1)

        @self.kb.add('c-down')
        def _handle_ctrl_down(event):
            if not self._categorization_ui_flow_active and not self._confirmation_ui_flow_active:
                event.current_buffer.cursor_down(count=1)

    def _init_layout(self):
        """Initializes the layout of the UI."""
        layout_components = [
            self.output_field, # This is now a Window wrapping FormattedTextControl
            self.separator_line,
            self.input_field,
            self.key_help_field
        ]
        root_container = HSplit(layout_components)
        self.layout = Layout(root_container, focused_element=self.input_field)

    def _init_style(self):
        """Initializes the style for the UI elements."""
        # Styles are taken directly from main.py's original style
        # Ensure 'output-field' style is applied to the Window if needed,
        # or rely on individual FormattedText styles.
        self.style = Style.from_dict({
            'output-field': 'bg:#282c34 #abb2bf', # Style for the output area Window
            'input-field': 'bg:#21252b #d19a66',
            'key-help': 'bg:#282c34 #5c6370',
            'line': '#3e4451',
            'prompt': 'bg:#21252b #61afef',
            'scrollbar.background': 'bg:#282c34',
            'scrollbar.button': 'bg:#3e4451',
            'default': '#abb2bf', # Default text color for FormattedText
            'welcome': 'bold #86c07c',
            'info': '#61afef',
            'info-header': 'bold #61afef',
            'info-subheader': 'underline #61afef',
            'info-item': '#abb2bf',
            'info-item-empty': 'italic #5c6370',
            'success': '#98c379',
            'error': '#e06c75',
            'warning': '#d19a66',
            'security-critical': 'bold #e06c75 bg:#5c0000',
            'security-warning': '#e06c75',
            'ai-query': '#c678dd',
            'ai-thinking': 'italic #56b6c2',
            'ai-thinking-detail': 'italic #4b8e97',
            'ai-response': '#56b6c2',
            'ai-unsafe': 'bold #e06c75',
            'executing': 'bold #61afef',
            'categorize-info': '#abb2bf',
            'categorize-prompt': 'bold #d19a66',
            'help-base': '#abb2bf',
            'help-title': 'bold underline #e5c07b',
            'help-text': '#abb2bf',
            'help-header': 'bold #61afef',
            'help-command': '#c678dd',
            'help-description': '#abb2bf',
            'help-example': 'italic #5c6370',
        })
        self.input_field.prompt_style = 'class:prompt'


    async def run(self):
        """Runs the prompt_toolkit application."""
        if self.app_instance:
            logger.info("UIManager: Application starting.")
            await self.app_instance.run_async()
            logger.info("UIManager: Application finished.")
        else:
            logger.error("UIManager: Application instance not created. Cannot run.")

    def exit_app(self):
        """Stops the prompt_toolkit application if it's running."""
        if self.app_instance and self.app_instance.is_running:
            logger.info("UIManager: Exiting application.")
            self.app_instance.exit()
        else:
            logger.info("UIManager: Application not running or not initialized for exit.")

    def invalidate(self):
        """Requests a redraw of the UI."""
        if self.app_instance: # Invalidate even if not running, changes apply on next draw
            self.app_instance.invalidate()

    def _build_formatted_output(self) -> FormattedText:
        """Builds FormattedText from the internal _output_buffer."""
        # `to_formatted_text` can take a list of (style_str, text_str) tuples.
        return to_formatted_text(self._output_buffer)

    def add_output_line(self, text: str, style_class: str = 'class:default'): # Default style class
        """
        Adds a line of text to the output area with a given style.
        Updates the FormattedTextControl.
        """
        if not text.endswith('\n'):
            text += '\n'
        
        self._output_buffer.append((style_class, text))
        
        # Update the FormattedTextControl with the new complete buffer
        self.output_text_control.text = self._build_formatted_output()

        # Auto-scrolling with FormattedTextControl in a Window:
        # The Window tries to keep the cursor visible. If we want to scroll to the bottom,
        # we can try to move the "cursor" of the FormattedTextControl,
        # or more simply, rely on the Window's behavior when content changes.
        # For explicit scroll to bottom, one might need to manipulate Window's vertical_scroll.
        # For now, frequent invalidation might be enough if the content grows downwards.
        if self._auto_scroll_output or self._categorization_ui_flow_active or self._confirmation_ui_flow_active:
            # This is a bit of a hack for FormattedTextControl.
            # We tell the window to scroll to the end of its content.
            if self.output_field and self.output_field.render_info:
                 self.output_field.vertical_scroll = self.output_field.render_info.content_height - self.output_field.render_info.window_height
        
        self.invalidate()

    # _handle_output_cursor_pos_changed is less relevant for FormattedTextControl
    # as it doesn't have a user-movable cursor in the same way TextArea does.
    # Auto-scroll logic is now partially in add_output_line.
    # If manual scrolling by user needs to disable auto-scroll, that needs a different mechanism.


    # --- Input Area Management ---
    def set_input_prompt(self, prompt_text: str):
        """Sets the prompt for the input field."""
        # Ensure prompt_text is FormattedText or HTML for styling
        if not isinstance(prompt_text, (FormattedText, HTML)):
            prompt_text = HTML(prompt_text) # Default to HTML if plain string
        self.input_field.prompt = prompt_text
        self.invalidate()

    def get_input_text(self) -> str:
        """Gets the current text from the input field."""
        return self.input_field.text

    def set_input_text(self, text: str, cursor_position: int = None):
        """Sets the text and cursor position in the input field."""
        if cursor_position is None:
            cursor_position = len(text)
        # Ensure the document is created correctly for the buffer
        self.input_field.buffer.document = Document(text=text, cursor_position=cursor_position)
        self.invalidate()

    def set_input_handler(self, handler_func):
        """Sets the accept handler for the main input field."""
        self._on_input_submit_callback = handler_func
        self.input_field.buffer.accept_handler = handler_func
        logger.debug(f"UIManager: Main input handler set to {handler_func.__name__ if handler_func else 'None'}")

    def set_input_multiline(self, is_multiline: bool):
        """Sets the input field to be multiline or single line."""
        self.input_field.multiline = is_multiline
        if is_multiline:
            self.input_field.height = self.config.get('behavior', {}).get('input_field_height', 3)
        else:
            self.input_field.height = 1
        self.invalidate()

    def focus_input(self):
        """Sets focus to the input field."""
        if self.app_instance and self.app_instance.layout:
            self.app_instance.layout.focus(self.input_field)

    # --- Keybinding Callbacks (from UI module to main.py) ---
    def set_on_exit_request_callback(self, callback_func):
        """Sets the callback for when the user requests to exit (Ctrl+C/D)."""
        self._on_exit_request_callback = callback_func

    # --- Flow Management (UI part) ---
    def _prepare_ui_for_flow(self, flow_prompt_prefix: str):
        """Common UI setup when starting any interactive flow."""
        self.set_input_multiline(False)
        self.input_field.buffer.reset(append_to_history=False)
        # Prompt is set by the specific flow step
        self.focus_input()
        self.invalidate()
    
    def _restore_ui_from_flow(self, original_handler, original_prompt_text):
        """Common UI restoration after an interactive flow ends."""
        self.set_input_handler(original_handler)
        self.set_input_prompt(original_prompt_text if original_prompt_text is not None else "")
        self.set_input_multiline(self.config.get('behavior', {}).get('input_field_height', 3) > 1)
        self.input_field.buffer.reset(append_to_history=False)
        self.focus_input()
        self.invalidate()

    # --- Confirmation Flow ---
    async def start_confirmation_flow(self, command_to_confirm: str, display_source: str, on_complete_callback):
        """Starts the UI part of the command confirmation flow."""
        if self._confirmation_ui_flow_active or self._categorization_ui_flow_active:
            logger.warning("UIManager: Another flow is already active. Cannot start confirmation flow.")
            on_complete_callback({'action': 'error', 'message': 'Another UI flow active'})
            return

        logger.info(f"UIManager: Starting confirmation flow for '{command_to_confirm}'")
        self._confirmation_ui_flow_active = True
        
        original_accept_handler = self.input_field.buffer.accept_handler
        # input_field.prompt can be a callable or FormattedText. Get its string representation for restoration.
        current_prompt_obj = self.input_field.prompt
        original_prompt_text = "".join(part[1] for part in to_formatted_text(current_prompt_obj() if callable(current_prompt_obj) else current_prompt_obj))


        self._confirmation_ui_flow_state = {
            'command_to_confirm': command_to_confirm,
            'display_source': display_source,
            'on_complete_callback': on_complete_callback,
            'original_accept_handler': original_accept_handler,
            'original_prompt': original_prompt_text, # Store the text
            'future': asyncio.Future(),
            'step': 'ask_main_choice'
        }
        
        self._ask_confirmation_main_choice_ui()

        try:
            await self._confirmation_ui_flow_state['future']
        except asyncio.CancelledError:
            logger.info("UIManager: Confirmation flow future cancelled.")
            if 'future' in self._confirmation_ui_flow_state and \
               not self._confirmation_ui_flow_state['future'].done():
                # Ensure callback is called if flow is aborted externally
                self._confirmation_ui_flow_state['on_complete_callback']({'action': 'cancel', 'message': 'Flow aborted'})
        finally:
            # Actual cleanup is handled by _end_confirmation_ui_flow
            pass

    def _ask_confirmation_main_choice_ui(self):
        """Displays the main choices for command confirmation."""
        state = self._confirmation_ui_flow_state
        cmd = state['command_to_confirm']
        source = state['display_source']

        self.add_output_line(f"\n🤖 AI proposed command (from: {source}):", style_class='class:ai-query')
        self.add_output_line(f"    👉 {cmd}", style_class='class:executing')
        self.add_output_line(
            "Action: [Y]es (Execute) | [E]xplain | [M]odify | [C]ancel execution?",
            style_class='class:categorize-prompt'
        )
        self._prepare_ui_for_flow("Confirm AI Cmd")
        self.set_input_prompt("[Confirm AI Cmd] Choice (Y/E/M/C): ")
        self.input_field.buffer.accept_handler = self._handle_confirmation_main_choice_response_ui

    def _handle_confirmation_main_choice_response_ui(self, buff):
        """Handles user's choice in the main confirmation step."""
        response = buff.text.strip().lower()
        state = self._confirmation_ui_flow_state
        
        valid_choice = False
        if response in ['y', 'yes']:
            state['on_complete_callback']({'action': 'execute', 'command': state['command_to_confirm']})
            self._end_confirmation_ui_flow()
            valid_choice = True
        elif response in ['e', 'explain']:
            self.input_field.buffer.reset(append_to_history=False) # Clear 'e'
            # Signal main.py to get explanation. UI will wait.
            state['on_complete_callback']({'action': 'explain_requested', 'command': state['command_to_confirm']})
            self.set_input_prompt("[Explaining...]")
            self.input_field.buffer.read_only = True # Make input read-only while waiting
            self.invalidate()
            valid_choice = True # Flow continues after main.py calls back
        elif response in ['m', 'modify']:
            self.set_input_text(state['command_to_confirm'])
            state['on_complete_callback']({'action': 'edit_handled_externally'})
            # Main.py will restore normal input handler after user submits the edited command.
            self._end_confirmation_ui_flow(restore_main_input_handler_immediately=False)
            valid_choice = True
        elif response in ['c', 'cancel', 'n', 'no']:
            state['on_complete_callback']({'action': 'cancel'})
            self._end_confirmation_ui_flow()
            valid_choice = True
        else:
            self.add_output_line("Invalid choice. Please enter Y, E, M, or C.", style_class='class:error')
            self._ask_confirmation_main_choice_ui() # Ask again
            return 

        if valid_choice and response not in ['e']: # 'e' keeps its input field state until explanation callback
            self.input_field.buffer.reset(append_to_history=False)

    def continue_confirmation_after_explain(self, explanation: str | None):
        """Called by main.py after it has fetched the explanation to update UI."""
        if not self._confirmation_ui_flow_active:
            logger.warning("UIManager: continue_confirmation_after_explain called but no confirmation flow active.")
            return

        self.input_field.buffer.read_only = False # Re-enable input
        self.input_field.buffer.reset(append_to_history=False) # Clear "Explaining..." prompt text

        if explanation:
            self.add_output_line("\n💡 AI Explanation:", style_class='class:info-header')
            self.add_output_line(explanation, style_class='class:info')
        else:
            self.add_output_line("⚠️ AI could not provide an explanation.", style_class='class:warning')
        
        self._ask_confirmation_after_explain_ui()

    def _ask_confirmation_after_explain_ui(self):
        """Displays choices after an explanation has been shown."""
        state = self._confirmation_ui_flow_state
        cmd = state['command_to_confirm']
        
        self.add_output_line(f"\nCommand to consider: {cmd}", style_class='class:executing')
        self.add_output_line(
            "Action: [Y]es (Execute) | [M]odify | [C]ancel execution?",
            style_class='class:categorize-prompt'
        )
        self._prepare_ui_for_flow("Confirm AI Cmd")
        self.set_input_prompt("[Confirm AI Cmd] Choice (Y/M/C): ")
        self.input_field.buffer.accept_handler = self._handle_confirmation_after_explain_response_ui

    def _handle_confirmation_after_explain_response_ui(self, buff):
        """Handles user's choice after an explanation."""
        response = buff.text.strip().lower()
        state = self._confirmation_ui_flow_state
        valid_choice = False

        if response in ['y', 'yes']:
            state['on_complete_callback']({'action': 'execute', 'command': state['command_to_confirm']})
            self._end_confirmation_ui_flow()
            valid_choice = True
        elif response in ['m', 'modify']:
            self.set_input_text(state['command_to_confirm'])
            state['on_complete_callback']({'action': 'edit_handled_externally'})
            self._end_confirmation_ui_flow(restore_main_input_handler_immediately=False)
            valid_choice = True
        elif response in ['c', 'cancel', 'n', 'no']:
            state['on_complete_callback']({'action': 'cancel'})
            self._end_confirmation_ui_flow()
            valid_choice = True
        else:
            self.add_output_line("Invalid choice. Please enter Y, M, or C.", style_class='class:error')
            self._ask_confirmation_after_explain_ui() # Ask again
            return
            
        if valid_choice:
            self.input_field.buffer.reset(append_to_history=False)

    def _end_confirmation_ui_flow(self, cancelled=False, restore_main_input_handler_immediately=True):
        """Cleans up and ends the confirmation UI flow."""
        logger.info(f"UIManager: Ending confirmation flow. Cancelled: {cancelled}")
        state = self._confirmation_ui_flow_state
        if not self._confirmation_ui_flow_active: return

        self._confirmation_ui_flow_active = False
        if 'future' in state and state['future'] and not state['future'].done():
            state['future'].set_result(None) 

        if restore_main_input_handler_immediately:
            self._restore_ui_from_flow(state.get('original_accept_handler'), state.get('original_prompt'))
        
        self._confirmation_ui_flow_state = {} 
        if cancelled:
            self.add_output_line("\n⚠️ Command confirmation cancelled by user.", style_class='class:warning')
        self.invalidate() # Ensure UI updates after flow ends


    # --- Categorization Flow (Mirroring structure of Confirmation Flow) ---
    async def start_categorization_flow(self, command_initially_proposed: str,
                                        ai_raw_candidate: str | None,
                                        original_direct_input: str | None,
                                        on_complete_callback):
        """Starts the UI part of the command categorization flow."""
        if self._categorization_ui_flow_active or self._confirmation_ui_flow_active:
            logger.warning("UIManager: Another flow is already active. Cannot start categorization flow.")
            on_complete_callback({'action': 'error', 'message': 'Another UI flow active'})
            return

        logger.info(f"UIManager: Starting categorization flow for '{command_initially_proposed}'")
        self._categorization_ui_flow_active = True
        
        original_accept_handler = self.input_field.buffer.accept_handler
        current_prompt_obj = self.input_field.prompt
        original_prompt_text = "".join(part[1] for part in to_formatted_text(current_prompt_obj() if callable(current_prompt_obj) else current_prompt_obj))


        self._categorization_ui_flow_state = {
            'command_initially_proposed': command_initially_proposed,
            'ai_raw_candidate': ai_raw_candidate,
            'original_direct_input': original_direct_input,
            'command_to_add_final': command_initially_proposed,
            'on_complete_callback': on_complete_callback,
            'original_accept_handler': original_accept_handler,
            'original_prompt': original_prompt_text,
            'future': asyncio.Future(),
            'step': 0.5 
        }
        
        self._ask_step_0_5_confirm_command_base_ui()

        try:
            await self._categorization_ui_flow_state['future']
        except asyncio.CancelledError:
            logger.info("UIManager: Categorization flow future cancelled.")
            if 'future' in self._categorization_ui_flow_state and \
               not self._categorization_ui_flow_state['future'].done():
                self._categorization_ui_flow_state['on_complete_callback']({'action': 'cancel_execution', 'message': 'Flow aborted'})
        finally:
            pass # Cleanup by _end_categorization_ui_flow

    def _ask_step_0_5_confirm_command_base_ui(self):
        """Categorization Step 0.5: Confirm which command string to use if original and proposed differ."""
        state = self._categorization_ui_flow_state
        proposed = state['command_initially_proposed']
        original = state['original_direct_input']

        if original and original.strip() != proposed.strip():
            self.add_output_line(f"\nSystem processed to: '{proposed}'\nOriginal input was: '{original}'", style_class='class:categorize-info')
            self.add_output_line(f"Which version to categorize?\n  1: Processed ('{proposed}')\n  2: Original ('{original}')\n  3: Modify/Enter new command\n  4: Cancel categorization", style_class='class:categorize-prompt')
            self._prepare_ui_for_flow("Categorize")
            self.set_input_prompt("[Categorize] Choice (1-4): ")
            self.input_field.buffer.accept_handler = self._handle_step_0_5_response_ui
        else:
            state['command_to_add_final'] = proposed
            state['step'] = 1
            self._ask_step_1_main_action_ui()

    def _handle_step_0_5_response_ui(self, buff):
        """Handles response for categorization step 0.5."""
        response = buff.text.strip()
        state = self._categorization_ui_flow_state
        proposed = state['command_initially_proposed']
        original = state['original_direct_input']
        
        self.input_field.buffer.reset(append_to_history=False)

        if response == '1':
            state['command_to_add_final'] = proposed
            self.add_output_line(f"Using processed: '{proposed}'", style_class='class:categorize-info')
            state['step'] = 1
            self._ask_step_1_main_action_ui()
        elif response == '2' and original:
            state['command_to_add_final'] = original
            self.add_output_line(f"Using original: '{original}'", style_class='class:categorize-info')
            state['step'] = 1
            self._ask_step_1_main_action_ui()
        elif response == '3':
            state['step'] = 3.5
            self._ask_step_3_5_enter_custom_command_for_categorization_ui()
        elif response == '4':
            state['on_complete_callback']({'action': 'cancel_execution'})
            self._end_categorization_ui_flow()
        else:
            self.add_output_line("Invalid choice (1-4). Please try again.", style_class='class:error')
            self._ask_step_0_5_confirm_command_base_ui()

    def _ask_step_1_main_action_ui(self):
        """Categorization Step 1: Ask user how to categorize the chosen command."""
        state = self._categorization_ui_flow_state
        cmd_display = state['command_to_add_final']
        
        # Use category descriptions from config if available
        cat_desc_config = self.config.get('category_manager', {}).get('CATEGORY_DESCRIPTIONS', {})
        cat_desc_simple = cat_desc_config.get('simple', 'Direct output')
        cat_desc_semi = cat_desc_config.get('semi_interactive', 'Tmux, output after')
        cat_desc_interactive = cat_desc_config.get('interactive_tui', 'Full tmux')
        default_cat_name = self.config.get('behavior',{}).get('default_category_for_unclassified', 'simple')

        self.add_output_line(f"\nCommand to categorize: '{cmd_display}'", style_class='class:categorize-info')
        self.add_output_line(
            f"How to categorize this command?\n"
            f"  1: simple             ({cat_desc_simple})\n"
            f"  2: semi_interactive   ({cat_desc_semi})\n"
            f"  3: interactive_tui    ({cat_desc_interactive})\n"
            f"  M: Modify command before categorizing\n"
            f"  D: Execute as default '{default_cat_name}' (once, no save)\n"
            f"  C: Cancel categorization & execution", style_class='class:categorize-prompt')
        self._prepare_ui_for_flow("Categorize")
        self.set_input_prompt("[Categorize] Action (1-3/M/D/C): ")
        self.input_field.buffer.accept_handler = self._handle_step_1_main_action_response_ui

    def _handle_step_1_main_action_response_ui(self, buff):
        """Handles response for categorization step 1."""
        response = buff.text.strip().lower()
        state = self._categorization_ui_flow_state
        cmd_to_add = state['command_to_add_final']
        
        cat_map_config = self.config.get('category_manager', {}).get('CATEGORY_MAP_NUM_TO_NAME', {
            "1": "simple", "2": "semi_interactive", "3": "interactive_tui"
        })
        self.input_field.buffer.reset(append_to_history=False)

        if response in ['1', '2', '3']:
            chosen_category_name = cat_map_config.get(response)
            state['on_complete_callback']({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category_name})
            self._end_categorization_ui_flow()
        elif response == 'm':
            state['step'] = 4
            self._ask_step_4_enter_modified_command_ui(base_command=cmd_to_add)
        elif response == 'd':
            state['on_complete_callback']({'action': 'execute_as_default', 'command': cmd_to_add}) # Pass command for default execution
            self._end_categorization_ui_flow()
        elif response == 'c':
            state['on_complete_callback']({'action': 'cancel_execution'})
            self._end_categorization_ui_flow()
        else:
            self.add_output_line("Invalid choice. Please enter 1-3, M, D, or C.", style_class='class:error')
            self._ask_step_1_main_action_ui()

    def _ask_step_3_5_enter_custom_command_for_categorization_ui(self):
        """Categorization Step 3.5: User wants to enter a completely new command."""
        self.add_output_line("\nEnter the new command string you want to categorize:", style_class='class:categorize-prompt')
        self._prepare_ui_for_flow("Categorize")
        self.set_input_prompt("[Categorize] New command: ")
        self.set_input_text("") 
        self.input_field.buffer.accept_handler = self._handle_step_3_5_response_ui

    def _handle_step_3_5_response_ui(self, buff):
        """Handles response for categorization step 3.5."""
        custom_command = buff.text.strip()
        state = self._categorization_ui_flow_state
        self.input_field.buffer.reset(append_to_history=False)

        if not custom_command:
            self.add_output_line("⚠️ Command cannot be empty. Please enter a command or Ctrl+C to cancel.", style_class='class:warning')
            self._ask_step_3_5_enter_custom_command_for_categorization_ui()
            return
        state['command_to_add_final'] = custom_command
        self.add_output_line(f"New command for categorization: '{custom_command}'", style_class='class:categorize-info')
        state['step'] = 1
        self._ask_step_1_main_action_ui()

    def _ask_step_4_enter_modified_command_ui(self, base_command: str):
        """Categorization Step 4: User wants to modify the current command candidate."""
        self.add_output_line(f"\nCurrent command: '{base_command}'\nEnter your modified command below:", style_class='class:categorize-prompt')
        self._prepare_ui_for_flow("Categorize")
        self.set_input_prompt("[Categorize] Modified Cmd: ")
        self.set_input_text(base_command, cursor_position=len(base_command))
        self.input_field.buffer.accept_handler = self._handle_step_4_modified_command_response_ui

    def _handle_step_4_modified_command_response_ui(self, buff):
        """Handles response for categorization step 4."""
        modified_command = buff.text.strip()
        state = self._categorization_ui_flow_state
        self.input_field.buffer.reset(append_to_history=False)

        if not modified_command:
            self.add_output_line("⚠️ Modified command empty. Using previous command for categorization.", style_class='class:warning')
        else:
            state['command_to_add_final'] = modified_command
        state['step'] = 4.5
        self._ask_step_4_5_category_for_modified_ui()

    def _ask_step_4_5_category_for_modified_ui(self):
        """Categorization Step 4.5: Ask for category for the (potentially) modified command."""
        state = self._categorization_ui_flow_state
        cmd_to_categorize = state['command_to_add_final']
        cat_desc_config = self.config.get('category_manager', {}).get('CATEGORY_DESCRIPTIONS', {})
        cat_desc_simple = cat_desc_config.get('simple', 'Direct output')
        cat_desc_semi = cat_desc_config.get('semi_interactive', 'Tmux, output after')
        cat_desc_interactive = cat_desc_config.get('interactive_tui', 'Full tmux')

        self.add_output_line(f"\nCategory for command: '{cmd_to_categorize}'", style_class='class:categorize-info')
        self.add_output_line(
            f"  1: simple             ({cat_desc_simple})\n"
            f"  2: semi_interactive   ({cat_desc_semi})\n"
            f"  3: interactive_tui    ({cat_desc_interactive})", style_class='class:categorize-prompt')
        self._prepare_ui_for_flow("Categorize")
        self.set_input_prompt("[Categorize] Category (1-3): ")
        self.input_field.buffer.accept_handler = self._handle_step_4_5_response_ui

    def _handle_step_4_5_response_ui(self, buff):
        """Handles response for categorization step 4.5."""
        response = buff.text.strip()
        state = self._categorization_ui_flow_state
        cat_map_config = self.config.get('category_manager', {}).get('CATEGORY_MAP_NUM_TO_NAME', {
            "1": "simple", "2": "semi_interactive", "3": "interactive_tui"
        })
        self.input_field.buffer.reset(append_to_history=False)

        chosen_category_name = cat_map_config.get(response)
        if chosen_category_name:
            state['on_complete_callback']({'action': 'categorize_and_execute', 'command': state['command_to_add_final'], 'category': chosen_category_name})
            self._end_categorization_ui_flow()
        else:
            self.add_output_line("Invalid category. Please enter 1, 2, or 3.", style_class='class:error')
            self._ask_step_4_5_category_for_modified_ui()

    def _end_categorization_ui_flow(self, cancelled=False):
        """Cleans up and ends the categorization UI flow."""
        logger.info(f"UIManager: Ending categorization flow. Cancelled: {cancelled}")
        state = self._categorization_ui_flow_state
        if not self._categorization_ui_flow_active: return

        self._categorization_ui_flow_active = False
        if 'future' in state and state['future'] and not state['future'].done():
            state['future'].set_result(None) 

        self._restore_ui_from_flow(state.get('original_accept_handler'), state.get('original_prompt'))
        
        self._categorization_ui_flow_state = {} 
        if cancelled:
            self.add_output_line("\n⚠️ Categorization cancelled by user.", style_class='class:warning')
        self.invalidate() # Ensure UI updates after flow ends

    def end_active_flow(self):
        """Public method for main.py to call if it needs to force-end a UI flow."""
        if self._confirmation_ui_flow_active:
            logger.info("UIManager: Force ending active confirmation flow (called by main.py).")
            if 'future' in self._confirmation_ui_flow_state and \
               self._confirmation_ui_flow_state['future'] and \
               not self._confirmation_ui_flow_state['future'].done():
                self._confirmation_ui_flow_state['future'].set_result({'action': 'cancel', 'message': 'Flow ended by external logic'})
            self._end_confirmation_ui_flow(cancelled=True)
        elif self._categorization_ui_flow_active:
            logger.info("UIManager: Force ending active categorization flow (called by main.py).")
            if 'future' in self._categorization_ui_flow_state and \
               self._categorization_ui_flow_state['future'] and \
               not self._categorization_ui_flow_state['future'].done():
                self._categorization_ui_flow_state['future'].set_result({'action': 'cancel_execution', 'message': 'Flow ended by external logic'})
            self._end_categorization_ui_flow(cancelled=True)
        else:
            logger.debug("UIManager: end_active_flow called, but no UI flow was active.")
        self.invalidate()
