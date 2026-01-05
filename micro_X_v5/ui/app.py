# micro_X_v4/ui/app.py

import asyncio
import logging
from typing import Optional
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea, Label, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import PathCompleter, WordCompleter, FuzzyCompleter, merge_completers
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.shell import BashLexer

from ..core.events import EventBus, Event, EventType
from ..core.state import StateManager, AppState

logger = logging.getLogger(__name__)

class V5UIManager:
    def __init__(self, bus: EventBus, state_manager: StateManager, history, completion_words: list = None):
        self.bus = bus
        self.state = state_manager
        self.history = history
        self.app: Optional[Application] = None
        
        # Autocompletion setup
        words = completion_words or []
        word_completer = WordCompleter(words, ignore_case=True)
        path_completer = PathCompleter(expanduser=True)
        self.completer = FuzzyCompleter(merge_completers([word_completer, path_completer]))

        # Syntax Highlighting
        self.lexer = PygmentsLexer(BashLexer)

        # Styles
        self.style = Style.from_dict({
            'output-field': '#abb2bf',
            'input-field': '#d19a66',
            'status-bar': 'bg:#282c34 #abb2bf',
            'prompt': 'bold #61afef',
            'ai-thinking': 'italic #56b6c2',
            'ai-suggestion': 'bold #c678dd',
            'error': '#e06c75',
            'success': '#98c379',
            'warning': '#d19a66',
            # Pygments tokens (basic mappings for Bash)
            'pygments.keyword': 'bold #c678dd',
            'pygments.string': '#98c379',
            'pygments.operator': '#56b6c2',
            'pygments.name.builtin': '#e5c07b',
            'pygments.name.function': '#61afef',
            'pygments.comment': 'italic #5c6370',
        })

        # UI Components
        self.output_area = TextArea(
            text="micro_X V5 - Hybrid Edition\n" + ("="*40) + "\n",
            read_only=True,
            scrollbar=True,
            style='class:output-field'
        )
        
        self.input_area = TextArea(
            prompt=[('class:prompt', '(v5) > ')],
            multiline=False,
            style='class:input-field',
            history=self.history,
            completer=self.completer,
            lexer=self.lexer,
            auto_suggest=AutoSuggestFromHistory()
        )
        
        self.status_bar = Label(text=" Status: BOOTING | Ollama: UNKNOWN", style='class:status-bar')
        
        # Bindings
        self.kb = KeyBindings()
        self._setup_keybindings()

        # Listen for events
        self.bus.subscribe_async(EventType.STATE_CHANGED, self._on_state_changed)
        self.bus.subscribe_async(EventType.ERROR_OCCURRED, self._on_error)
        self.bus.subscribe_async(EventType.OLLAMA_STATUS_CHANGED, self._on_ollama_status)
        self.bus.subscribe_async(EventType.EXECUTION_OUTPUT, self._on_execution_output)
        self.bus.subscribe_async(EventType.AI_EXPLANATION_READY, self._on_explanation_ready)
        self.bus.subscribe_async(EventType.APP_SHUTDOWN, self._on_shutdown)

    def _setup_keybindings(self):
        @self.kb.add("c-c")
        def _(event):
            event.app.exit()

        @self.kb.add("enter")
        def _(event):
            # VERY IMPORTANT: Only handle input relevant to the current state!
            current_state = self.state.current_state
            
            # Read input and clear it immediately
            user_text = self.input_area.text.strip()
            self.input_area.text = ""

            if current_state == AppState.IDLE:
                if user_text:
                    self.append_text(f"\n(v5) > {user_text}\n")
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_INPUT_RECEIVED,
                        payload={'input': user_text},
                        sender="UIManager"
                    )))
            
            elif current_state == AppState.CONFIRMATION:
                choice = user_text.lower()
                
                if choice in ['1', 'y', 'yes', '']:
                    # Default confirmation (uses currently proposed category)
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED,
                        sender="UIManager"
                    )))
                elif choice == '2':
                    # Force Simple
                    self.state.context.proposed_category = 'simple'
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED,
                        sender="UIManager"
                    )))
                elif choice == '3':
                    # Force Semi-Interactive
                    self.state.context.proposed_category = 'semi_interactive'
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED,
                        sender="UIManager"
                    )))
                elif choice == '4':
                    # Force Interactive TUI
                    self.state.context.proposed_category = 'interactive_tui'
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED,
                        sender="UIManager"
                    )))
                elif choice in ['5', 'e', 'explain']:
                    cmd = self.state.context.proposed_command
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.AI_EXPLAIN_REQUESTED,
                        payload={'command': cmd},
                        sender="UIManager"
                    )))
                elif choice in ['6', 'm', 'modify']:
                    # Modify: Cancel confirmation, pre-fill input with command
                    cmd = self.state.context.proposed_command
                    
                    # We manually cancel the current flow
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CANCELLED,
                        sender="UIManager"
                    )))
                    
                    # And set the input text. 
                    self.input_area.text = cmd
                    # Move cursor to end
                    self.input_area.buffer.cursor_position = len(cmd)
                    
                elif choice in ['7', 'c', 'cancel', 'n', 'no']:
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CANCELLED,
                        sender="UIManager"
                    )))
                else:
                    self.append_text("\n⚠️ Invalid choice. Use 1-4 to run, 5 to explain, 7 to cancel.\n")

            elif current_state == AppState.CATEGORIZATION:
                choice = user_text.lower()
                cmd = self.state.context.proposed_command
                
                cat_map = {
                    '1': 'simple',
                    '2': 'semi_interactive',
                    '3': 'interactive_tui'
                }
                
                if choice in cat_map:
                    # Save and Run
                    # We need to trigger a SAVE logic? Or just pass category to execution?
                    # The requirement is to save it.
                    # We can use a new event CATEGORIZATION_SAVED or reuse USER_CONFIRMED with extra payload.
                    # Let's use a new event or rely on Logic to handle saving?
                    # LogicEngine listens to USER_CONFIRMED.
                    # We'll publish USER_CONFIRMED but update the context first?
                    # StateManager context update is not directly accessible from here cleanly (async).
                    
                    # Better: Publish CATEGORY_SELECTED event.
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED, # Reusing logic flow
                        payload={'category': cat_map[choice], 'save': True},
                        sender="UIManager"
                    )))
                elif choice == '4':
                    # Modify
                    self.input_area.text = cmd
                    self.input_area.buffer.cursor_position = len(cmd)
                    asyncio.create_task(self.bus.publish(Event(EventType.USER_CANCELLED))) # Go to IDLE
                elif choice == '5':
                    # Run once (default semi)
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED,
                        payload={'category': 'semi_interactive', 'save': False},
                        sender="UIManager"
                    )))
                elif choice == '6':
                    asyncio.create_task(self.bus.publish(Event(EventType.USER_CANCELLED)))
                else:
                    self.append_text("\n⚠️ Invalid choice.\n")

            elif current_state == AppState.CAUTION:
                choice = user_text.lower()
                if choice in ['1', 'y', 'yes']:
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CONFIRMED,
                        sender="UIManager"
                    )))
                elif choice in ['7', 'n', 'no', 'c', 'cancel', '']: # Default to cancel for caution
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CANCELLED,
                        sender="UIManager"
                    )))
                else:
                    self.append_text("\n⚠️ Invalid choice. Use 1 (Confirm) or 7 (Cancel).\n")

            elif current_state == AppState.ERROR_RECOVERY:
                choice = user_text.lower()
                if choice in ['1', 'y', 'yes', '']:
                    # Trigger analysis
                    failed_cmd = self.state.context.failed_command
                    failed_out = self.state.context.failed_output
                    
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.AI_ANALYZE_ERROR, 
                        payload={'command': failed_cmd, 'output': failed_out},
                        sender="UIManager"
                    )))
                else:
                    # Ignore/Cancel
                    asyncio.create_task(self.bus.publish(Event(
                        type=EventType.USER_CANCELLED,
                        sender="UIManager"
                    )))

        @self.kb.add("escape")
        def _(event):
            if self.state.current_state in [AppState.CONFIRMATION, AppState.CAUTION, AppState.ERROR_RECOVERY]:
                asyncio.create_task(self.bus.publish(Event(
                    type=EventType.USER_CANCELLED,
                    sender="UIManager"
                )))

        @self.kb.add("pageup")
        def _(event):
            # Move cursor back significantly to force scroll up
            b = self.output_area.buffer
            new_pos = max(0, b.cursor_position - 1000)
            b.cursor_position = new_pos

        @self.kb.add("pagedown")
        def _(event):
            b = self.output_area.buffer
            new_pos = min(len(b.text), b.cursor_position + 1000)
            b.cursor_position = new_pos

    def append_text(self, text: str):
        """Helper to append text to the output area and scroll."""
        self.output_area.text += text
        # Scroll to end
        self.output_area.buffer.cursor_position = len(self.output_area.text)

    async def _on_state_changed(self, event: Event):
        new_state = event.payload.get('new')
        self._update_status_bar()
        
        if new_state == AppState.PROCESSING:
            self.append_text("\n[AI is thinking...]\n")
        
        elif new_state == AppState.CONFIRMATION:
            cmd = self.state.context.proposed_command
            cat = self.state.context.proposed_category
            self.append_text(f"\n🤖 AI Suggestion: {cmd}")
            self.append_text(f"\n📂 Category: {cat or 'Unknown'}\n")
            self.append_text("Action:\n")
            self.append_text("  [1] Yes (Confirm & Categorize)\n")
            self.append_text("  [2] Run Once as Simple\n")
            self.append_text("  [3] Run Once as Semi-Interactive\n")
            self.append_text("  [4] Run Once as TUI\n")
            self.append_text("  [5] Explain\n")
            self.append_text("  [6] Modify\n")
            self.append_text("  [7] Cancel\n")
            self.append_text("Choice (1-7): ")
            if self.app:
                self.app.layout.focus(self.input_area)

        elif new_state == AppState.CATEGORIZATION:
            cmd = self.state.context.proposed_command
            self.append_text(f"\n📂 Unknown Command: '{cmd}'\n")
            self.append_text("How should this command run?\n")
            self.append_text("  [1] simple             (Direct output)\n")
            self.append_text("  [2] semi_interactive   (Tmux, wait)\n")
            self.append_text("  [3] interactive_tui    (Tmux, interactive)\n")
            self.append_text("  [4] Modify command\n")
            self.append_text("  [5] Run once (Don't save)\n")
            self.append_text("  [6] Cancel\n")
            self.append_text("Choice (1-6): ")
            if self.app:
                self.app.layout.focus(self.input_area)

        elif new_state == AppState.CAUTION:
            cmd = self.state.context.proposed_command
            self.append_text(f"\n⚠️  SECURITY CAUTION: '{cmd}' is a sensitive command.\n")
            self.append_text("Are you sure you want to run it?\n")
            self.append_text("  [1] Yes (Confirm)\n")
            self.append_text("  [7] No (Cancel)\n")
            self.append_text("Choice (1/7): ")
            if self.app:
                self.app.layout.focus(self.input_area)

        elif new_state == AppState.ERROR_RECOVERY:
            self.append_text(f"\n⚠️  Command failed (Exit Code: Non-Zero)\n")
            self.append_text("Action:\n")
            self.append_text("  [1] Analyze Error with AI\n")
            self.append_text("  [7] Ignore (Return to prompt)\n")
            self.append_text("Choice (1/7): ")
            if self.app:
                self.app.layout.focus(self.input_area)
            
        elif new_state == AppState.EXECUTING:
            self.append_text(f"\n[Running Command...]\n")
        
        elif new_state == AppState.IDLE:
             if self.app:
                 self.app.layout.focus(self.input_area)

        if self.app:
            self.app.invalidate()

    async def _on_error(self, event: Event):
        msg = event.payload.get('message', "Unknown error")
        self.append_text(f"\n❌ Error: {msg}\n")
        if self.app:
            self.app.invalidate()

    async def _on_ollama_status(self, event: Event):
        self._update_status_bar()
        if self.app:
            self.app.invalidate()

    def _update_status_bar(self):
        state_name = self.state.current_state.name
        # Note: We'd ideally track ollama status in the StateContext too
        self.status_bar.text = f" Status: {state_name}"

    async def _on_execution_output(self, event: Event):
        text = event.payload.get('output', "")
        is_err = event.payload.get('is_stderr', False)
        prefix = "! " if is_err else "  "
        self.append_text(f"{prefix}{text}\n")
        if self.app:
            self.app.invalidate()

    async def _on_explanation_ready(self, event: Event):
        explanation = event.payload.get('explanation', "No explanation available.")
        self.append_text(f"\n{explanation}\n")
        
        # Only re-prompt if we are still in a confirmation flow
        if self.state.current_state == AppState.CONFIRMATION:
            self.append_text("\nChoice (1-7): ")
            
        if self.app:
            self.app.invalidate()

    async def _on_shutdown(self, event: Event):
        if self.app:
            self.app.exit()

    def build_app(self) -> Application:
        root_container = HSplit([
            Frame(self.output_area, title="Output Log"),
            self.input_area,
            self.status_bar
        ])
        
        self.main_layout = Layout(root_container, focused_element=self.input_area)
        
        self.app = Application(
            layout=self.main_layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True
        )
        return self.app
