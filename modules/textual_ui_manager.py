import logging
import asyncio
from typing import Optional

# Import the actual Textual app class
from .textual_app import MicroXTextualApp

logger = logging.getLogger(__name__)

class TextualUIManager:
    """
    Adapter for UIManager that bridges the ShellEngine to a Textual App.
    Mimics the interface of the original prompt_toolkit UIManager.
    """
    def __init__(self, config: dict, shell_engine_instance=None):
        self.config = config
        self.shell_engine_instance = shell_engine_instance
        self.app: Optional[MicroXTextualApp] = None
        
        # Mode flags for compatibility
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.is_in_edit_mode = False
        self.initial_prompt_settled = True
        self.output_buffer = [] # Buffer for compatibility
        self.last_output_was_separator = False

    def append_output(self, content: str, style_class: str = None) -> None:
        """Delegates to the Textual app's log widget."""
        self.output_buffer.append((style_class, content))
        self.last_output_was_separator = False
        if self.app:
            # Use call_later which schedules the callback on the app's loop.
            # It works from both the same loop and other threads.
            self.app.call_later(self.app.append_output, content, style_class)
        else:
            print(content) # Fallback if app isn't running

    def update_input_prompt(self, path: str = None) -> None:
        # Textual uses a placeholder or static prompt label.
        # We can update the Input widget's placeholder.
        if self.app and path:
             self.app.call_later(lambda: setattr(self.app.input_widget, 'placeholder', f"({path}) > "))

    async def prompt_for_command_confirmation(self, command: str, original_query: str, callback_ref=None) -> dict:
        """Mimics the interactive confirmation flow using the Textual app's Modal/Inline widget."""
        if not self.app:
            return {'action': 'cancel'}

        self.confirmation_flow_active = True
        self.last_output_was_separator = False
        explanation_text = None
        
        try:
            while True:
                # Display the interaction widget and await user choice
                user_choice = await self.app.show_confirmation_modal(command, original_query, explanation_text)
                
                if user_choice == 'execute':
                    return {'action': 'execute', 'command': command}
                
                elif user_choice == 'execute_simple':
                    return {'action': 'execute_and_categorize', 'category': 'simple', 'command': command}
                
                elif user_choice == 'execute_semi':
                    return {'action': 'execute_and_categorize', 'category': 'semi_interactive', 'command': command}
                
                elif user_choice == 'execute_tui':
                    return {'action': 'execute_and_categorize', 'category': 'interactive_tui', 'command': command}

                elif user_choice == 'explain':
                    self.append_output(f"🤔 Explaining: {command}", "info")
                    from modules.ai_handler import explain_linux_command_with_ai
                    explanation = await explain_linux_command_with_ai(command, self.config, self.append_output)
                    if explanation:
                        self.append_output(f"💡 Explanation:\n{explanation}", "info") # Print to log
                        explanation_text = explanation # Also update menu
                    continue
                
                elif user_choice == 'modify':
                    if self.app:
                        # Load command into input
                        self.app.call_later(setattr, self.app.input_widget, 'value', command)
                        # Set cursor to end
                        self.app.call_later(setattr, self.app.input_widget, 'cursor_position', len(command))
                        self.app.call_later(self.app.input_widget.focus)
                    return {'action': 'edit_mode_engaged'}

                else: # cancel or unknown
                    return {'action': 'cancel'}

        except Exception as e:
            logger.error(f"Error in confirmation flow: {e}", exc_info=True)
            return {'action': 'cancel'}
        finally:
            self.confirmation_flow_active = False

    async def start_categorization_flow(self, command: str, ai_raw=None, original_input=None) -> dict:
        """Mimics the categorization flow."""
        if not self.app:
            return {'category': 'simple'}
            
        self.categorization_flow_active = True
        self.last_output_was_separator = False
        
        try:
            user_choice = await self.app.show_categorization_modal(command)
            
            mapping = {
                'simple': 'simple',
                'semi': 'semi_interactive',
                'tui': 'interactive_tui'
            }
            
            if user_choice in mapping:
                return {'action': 'categorize_and_execute', 'category': mapping[user_choice], 'command': command, 'save': True}
            else:
                return {'action': 'cancel_execution'}
                
        except Exception as e:
            logger.error(f"Error in categorization flow: {e}", exc_info=True)
            return {'action': 'cancel_execution'}
        finally:
            self.categorization_flow_active = False

    def update_status_bar(self, text: str, style: str = None) -> None:
        """Updates the status bar (Header subtitle in Textual)."""
        if self.app:
            self.app.call_later(setattr, self.app, 'sub_title', text)

    def add_interaction_separator(self) -> None:
        """Adds a visual separator to the log."""
        self.last_output_was_separator = True
        self.append_output("─" * 40, style_class="dim")

    def initialize_ui_elements(self, **kwargs):
        """Mock method for compatibility with main.py startup sequence."""
        return self.app

    async def prompt_for_caution_confirmation(self, command: str) -> dict:
        """Prompts for confirmation for dangerous commands."""
        if not self.app: return {'action': 'cancel'}
        result = await self.prompt_for_command_confirmation(command, "CAUTION: Dangerous Command")
        return {'action': 'confirm' if result['action'] == 'execute' else 'cancel'}

    async def prompt_for_api_input(self, prompt: str) -> str:
        """Mock for API input."""
        return ""

    # Mock methods for compatibility
    def set_normal_input_mode(self, handler=None, cwd=None): pass
    def set_edit_mode(self, text): pass
    def set_flow_input_mode(self, prompt): pass
    def get_app_instance(self): return self.app