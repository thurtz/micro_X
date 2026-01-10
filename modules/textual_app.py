from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Label, Static
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from rich.text import Text
from rich.markdown import Markdown
import asyncio
import logging

logger = logging.getLogger(__name__)

class ClickableLabel(Label):
    """A label that acts like a button/link."""
    def on_click(self) -> None:
        self.app.post_message(InlineConfirmation.Selected(self.id))

class InlineConfirmation(Vertical):
    """Integrated confirmation widget."""
    
    DEFAULT_CSS = """
    InlineConfirmation {
        height: auto;
        padding: 0 1;
        background: $surface;
    }

    #command_display {
        width: 100%;
        background: $boost;
        padding: 0 1;
        margin: 0;
        color: $text;
        text-style: bold;
        text-align: center;
    }
    
    Horizontal {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    ClickableLabel {
        padding: 0 1;
        margin: 0 1;
        color: $text;
        text-style: underline;
    }

    ClickableLabel:hover {
        background: $surface-lighten-1;
        color: $accent;
        text-style: bold underline;
    }

    .success { color: $success; }
    .primary { color: $primary; }
    .error { color: $error; }
    """

    class Selected(Message):
        def __init__(self, action: str):
            self.action = action
            super().__init__()

    def __init__(self, command: str, query: str, explanation_text: str = None):
        super().__init__()
        self.command = command
        self.user_query = query

    def compose(self) -> ComposeResult:
        yield Label(f"AI suggests: {self.command}", id="command_display")
        
        with Horizontal():
            yield ClickableLabel("Run", classes="success", id="execute")
            yield ClickableLabel("Simple", classes="primary", id="execute_simple")
            yield ClickableLabel("Semi", classes="primary", id="execute_semi")
            yield ClickableLabel("TUI", classes="primary", id="execute_tui")
            yield ClickableLabel("Explain", classes="default", id="explain")
            yield ClickableLabel("Modify", classes="default", id="modify")
            yield ClickableLabel("Cancel", classes="error", id="cancel")

class InlineCategorization(Vertical):
    """Inline categorization menu."""
    
    DEFAULT_CSS = """
    InlineCategorization {
        height: auto;
        padding: 0 1;
        background: $surface;
    }

    #command_display {
        width: 100%;
        background: $boost;
        padding: 0 1;
        margin: 0;
        color: $text;
        text-style: bold;
        text-align: center;
    }
    
    Horizontal {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    ClickableLabel {
        padding: 0 1;
        margin: 0 1;
        color: $text;
        text-style: underline;
    }

    ClickableLabel:hover {
        background: $surface-lighten-1;
        color: $accent;
        text-style: bold underline;
    }

    .success { color: $success; }
    .primary { color: $primary; }
    .error { color: $error; }
    """

    class Selected(Message):
        def __init__(self, action: str):
            self.action = action
            super().__init__()

    def __init__(self, command: str):
        super().__init__()
        self.command = command

    def compose(self) -> ComposeResult:
        yield Label(f"Categorize: {self.command}", id="command_display")
        
        with Horizontal():
            yield ClickableLabel("Simple", classes="primary", id="simple")
            yield ClickableLabel("Semi-Interactive", classes="primary", id="semi")
            yield ClickableLabel("TUI", classes="primary", id="tui")
            yield ClickableLabel("Cancel", classes="error", id="cancel")

class MicroXTextualApp(App):
    """The main Textual application for micro_X."""
    
    CSS = """
    Screen {
        background: #1e1e1e;
        layout: vertical;
    }

    #main_log {
        background: #1e1e1e;
        color: #d4d4d4;
        border: none;
        height: 1fr;
    }

    #interaction_zone {
        dock: bottom;
        height: 5;
        background: #252526;
        border-top: solid $primary;
        margin-bottom: 5;
        overflow-y: auto;
    }

    Input {
        dock: bottom;
        background: #252526;
        color: #cccccc;
        border: tall #333333;
        height: 5;
    }

    Input:focus {
        border: tall #007acc;
    }
    """

    BINDINGS = [
        Binding("f1", "help", "Help", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "cancel_or_clear", "Cancel/Clear", show=True),
        Binding("ctrl+l", "clear_screen", "Clear Output", show=True),
    ]

    def __init__(self, shell_engine=None, history=None, initial_logs=None, **kwargs):
        super().__init__(**kwargs)
        self.shell_engine = shell_engine
        self.history = history or []
        self.history_index = -1
        self.pending_input_future = None
        self.current_confirmation_future = None
        self.log_widget = None
        self._pending_logs = initial_logs or []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="main_log", highlight=True, markup=True)
        yield Vertical(id="interaction_zone")
        yield Input(placeholder="Command... [Ctrl+Shift+V] Paste | [Shift+Select & Ctrl+Shift+C] Copy")
        yield Footer()

    def action_clear_screen(self) -> None:
        if self.log_widget:
            self.log_widget.clear()

    def action_help(self) -> None:
        """Trigger the /help command."""
        if self.shell_engine:
            asyncio.create_task(self.shell_engine.handle_built_in_command("/help"))

    def action_cancel_or_clear(self) -> None:
        """Handle Ctrl+C: Cancel current interaction or clear input."""
        # 1. Cancel any active inline confirmation/categorization
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result("cancel")
            self.interaction_zone.remove_children()
            self.input_widget.focus()
            return

        # 2. Clear input if not empty
        if self.input_widget.value:
            self.input_widget.value = ""
            return
        
        # 3. If nothing else, maybe show a hint about Quitting?
        self.notify("Press Ctrl+Q to Quit", timeout=2)

    async def on_mount(self) -> None:
        self.log_widget = self.query_one("#main_log")
        self.log_widget.auto_scroll = True
        self.input_widget = self.query_one(Input)
        self.interaction_zone = self.query_one("#interaction_zone")
        self.input_widget.focus()
        
        # Flush initial logs
        for entry in self._pending_logs:
            if isinstance(entry, tuple):
                self.append_output(entry[1], entry[0])
            else:
                self.append_output(entry)
        self._pending_logs = []

    def on_inline_confirmation_selected(self, message: InlineConfirmation.Selected) -> None:
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result(message.action)
        self.interaction_zone.remove_children()
        self.input_widget.focus()

    def on_inline_categorization_selected(self, message: InlineCategorization.Selected) -> None:
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result(message.action)
        self.interaction_zone.remove_children()
        self.input_widget.focus()

    def key_up(self) -> None:
        if self.input_widget.has_focus:
            if not self.history: return
            if self.history_index == -1: self.history_index = len(self.history) - 1
            elif self.history_index > 0: self.history_index -= 1
            self.input_widget.value = self.history[self.history_index]
            self.input_widget.cursor_position = len(self.input_widget.value)

    def key_down(self) -> None:
        if self.input_widget.has_focus:
            if self.history_index == -1: return
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.input_widget.value = self.history[self.history_index]
            else:
                self.history_index = -1
                self.input_widget.value = ""
            self.input_widget.cursor_position = len(self.input_widget.value)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input: return

        self.history.append(user_input)
        self.history_index = -1
        self.input_widget.value = ""
        self.log_widget.write(Text(f"\n> {user_input}", style="bold yellow"))

        if self.pending_input_future and not self.pending_input_future.done():
            self.pending_input_future.set_result(user_input)
            self.pending_input_future = None
        elif self.shell_engine:
            # Correct flow: Check built-ins/aliases first
            was_builtin = await self.shell_engine.handle_built_in_command(user_input)
            if not was_builtin:
                asyncio.create_task(self.shell_engine.submit_user_input(user_input))

    def append_output(self, content: str, style_class: str = None) -> None:
        if not content: return
        if self.log_widget is None:
            self._pending_logs.append((style_class, content))
            return
        style = None
        if style_class == 'success': style = "green"
        elif style_class == 'error': style = "bold red"
        elif style_class == 'warning': style = "yellow"
        if content.strip().startswith(("#", "*", "-", "```")):
            self.log_widget.write(Markdown(content))
        else:
            self.log_widget.write(Text(content, style=style))

    def action_clear(self) -> None:
        self.log_widget.clear()

    def invalidate(self) -> None:
        self.refresh()

    async def show_confirmation_modal(self, command: str, query: str, explanation_text: str = None) -> str:
        await self.interaction_zone.remove_children()
        loop = asyncio.get_running_loop()
        self.current_confirmation_future = loop.create_future()
        widget = InlineConfirmation(command, query, explanation_text)
        await self.interaction_zone.mount(widget)
        return await self.current_confirmation_future

    async def show_categorization_modal(self, command: str) -> str:
        await self.interaction_zone.remove_children()
        loop = asyncio.get_running_loop()
        self.current_confirmation_future = loop.create_future()
        widget = InlineCategorization(command)
        await self.interaction_zone.mount(widget)
        return await self.current_confirmation_future

if __name__ == "__main__":
    app = MicroXTextualApp()
    app.run()