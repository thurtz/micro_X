#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
import asyncio
import subprocess
import uuid
import shlex
import os
import re
import ollama  #  Import ollama here
import logging  # Import the logging module
from prompt_toolkit.application import get_app
import json # Import json

# Set up logging
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "micro_x.log")
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the directory exists

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),  # Log to file
    ]
)
logger = logging.getLogger(__name__)  # Get a logger instance

# Load command categories from JSON file
CATEGORY_PATH = "config/command_categories.json"  #  Path to the JSON file
CATEGORY_MAP = {
    "1": "simple",
    "2": "semi_interactive",
    "3": "interactive_tui",
    "simple": "simple",
    "semi_interactive": "semi_interactive",
    "interactive_tui": "interactive_tui",
}


def load_command_categories():
    """Load command categories from a JSON file."""
    if os.path.exists(CATEGORY_PATH):
        try:
            with open(CATEGORY_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Error decoding command_categories.json.  Returning default categories.")
            return {
                "interactive_tui": [],
                "semi_interactive": [],
                "simple": []
            }
    else:
        logger.info("command_categories.json not found.  Returning default categories.")
        return {
            "interactive_tui": [],
            "semi_interactive": [],
            "simple": []
        }


def classify_command(cmd):
    """Classify a command into a category."""
    known = load_command_categories()
    for category, commands in known.items():
        if cmd in commands:
            return category
    return "simple"  # Default category if not found


# Globals
output_buffer = []
output_field = None
input_field = None
key_help_field = None
app = None
auto_scroll = True
current_directory = os.getcwd()  # Keep track of the current directory

kb = KeyBindings()

@kb.add('c-c')
@kb.add('c-d')
def _(event):
    event.app.exit()

@kb.add('c-n')
def _(event):
    event.current_buffer.insert_text('\n')

@kb.add('enter')
def _(event):
    buff = event.current_buffer
    if not buff.complete_state:
        buff.validate_and_handle()

@kb.add('tab')
def _(event):
    """Insert tab character unless completions are active."""
    buff = event.current_buffer
    if not buff.complete_state:  # No active completion menu
        event.current_buffer.insert_text('    ')  # insert 4 spaces (or use '\t' for tab char)
    else:
        event.app.current_buffer.complete_next()  # fallback to tab completion behavior

@kb.add('pageup')
def _(event):
    if output_field and output_field.window.render_info:
        output_field.window._scroll_up()

@kb.add('pagedown')
def _(event):
    if output_field and output_field.window.render_info:
        output_field.window._scroll_down()

@kb.add('c-up')
def _(event):
    b = event.current_buffer
    b.cursor_up(count=1)

@kb.add('c-down')
def _(event):
    b = event.current_buffer
    b.cursor_down(count=1)

@kb.add('up')
def _(event):
    b = event.current_buffer
    if b.history_backward():
        b.document = Document(text=b.text, cursor_position=len(b.text))
        event.app.invalidate()

@kb.add('down')
def _(event):
    b = event.current_buffer
    if b.history_forward():
        b.document = Document(text=b.text, cursor_position=len(b.text))
        event.app.invalidate()


def append_output(text: str):
    """Append text to the output area."""
    if not text.endswith('\n'):
        text += '\n'
    output_buffer.append(text)

    if output_field:
        new_text = ''.join(output_buffer)
        buffer = output_field.buffer
        buffer.set_document(Document(new_text, cursor_position=len(new_text)), bypass_readonly=True)
        async def refresh():
            await asyncio.sleep(0.01)
            get_app().invalidate()
        get_app().create_background_task(refresh())



def handle_input(user_input):
    """Handle user input and execute commands."""
    global current_directory
    user_input = user_input.strip()
    logger.debug(f"Input: {user_input}") # Log the input

    if not user_input:
        return  # Ignore empty input

    if user_input in {"exit", "quit", "/exit", "/quit"}:
        append_output("Exiting micro_X Shell")
        logger.info("Exiting micro_X")
        get_app().exit()
        return

    if user_input.startswith("/ai "):
        human_query = user_input[4:].strip()
        linux_command = interpret_human_input(human_query) # Call the AI interpreter
        if linux_command:
            append_output(f"AI: {linux_command}")
            category = classify_command(linux_command)
            logger.info(f"Command Category: {category}")
            if category == "simple":
                execute_shell_command(linux_command)
            else:
                execute_command_in_tmux(linux_command) # Execute the AI's command in tmux
        else:
            append_output("AI could not process the request.")
        return

    # Handle 'cd' command directly
    if user_input.startswith("cd "):
        new_dir = os.path.abspath(os.path.join(current_directory, user_input.split("cd ", 1)[1].strip()))
        if os.path.isdir(new_dir):
            current_directory = new_dir
            append_output(f"📂 Changed directory to: {current_directory}")
            return
        else:
            append_output(f"❌ Error: Directory '{new_dir}' does not exist.")
            return

    # Sanitize and validate the command (you can expand this)
    command = sanitize_and_validate(user_input)  # Use the function
    if command:
        category = classify_command(command)
        logger.info(f"Command Category: {category}")
        if category == "simple":
            execute_shell_command(command)
        else:
            execute_command_in_tmux(command) # Execute all commands in tmux
    else:
        append_output(f"⚠️  Command blocked: {user_input}") # Or this

def sanitize_and_validate(command):
    """Sanitize and validate the command before execution."""
    dangerous_patterns = [
        r'\brm\s+-rf\s+/.*',
        r'\bmkfs\b',
        r'\bdd\b',
        r'\bshutdown\b',
        r'\breboot\b',
        r'\bhalt\b',
        r'\bpoweroff\b',
        r'>\s*/dev/sd.*',
        r':>\s*/'
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            logger.warning(f"Command blocked: {command}")
            return None  # Return None for blocked commands
    return command
    
def execute_command_in_tmux(command):
    """Execute a command in a new tmux window."""
    try:
        unique_id = str(uuid.uuid4())[:8]
        window_name = f"micro_x_{unique_id}"  # Unique window name
        tmux_command = ["tmux", "new-window", "-n", window_name, command]
        logger.info(f"Executing in tmux: {tmux_command}")
        subprocess.run(tmux_command)
    except FileNotFoundError:
        append_output("Error: tmux not found. Please ensure tmux is installed.")
        logger.error("tmux not found")
    except Exception as e:
        append_output(f"❌ Error launching command in tmux: {e}")
        logger.exception(f"Error launching command in tmux: {e}")



def execute_shell_command(command):
    """Execute a shell command and display the output."""
    try:
        parts = shlex.split(command)
        process = subprocess.Popen(
            parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=current_directory,
            text=True
        )
        stdout, stderr = process.communicate()

        if stdout:
            append_output(stdout)
        if stderr:
            append_output(f"❌ Error:\n{stderr}")
    except FileNotFoundError:
        append_output(f"❌ Command not found: {command}")
        logger.error(f"Command not found: {command}")
    except Exception as e:
        append_output(f"❌ Error executing command: {e}")
        logger.exception(f"Error executing command: {e}")

def run_shell(on_input, history=None, completer=None):
    """Run the fullscreen shell application."""
    global output_field, input_field, key_help_field, app, auto_scroll

    output_field = TextArea(
        text="Welcome to micro_X\n",
        style='class:output-field',
        scrollbar=True,
        focusable=False,
        wrap_lines=True,
        read_only=True
    )

    input_field = TextArea(
        height=4,
        prompt='> ',
        style='class:input-field',
        multiline=True,
        wrap_lines=False,
        history=history,
        completer=completer
    )
    input_field.buffer.accept_handler = lambda buff: handle_input(buff.text) # Change Here

    key_help_field = Window(
        content=FormattedTextControl(
            text=" Ctrl+N = newline | Enter = submit | Ctrl+C/D = exit | Tab = complete | PageUp/PageDown = scroll"
        ),
        height=1,
        style='class:key-help'
    )

    layout = HSplit([
        output_field,
        Window(height=1, char='─', style='class:line'),
        input_field,
        key_help_field
    ])

    style = Style.from_dict({
        'output-field': 'bg:#1e1e1e #d4d4d4',
        'input-field': 'bg:#1e1e1e #ffffff',
        'key-help': 'bg:#1e1e1e #888888',
        'line': '#444444',
    })

    def on_cursor_position_changed(_):
        """Handle cursor position changes in the output area for auto-scrolling."""
        global auto_scroll
        doc = output_field.buffer.document
        cursor_row = doc.cursor_position_row
        total_rows = doc.line_count
        window = output_field.window.render_info
        if window:
            height = window.content_height
            if total_rows - cursor_row > height:
                auto_scroll = False
            else:
                auto_scroll = True
    output_field.buffer.on_cursor_position_changed += on_cursor_position_changed

    app = Application(
        layout=Layout(layout, focused_element=input_field),
        key_bindings=kb,
        style=style,
        full_screen=True,
        mouse_support=True
    )

    try:
        app.run()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        logger.info("Exiting micro_X due to KeyboardInterrupt or EOFError")

def interpret_human_input(human_input):
    """Sends human input to Ollama for Linux command translation."""
    try:
        response = ollama.chat(
            model='llama3.2',  # Or another model you have available in Ollama
            messages=[
                {
                    'role': 'user',
                    'content': f'You are a Linux command interpreter. Translate this human input to a single best matching Linux command: "{human_input}". Only respond with the Linux command.'
                }
            ]
        )
        linux_command = response['message']['content'].strip()
        logger.debug(f"AI interpreted '{human_input}' as: '{linux_command}'")
        return linux_command
    except ollama.OllamaAPIError as e:
        error_message = f"Error communicating with Ollama: {e}"
        print(error_message)
        logger.error(error_message)
        return None  # Important: Return None on error
    except Exception as e:
        error_message = f"Error during Ollama interaction: {e}"
        print(error_message)
        logger.exception(error_message)
        return None  # Important: Return None on error



if __name__ == "__main__":
    def handle_user_input(user_input):
        """Placeholder for handling user input."""
        print(f"You entered: {user_input}")
        append_output(f"Received: {user_input}")

    run_shell(handle_user_input)
