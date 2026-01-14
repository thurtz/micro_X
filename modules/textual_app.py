from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, TextArea, RichLog, Label, Static, OptionList, Input
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from rich.text import Text
from rich.markdown import Markdown
from textual import events
import asyncio
import logging

logger = logging.getLogger(__name__)

class HistorySearchScreen(Screen):
    """Screen for searching command history."""
    
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, history: list[str]):
        super().__init__()
        self.history = history

    def compose(self) -> ComposeResult:
        yield Label("Search History:", classes="search-label")
        yield Input(placeholder="Type to filter...", id="search_input")
        yield OptionList(id="search_results")

    def on_mount(self) -> None:
        self.query_one("#search_input").focus()
        self.update_results("")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_results(event.value)

    def update_results(self, query: str) -> None:
        results = self.query_one("#search_results")
        results.clear_options()
        if not query:
            matches = self.history[:20]
        else:
            q = query.lower()
            matches = [h for h in self.history if q in h.lower()]
            seen = set()
            unique_matches = []
            for m in matches:
                if m not in seen:
                    unique_matches.append(m)
                    seen.add(m)
            matches = unique_matches[:50]

        for m in matches:
            results.add_option(Option(m))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)

class KeyHint(Static):
    """Clickable hint for the top bar."""
    def __init__(self, label: str, action: str, classes: str = ""):
        super().__init__(label, classes=classes)
        self.action_name = action
    
    async def on_click(self, event: events.Click) -> None:
        await self.app.run_action(self.action_name)

class KeyHintBar(Horizontal):
    """Display interactive key bindings at the top."""
    DEFAULT_CSS = """
    KeyHintBar {
        dock: top;
        height: 1;
        background: #252526;
        color: #cccccc;
    }
    KeyHint {
        padding: 0 1;
        width: auto;
        color: #cccccc;
    }
    KeyHint:hover {
        text-style: bold;
        background: $primary; 
        color: white;
    }
    .spacer {
        width: 1fr;
    }
    .quit {
        background: $error;
        color: white;
        text-style: bold;
    }
    """
    def compose(self) -> ComposeResult:
        yield KeyHint("F1 Help", "help")
        yield KeyHint("^D Docs", "docs")
        yield KeyHint("^R Search", "history_search")
        yield KeyHint("^T Shell", "spawn_shell")
        yield KeyHint("^L Clear", "clear_screen")
        yield KeyHint("^C Cancel", "cancel_or_clear")
        
        yield Static(classes="spacer")
        
        yield KeyHint("^Q Quit", "quit", classes="quit")

class KeyboardSelectableLabel(Label):
    """A label that can be focused and activated via keyboard or mouse."""
    
    can_focus = True

    BINDINGS = [
        Binding("enter", "activate", "Select", show=False),
        Binding("space", "activate", "Select", show=False),
    ]

    def on_click(self) -> None:
        self.action_activate()

    def action_activate(self) -> None:
        self.app.post_message(InlineConfirmation.Selected(self.id))

class InlineConfirmation(Vertical):
    """Integrated confirmation widget."""
    
    BINDINGS = [
        Binding("left", "prev_item", "Previous", show=False),
        Binding("right", "next_item", "Next", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def action_cancel(self) -> None:
        self.app.post_message(self.Selected("cancel"))

    def action_next_item(self) -> None:
        self._cycle_focus(1)

    def action_prev_item(self) -> None:
        self._cycle_focus(-1)

    def _cycle_focus(self, direction: int) -> None:
        items = [c for c in self.query("KeyboardSelectableLabel")]
        if not items: return
        
        current = self.app.focused
        try:
            current_index = items.index(current)
            next_index = (current_index + direction) % len(items)
            items[next_index].focus()
        except ValueError:
            items[0].focus()

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

    KeyboardSelectableLabel {
        padding: 0 1;
        margin: 0 1;
        color: $text;
        text-style: underline;
        border: none;
    }

    KeyboardSelectableLabel:hover {
        background: $surface-lighten-1;
        color: $accent;
        text-style: bold underline;
    }

    KeyboardSelectableLabel:focus {
        background: $primary;
        color: $text;
        text-style: bold;
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
            yield KeyboardSelectableLabel("Run Once", classes="success", id="execute")
            yield KeyboardSelectableLabel("Simple", classes="primary", id="execute_simple")
            yield KeyboardSelectableLabel("Semi", classes="primary", id="execute_semi")
            yield KeyboardSelectableLabel("TUI", classes="primary", id="execute_tui")
            yield KeyboardSelectableLabel("Explain", classes="default", id="explain")
            yield KeyboardSelectableLabel("Modify", classes="default", id="modify")
            yield KeyboardSelectableLabel("Cancel", classes="error", id="cancel")

class InlineCategorization(Vertical):
    """Inline categorization menu."""
    
    BINDINGS = [
        Binding("left", "prev_item", "Previous", show=False),
        Binding("right", "next_item", "Next", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def action_cancel(self) -> None:
        self.app.post_message(self.Selected("cancel"))

    def action_next_item(self) -> None:
        self._cycle_focus(1)

    def action_prev_item(self) -> None:
        self._cycle_focus(-1)

    def _cycle_focus(self, direction: int) -> None:
        items = [c for c in self.query("KeyboardSelectableLabel")]
        if not items: return
        
        current = self.app.focused
        try:
            current_index = items.index(current)
            next_index = (current_index + direction) % len(items)
            items[next_index].focus()
        except ValueError:
            items[0].focus()

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

    KeyboardSelectableLabel {
        padding: 0 1;
        margin: 0 1;
        color: $text;
        text-style: underline;
    }

    KeyboardSelectableLabel:hover {
        background: $surface-lighten-1;
        color: $accent;
        text-style: bold underline;
    }

    KeyboardSelectableLabel:focus {
        background: $primary;
        color: $text;
        text-style: bold;
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
            yield KeyboardSelectableLabel("Run Once", classes="success", id="execute")
            yield KeyboardSelectableLabel("Simple", classes="primary", id="simple")
            yield KeyboardSelectableLabel("Semi-Interactive", classes="primary", id="semi")
            yield KeyboardSelectableLabel("TUI", classes="primary", id="tui")
            yield KeyboardSelectableLabel("Cancel", classes="error", id="cancel")

class InlineSafetyWarning(Vertical):
    """Integrated safety warning widget."""
    
    BINDINGS = [
        Binding("left", "prev_item", "Previous", show=False),
        Binding("right", "next_item", "Next", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def action_cancel(self) -> None:
        self.app.post_message(self.Selected("cancel"))

    def action_next_item(self) -> None:
        self._cycle_focus(1)

    def action_prev_item(self) -> None:
        self._cycle_focus(-1)

    def _cycle_focus(self, direction: int) -> None:
        items = [c for c in self.query("KeyboardSelectableLabel")]
        if not items: return
        
        current = self.app.focused
        try:
            current_index = items.index(current)
            next_index = (current_index + direction) % len(items)
            items[next_index].focus()
        except ValueError:
            items[0].focus()

    DEFAULT_CSS = """
    InlineSafetyWarning {
        height: auto;
        padding: 0 1;
        background: $error-darken-2;
    }

    #warning_display {
        width: 100%;
        background: $error;
        padding: 0 1;
        margin: 0;
        color: white;
        text-style: bold;
        text-align: center;
    }
    
    Horizontal {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    KeyboardSelectableLabel {
        padding: 0 1;
        margin: 0 1;
        color: white;
        text-style: underline;
    }

    KeyboardSelectableLabel:hover {
        background: $error-lighten-1;
        text-style: bold underline;
    }

    KeyboardSelectableLabel:focus {
        background: white;
        color: $error;
        text-style: bold;
    }
    """

    class Selected(Message):
        def __init__(self, action: str):
            self.action = action
            super().__init__()

    def __init__(self, command: str, reason: str = "Potentially Dangerous Command"):
        super().__init__()
        self.command = command
        self.reason = reason

    def compose(self) -> ComposeResult:
        yield Label(f"⚠️ {self.reason}: {self.command}", id="warning_display")
        
        with Horizontal():
            yield KeyboardSelectableLabel("Cancel", id="cancel")
            yield KeyboardSelectableLabel("Proceed Anyway", id="proceed")

class CommandInput(TextArea):
    """Custom TextArea for command input that handles Enter key for submission."""
    
    BINDINGS = [
        Binding("enter", "submit", "Submit Command", show=False),
        Binding("up", "history_up", "History Up", show=False),
        Binding("down", "history_down", "History Down", show=False),
        Binding("ctrl+r", "history_search", "Search History", show=True),
        Binding("ctrl+d", "docs", "Docs", show=True),
    ]

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.action_submit()
        elif event.key == "up":
            event.prevent_default()
            event.stop()
            self.action_history_up()
        elif event.key == "down":
            event.prevent_default()
            event.stop()
            self.action_history_down()

    def action_submit(self) -> None:
        """Submit the command."""
        self.app.action_submit_command()

    def action_history_up(self) -> None:
        self.app.action_history_up()

    def action_history_down(self) -> None:
        self.app.action_history_down()

    def action_history_search(self) -> None:
        self.app.action_history_search()

    def action_docs(self) -> None:
        self.app.action_docs()

class MicroXTextualApp(App):
    """The main Textual application for micro_X."""
    
    CSS = """
    Screen {
        background: #1e1e1e;
        layout: vertical;
    }

    Footer {
        dock: top;
    }

    .hidden {
        display: none;
    }

    #main_log {
        background: #1e1e1e;
        color: #d4d4d4;
        border: none;
        height: 1fr;
    }

    #bottom_container {
        dock: bottom;
        height: 5;
        background: #252526;
    }

    #interaction_zone {
        height: 100%;
        border-top: solid $primary;
        overflow-y: auto;
        background: #252526;
        align: center middle;
    }

    CommandInput {
        height: 100%;
        border: tall #333333;
        background: #252526;
        color: #cccccc;
    }

    CommandInput:focus {
        border: tall #007acc;
    }

    HistorySearchScreen {
        align: center middle;
        background: #1e1e1e 80%; /* Semi-transparent overlay */
    }

    HistorySearchScreen > Label {
        margin-top: 1;
        width: 80%;
        color: $accent;
        text-style: bold;
    }

    HistorySearchScreen > Input {
        width: 80%;
        margin-bottom: 1;
    }

    HistorySearchScreen > OptionList {
        width: 80%;
        height: 60%;
        border: tall $primary;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("f1", "help", "Help", show=True),
        Binding("ctrl+d", "docs", "Docs", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "cancel_or_clear", "Cancel", show=True),
        Binding("ctrl+l", "clear_screen", "Clear", show=True),
        Binding("ctrl+r", "history_search", "Search", show=True),
        Binding("ctrl+t", "spawn_shell", "Shell", show=True),
    ]

    def __init__(self, shell_engine=None, history=None, initial_logs=None, history_path=None, **kwargs):
        super().__init__(**kwargs)
        self.shell_engine = shell_engine
        # Ensure history is chronologically ordered (Old -> New)
        self.history = list(reversed(history or []))
        self.history_path = history_path
        self.history_index = -1
        self.pending_input_future = None
        self.current_confirmation_future = None
        self.log_widget = None
        self._pending_logs = initial_logs or []

    def action_spawn_shell(self) -> None:
        """Spawn a new shell in a tmux window."""
        if self.shell_engine:
            shell_cmd = self.shell_engine.config.get("behavior", {}).get("default_shell_command", "bash")
            # We use 'interactive_tui' category to treat it as a foreground TUI application (which a shell is)
            asyncio.create_task(self.shell_engine.execute_command_in_tmux(shell_cmd, "New Shell Session", "interactive_tui"))

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()
        yield RichLog(id="main_log", highlight=True, markup=True, wrap=True)
        with Vertical(id="bottom_container"):
            yield Vertical(id="interaction_zone", classes="hidden")
            yield CommandInput(id="input_field", soft_wrap=True, placeholder="Command... [Ctrl+Shift+V] Paste | [Shift+Select & Ctrl+Shift+C] Copy")

    def show_status(self, message: str) -> None:
        """Display a status message in the interaction zone (swapping out input)."""
        self.interaction_zone.remove_children()
        self.interaction_zone.mount(Label(message))
        self.switch_to_menu()

    def clear_status(self) -> None:
        """Clear status and return to input."""
        self.switch_to_input()

    def action_clear_screen(self) -> None:
        if self.log_widget:
            self.log_widget.clear()

    def action_help(self) -> None:
        """Trigger the /help command."""
        if self.shell_engine:
            asyncio.create_task(self.shell_engine.handle_built_in_command("/help"))

    def action_docs(self) -> None:
        """Trigger the /docs command."""
        if self.shell_engine:
            asyncio.create_task(self.shell_engine.handle_built_in_command("/docs"))

    def action_cancel_or_clear(self) -> None:
        """Handle Ctrl+C: Cancel current interaction or clear input."""
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result("cancel")
            self.switch_to_input()
            return

        if self.input_widget.text:
            self.input_widget.text = ""
            return
        
        self.notify("Press Ctrl+Q to Quit", timeout=2)

    def switch_to_menu(self) -> None:
        self.input_widget.add_class("hidden")
        self.interaction_zone.remove_class("hidden")

    def switch_to_input(self) -> None:
        self.interaction_zone.remove_children()
        self.interaction_zone.add_class("hidden")
        self.input_widget.remove_class("hidden")
        self.input_widget.focus()

    async def on_mount(self) -> None:
        self.log_widget = self.query_one("#main_log")
        self.log_widget.auto_scroll = True
        self.input_widget = self.query_one("#input_field")
        self.interaction_zone = self.query_one("#interaction_zone")
        self.input_widget.focus()
        
        for entry in self._pending_logs:
            if isinstance(entry, tuple):
                self.append_output(entry[1], entry[0])
            else:
                self.append_output(entry)
        self._pending_logs = []

    def on_inline_confirmation_selected(self, message: InlineConfirmation.Selected) -> None:
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result(message.action)
        self.switch_to_input()

    def on_inline_categorization_selected(self, message: InlineCategorization.Selected) -> None:
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result(message.action)
        self.switch_to_input()

    def action_submit_command(self) -> None:
        cmd = self.input_widget.text.strip()
        if cmd:
            self.handle_input_submission(cmd)
            self.input_widget.text = ""

    def action_history_up(self) -> None:
        self.history_up()

    def action_history_down(self) -> None:
        self.history_down()

    def action_history_search(self) -> None:
        def on_search_complete(result: str | None) -> None:
            if result:
                self.input_widget.text = result
                self.input_widget.move_cursor((0, len(result)))
            self.input_widget.focus()

        self.push_screen(HistorySearchScreen(self.history), on_search_complete)

    def _save_to_history_file(self, value: str) -> None:
        """Append a command to the persistent history file."""
        if not self.history_path:
            return
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(f"# {timestamp}\n")
                f.write(f"+{value}\n")
        except Exception as e:
            logger.error(f"Failed to save history to {self.history_path}: {e}")

    def handle_input_submission(self, value: str) -> None:
        if self.pending_input_future and not self.pending_input_future.done():
            self.pending_input_future.set_result(value)
            self.pending_input_future = None
        else:
            # Normal command submission
            if value:
                self.history.append(value)
                self.history_index = -1
                self._save_to_history_file(value)
                if self.shell_engine and self.shell_engine.main_normal_input_accept_handler_ref:
                    self.shell_engine.main_normal_input_accept_handler_ref(value)

    def history_up(self) -> None:
        if not self.history:
            return
        if self.history_index == -1:
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        
        val = self.history[self.history_index]
        self.input_widget.text = val
        self._move_cursor_to_end()

    def history_down(self) -> None:
        if self.history_index == -1:
            return
        
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.input_widget.text = self.history[self.history_index]
        else:
            self.history_index = -1
            self.input_widget.text = ""
        
        self._move_cursor_to_end()

    def _move_cursor_to_end(self) -> None:
        lines = self.input_widget.text.split('\n')
        row = max(0, len(lines) - 1)
        col = len(lines[row])
        self.input_widget.move_cursor((row, col))

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
        self.switch_to_menu()
        # Focus the first option ("Run" usually)
        widget.query_one("#execute").focus()
        return await self.current_confirmation_future

    async def show_categorization_modal(self, command: str) -> str:
        await self.interaction_zone.remove_children()
        loop = asyncio.get_running_loop()
        self.current_confirmation_future = loop.create_future()
        widget = InlineCategorization(command)
        await self.interaction_zone.mount(widget)
        self.switch_to_menu()
        # Focus the first option
        widget.query_one("#simple").focus()
        return await self.current_confirmation_future

    async def show_safety_modal(self, command: str, reason: str = "Caution") -> bool:
        await self.interaction_zone.remove_children()
        loop = asyncio.get_running_loop()
        self.current_confirmation_future = loop.create_future()
        widget = InlineSafetyWarning(command, reason)
        await self.interaction_zone.mount(widget)
        self.switch_to_menu()
        # Focus Cancel by default for safety
        widget.query_one("#cancel").focus()
        result = await self.current_confirmation_future
        return result == 'proceed'

    def on_inline_safety_warning_selected(self, message: InlineSafetyWarning.Selected) -> None:
        if self.current_confirmation_future and not self.current_confirmation_future.done():
            self.current_confirmation_future.set_result(message.action)
        self.switch_to_input()

if __name__ == "__main__":
    app = MicroXTextualApp()
    app.run()