#!/usr/bin/env python

import logging
from prompt_toolkit import Application, HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText, to_formatted_text

logger = logging.getLogger(__name__)

class UIManager:
    """
    Manages the core user interface for micro_X using prompt_toolkit.
    This is a minimal version focusing on application lifecycle, basic layout, and output.
    """
    def __init__(self, config, history_object, initial_prompt_text_func, key_help_text_content):
        """
        Initializes the UIManager.

        Args:
            config (dict): The application configuration.
            history_object (FileHistory): The command history object.
            initial_prompt_text_func (callable): A function that returns the initial prompt string.
            key_help_text_content (str): The text for the key help bar.
        """
        self.config = config
        self.history = history_object
        self.initial_prompt_text_func = initial_prompt_text_func
        self.key_help_text_content = key_help_text_content

        self._output_buffer = []  # Stores (style_class, text) tuples
        self._auto_scroll_output = True # Basic auto-scroll flag
        self.app_instance = None

        # Callbacks to be set by main.py if UIManager needs to trigger main logic
        self._on_input_submit_callback = None # For Enter key on main input
        self._on_exit_request_callback = None # For Ctrl+C/D to exit app (handled by UIManager)

        self._init_ui_elements()
        self._init_keybindings() # Basic keybindings like exit
        self._init_layout()
        self._init_style()

        self.app_instance = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True
        )
        logger.info("Minimal UIManager initialized.")

    def _init_ui_elements(self):
        """Initializes the TextArea and Window widgets."""
        self.output_text_control = FormattedTextControl(
            text=self._build_formatted_output(), # Start with empty or initial buffer
            focusable=False,
            # key_bindings=self._get_output_field_key_bindings() # For scrolling output
        )
        self.output_field = Window(
            content=self.output_text_control,
            wrap_lines=True,
            # scrollbar=True, # Optional: make scrollbar always visible
            # allow_scroll_beyond_bottom=False, # Default
        )
        # Output field scroll listener
        self.output_field.vertical_scroll_on_new_content = True # Helps with auto-scroll
        self.output_field.buffer_empty_on_new_content = False


        self.input_field = TextArea(
            # prompt will be set dynamically by main.py via a UIManager method
            prompt=self.initial_prompt_text_func, # Use the function to get initial prompt
            style='class:input-field',
            multiline=self.config.get('behavior', {}).get('input_field_height', 3) > 1,
            wrap_lines=False,
            history=self.history,
            # accept_handler will be set by main.py via set_input_handler
            height=self.config.get('behavior', {}).get('input_field_height', 3)
        )

        self.key_help_field = Window(
            content=FormattedTextControl(text=HTML(self.key_help_text_content)), # Use HTML for simple formatting
            height=1,
            style='class:key-help'
        )
        self.separator_line = Window(height=1, char='─', style='class:line')
        logger.debug("UI elements initialized.")

    def _init_keybindings(self):
        """Initializes basic keybindings (e.g., for exiting the app)."""
        self.kb = KeyBindings()

        @self.kb.add('c-c', eager=True)
        @self.kb.add('c-d', eager=True)
        def _handle_exit(event):
            """Handles Ctrl+C or Ctrl+D to exit the application."""
            logger.info("UIManager: Exit requested via Ctrl+C/D.")
            if self.app_instance:
                self.app_instance.exit()
        # More complex keybindings (Enter, Tab, Arrows for input field) will remain
        # in main.py's KeyBindings instance for now, which will be passed to Application.
        # Or, main.py will pass its keybinding handlers to UIManager.
        # For this minimal version, UIManager only handles its own direct exit.
        # The main input field's keybindings (like Enter) will be handled by its accept_handler.

    def _init_layout(self):
        """Initializes the layout of the UI."""
        layout_components = [
            self.output_field,
            self.separator_line,
            self.input_field,
            self.key_help_field
        ]
        root_container = HSplit(layout_components)
        self.layout = Layout(root_container, focused_element=self.input_field)
        logger.debug("Layout initialized.")

    def _init_style(self):
        """Initializes the style for the UI elements."""
        self.style = Style.from_dict({
            'output-field': 'bg:#282c34 #abb2bf',
            'input-field': 'bg:#21252b #d19a66',
            'key-help': 'bg:#282c34 #5c6370',
            'line': '#3e4451',
            'prompt': 'bg:#21252b #61afef',
            'scrollbar.background': 'bg:#282c34',
            'scrollbar.button': 'bg:#3e4451',
            # Define styles that main.py might use via add_output_line
            'class:default': '#abb2bf',
            'class:welcome': 'bold #86c07c',
            'class:info': '#61afef',
            'class:info-header': 'bold #61afef',
            'class:info-subheader': 'underline #61afef',
            'class:info-item': '#abb2bf',
            'class:info-item-empty': 'italic #5c6370',
            'class:success': '#98c379',
            'class:error': '#e06c75',
            'class:warning': '#d19a66',
            'class:security-critical': 'bold #e06c75 bg:#5c0000',
            'class:security-warning': '#e06c75',
            'class:ai-query': '#c678dd',
            'class:ai-thinking': 'italic #56b6c2',
            'class:ai-thinking-detail': 'italic #4b8e97',
            'class:ai-response': '#56b6c2',
            'class:ai-unsafe': 'bold #e06c75',
            'class:executing': 'bold #61afef',
            'class:categorize-info': '#abb2bf',
            'class:categorize-prompt': 'bold #d19a66',
            'class:help-base': '#abb2bf',
            'class:help-title': 'bold underline #e5c07b',
            'class:help-text': '#abb2bf',
            'class:help-header': 'bold #61afef',
            'class:help-command': '#c678dd',
            'class:help-description': '#abb2bf',
            'class:help-example': 'italic #5c6370',
        })
        # Apply the prompt style to the input_field's prompt text
        self.input_field.prompt_style = 'class:prompt'
        logger.debug("Style initialized.")

    def _build_formatted_output(self) -> FormattedText:
        """Builds FormattedText from the internal _output_buffer."""
        return to_formatted_text(self._output_buffer)

    def add_output_line(self, text: str, style_class: str = 'class:default'):
        """
        Adds a line of text to the output area with a given style.
        Ensures style_class starts with 'class:'.
        """
        if not text.endswith('\n'):
            text += '\n'
        
        # Ensure style_class is correctly formatted
        actual_style_class = style_class
        if not style_class.startswith('class:'):
            logger.warning(f"Style '{style_class}' for UIManager.add_output_line doesn't start with 'class:'. Prepending.")
            actual_style_class = f'class:{style_class}'
            
        self._output_buffer.append((actual_style_class, text))
        self.output_text_control.text = self._build_formatted_output()

        if self._auto_scroll_output: # Basic auto-scroll
            if self.output_field and self.output_field.render_info:
                try:
                    content_height = self.output_field.render_info.content_height
                    window_height = self.output_field.render_info.window_height
                    self.output_field.vertical_scroll = max(0, content_height - window_height)
                except Exception as e:
                    logger.error(f"Error during auto-scroll: {e}", exc_info=True)
        self.invalidate()

    def set_input_prompt(self, prompt_text: str):
        """Sets the prompt for the input field."""
        self.input_field.prompt = prompt_text
        self.invalidate()

    def set_input_handler(self, handler_func):
        """Sets the accept handler for the main input field."""
        self._on_input_submit_callback = handler_func # Store for UIManager's own logic if needed
        self.input_field.accept_handler = handler_func # Set on the actual buffer
        logger.debug(f"UIManager: Main input handler set to {handler_func.__name__ if handler_func else 'None'}")

    def set_input_multiline(self, is_multiline: bool):
        """Sets the input field to be multiline or single line and adjusts height."""
        self.input_field.multiline = is_multiline
        if is_multiline:
            self.input_field.height = self.config.get('behavior', {}).get('input_field_height', 3)
        else:
            self.input_field.height = 1 # Single line height for flows
        self.invalidate()
        
    def get_input_text(self) -> str:
        """Gets the current text from the input field."""
        return self.input_field.text

    def set_input_text(self, text: str, cursor_at_end: bool = True):
        """Sets the text in the input field and optionally moves cursor to end."""
        pos = len(text) if cursor_at_end else self.input_field.buffer.cursor_position
        self.input_field.buffer.document = Document(text=text, cursor_position=pos)
        self.invalidate()

    def reset_input_buffer(self, append_to_history=False):
        """Resets the input field's buffer."""
        self.input_field.buffer.reset(append_to_history=append_to_history)
        self.invalidate()

    def focus_input(self):
        """Sets focus to the input field."""
        if self.app_instance and self.app_instance.layout:
            try:
                self.app_instance.layout.focus(self.input_field)
            except Exception as e:
                logger.error(f"Error focusing input field: {e}", exc_info=True)

    def invalidate(self):
        """Requests a redraw of the UI if the application is running."""
        if self.app_instance and self.app_instance.is_running:
            self.app_instance.invalidate()
        elif self.app_instance: # App exists but not running (e.g. during setup)
            pass # logger.debug("UIManager: Invalidate called, but app not running yet.")
        else:
            logger.warning("UIManager: Invalidate called, but no app_instance.")


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
