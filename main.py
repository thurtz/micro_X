#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.application import get_app
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.formatted_text import FormattedText # Added for styled output

import asyncio
import subprocess
import uuid
import shlex
import os
import re
import ollama
import logging
import json
import time
import shutil
import hashlib # For checking file changes
import sys # Added for /utils command to use the current Python interpreter

# --- Configuration Constants (File Names & Static Values) ---
LOG_DIR = "logs"
CONFIG_DIR = "config"
DEFAULT_CATEGORY_FILENAME = "default_command_categories.json"
USER_CATEGORY_FILENAME = "user_command_categories.json"
HISTORY_FILENAME = ".micro_x_history"
REQUIREMENTS_FILENAME = "requirements.txt"
UNKNOWN_CATEGORY_SENTINEL = "##UNKNOWN_CATEGORY##"
UTILS_DIR_NAME = "utils" # Added for /utils command

# --- Path Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True)
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
DEFAULT_CATEGORY_PATH = os.path.join(SCRIPT_DIR, CONFIG_DIR, DEFAULT_CATEGORY_FILENAME)
USER_CATEGORY_PATH = os.path.join(SCRIPT_DIR, CONFIG_DIR, USER_CATEGORY_FILENAME)
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME)
REQUIREMENTS_FILE_PATH = os.path.join(SCRIPT_DIR, REQUIREMENTS_FILENAME)
UTILS_DIR_PATH = os.path.join(SCRIPT_DIR, UTILS_DIR_NAME) # Added for /utils command
os.makedirs(UTILS_DIR_PATH, exist_ok=True) # Ensure utils directory exists

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger(__name__)

# --- Global Configuration ---
config = {}
DEFAULT_CONFIG_FILENAME = "default_config.json" # For general app settings
USER_CONFIG_FILENAME = "user_config.json"     # For user overrides of general settings

def merge_configs(base, override):
    """Recursively merges override dict into base dict."""
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_configuration():
    """Loads general configurations from default and user JSON files."""
    global config
    default_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(SCRIPT_DIR, CONFIG_DIR, USER_CONFIG_FILENAME)

    # Fallback configuration, mirroring the structure of default_config.json
    fallback_config = {
        "ai_models": {
            "primary_translator": "llama3.2:3b",
            "direct_translator": "vitali87/shell-commands-qwen2-1.5b",
            "validator": "herawen/lisa:latest"
        },
        "timeouts": {
            "tmux_poll_seconds": 300,
            "tmux_semi_interactive_sleep_seconds": 1
        },
        "behavior": {
            "input_field_height": 3,
            "default_category_for_unclassified": "simple",
            "validator_ai_attempts": 3,
            "translation_validation_cycles": 3,
            "ai_retry_delay_seconds": 1,
            "ollama_api_call_retries": 2
        },
        "ui": {
            "max_prompt_length": 20
        },
        "paths": {
            "tmux_log_base_path": "/tmp"
        },
        "prompts": {
            "validator": {
                "system": "You are a Linux command validation assistant. Your task is to determine if a given string is likely a valid Linux command. If the string looks like a phrase rather than a linux command then the answer is no. If the string looks like a Linux command rather than a phrase then the answer is yes. Answer only with 'yes' or 'no'.",
                "user_template": "Is the following string likely a Linux command: '{command_text}'"
            },
            "primary_translator": {
                "system": "You are a helpful assistant that translates human language queries into a single, precise Linux command.\nStrictly enclose the Linux command within <bash></bash> tags.\nDo not add any other explanations, apologies, or text outside these tags.\nIf the request is ambiguous, unsafe, or cannot be translated into a single command, respond with only \"<unsafe>Cannot translate safely</unsafe>\" or a similar message within <unsafe> tags.",
                "user_template": "Translate to a single Linux command: \"{human_input}\"."
            },
            "direct_translator": {
                "system": "Translate the following user request into a single Linux command. Output only the command. Do not include any other text, explanations, or markdown formatting.",
                "user_template": "Translate to a single Linux command: \"{human_input}\"."
            }
        }
    }
    config = fallback_config.copy() # Start with fallbacks
    logger.info("Initialized with hardcoded fallback general configurations.")

    # Load default configuration file
    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f:
                default_settings = json.load(f)
            config = merge_configs(config, default_settings) # Merge defaults over fallbacks
            logger.info(f"Loaded general configurations from {default_config_path}")
        except Exception as e:
            logger.error(f"Error loading {default_config_path}: {e}. Using current config (fallbacks or previously loaded).", exc_info=True)
    else:
        logger.warning(f"{default_config_path} not found. Using fallback defaults. Creating it now.")
        try:
            os.makedirs(os.path.dirname(default_config_path), exist_ok=True) # Ensure config dir exists
            with open(default_config_path, 'w') as f:
                json.dump(fallback_config, f, indent=2) # Write the fallback_config
            logger.info(f"Created default general configuration file at {default_config_path} with fallback values.")
        except Exception as e:
            logger.error(f"Could not create default general configuration file at {default_config_path}: {e}", exc_info=True)

    # Load user configuration file (overrides defaults)
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r') as f:
                user_settings = json.load(f)
            config = merge_configs(config, user_settings) # Merge user settings over current config
            logger.info(f"Loaded and merged general configurations from {user_config_path}")
        except Exception as e:
            logger.error(f"Error loading {user_config_path}: {e}. Previous configurations remain.", exc_info=True)
    else:
        logger.info(f"{user_config_path} not found. No user general overrides applied.")

load_configuration()

# --- Command Category Mapping ---
CATEGORY_MAP = {
    "1": "simple", "2": "semi_interactive", "3": "interactive_tui",
    "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
}
# UI Enhancement: Descriptions for categories for prompts
CATEGORY_DESCRIPTIONS = {
    "simple": "Direct output in micro_X",
    "semi_interactive": "Output in micro_X after tmux run",
    "interactive_tui": "Full interactive tmux session"
}


# --- Global Variables ---
output_buffer = [] # Stores FormattedText tuples
output_field = None
input_field = None
key_help_field = None
app = None
auto_scroll = True
current_directory = os.getcwd()
categorization_flow_active = False
categorization_flow_state = {}
_CURRENTLY_LOADED_CATEGORIES = {} # Cache for merged command categories


# --- Keybindings ---
kb = KeyBindings()
@kb.add('c-c')
@kb.add('c-d')
def _handle_exit_or_cancel(event):
    """Handles Ctrl+C and Ctrl+D. Exits the app or cancels categorization."""
    global categorization_flow_active, categorization_flow_state
    if categorization_flow_active:
        append_output("\n⚠️ Categorization cancelled by user.", style_class='warning') # UI Enhancement: Styled output
        logger.info("Categorization flow cancelled by Ctrl+C/D.")
        categorization_flow_active = False
        if 'future' in categorization_flow_state and not categorization_flow_state['future'].done():
            categorization_flow_state['future'].set_result({'action': 'cancel_execution'})
        restore_normal_input_handler()
        event.app.invalidate()
    else:
        logger.info("Exit keybinding triggered.")
        event.app.exit()

@kb.add('c-n')
def _handle_newline(event):
    """Handles Ctrl+N to insert a newline in the input field (if not in categorization)."""
    if not categorization_flow_active:
        event.current_buffer.insert_text('\n')

@kb.add('enter')
def _handle_enter(event):
    """Handles Enter key. Submits the input buffer if complete."""
    buff = event.current_buffer
    buff.validate_and_handle()

@kb.add('tab')
def _handle_tab(event):
    """Handles Tab key. Tries completion or inserts spaces."""
    buff = event.current_buffer
    if buff.complete_state:
        event.app.current_buffer.complete_next()
    else:
        event.current_buffer.insert_text('    ') # Standard four spaces for tab

@kb.add('pageup')
def _handle_pageup(event):
    """Handles Page Up key to scroll the output area up."""
    if output_field and output_field.window.render_info:
        output_field.window._scroll_up()
        event.app.invalidate()

@kb.add('pagedown')
def _handle_pagedown(event):
    """Handles Page Down key to scroll the output area down."""
    if output_field and output_field.window.render_info:
        output_field.window._scroll_down()
        event.app.invalidate()

@kb.add('c-up')
def _handle_ctrl_up(event):
    """Handles Ctrl+Up to move cursor up one line in input (if not in categorization)."""
    if not categorization_flow_active:
        event.current_buffer.cursor_up(count=1)

@kb.add('c-down')
def _handle_ctrl_down(event):
    """Handles Ctrl+Down to move cursor down one line in input (if not in categorization)."""
    if not categorization_flow_active:
        event.current_buffer.cursor_down(count=1)

@kb.add('up')
def _handle_up_arrow(event):
    """Handles Up Arrow key. Navigates history or moves cursor up."""
    buff = event.current_buffer
    doc = buff.document
    if not categorization_flow_active:
        if doc.cursor_position_row == 0: # If at the first line of current input
            if buff.history_backward(): # Try to go back in history
                buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                event.app.invalidate()
        else: # Not at the first line, so just move cursor up
            buff.cursor_up()

@kb.add('down')
def _handle_down_arrow(event):
    """Handles Down Arrow key. Navigates history or moves cursor down."""
    buff = event.current_buffer
    doc = buff.document
    if not categorization_flow_active:
        if doc.cursor_position_row == doc.line_count - 1: # If at the last line of current input
            if buff.history_forward(): # Try to go forward in history
                buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                event.app.invalidate()
        else: # Not at the last line, so just move cursor down
            buff.cursor_down()

# --- Output Area Management (UI Enhancement) ---
def append_output(text: str, style_class: str = 'default'):
    """
    Appends text to the output buffer and updates the output TextArea widget.
    Allows specifying a style class for the appended text.
    """
    global output_buffer, output_field, auto_scroll
    if not text.endswith('\n'):
        text += '\n'
    
    # Store as a tuple (style_class, text_content)
    output_buffer.append((style_class, text))
    
    if output_field:
        # Construct FormattedText from the buffer
        # For simplicity, we'll join the text and rely on the overall TextArea style
        # and the main Style object to interpret class names.
        # True per-line FormattedText rendering in a standard TextArea is complex.
        
        plain_text_output = "".join([content for _, content in output_buffer])
        
        buffer = output_field.buffer
        current_cursor_pos = buffer.cursor_position
        
        # Use set_document with bypass_readonly=True, as output_field is read_only
        buffer.set_document(Document(plain_text_output, cursor_position=len(plain_text_output)), bypass_readonly=True)

        if auto_scroll or categorization_flow_active: # Force scroll during categorization
            buffer.cursor_position = len(plain_text_output)
        else: # Respect user's scroll position if not auto-scrolling
            buffer.cursor_position = min(current_cursor_pos, len(plain_text_output))
            
        if get_app().is_running: # Invalidate to trigger redraw
            get_app().invalidate()
        else: # Log if app isn't running
            logger.debug(f"Output appended while app not running: {text.strip()}")

# --- Shell Variable Expansion ---
def expand_shell_variables(command_string: str, current_pwd: str) -> str:
    """Expands environment variables like $HOME and $PWD in a command string."""
    pwd_placeholder = f"__MICRO_X_PWD_PLACEHOLDER_{uuid.uuid4().hex}__"
    temp_command_string = re.sub(r'\$PWD(?![a-zA-Z0-9_])', pwd_placeholder, command_string)
    temp_command_string = re.sub(r'\$\{PWD\}', pwd_placeholder, temp_command_string)
    expanded_string = os.path.expandvars(temp_command_string)
    expanded_string = expanded_string.replace(pwd_placeholder, current_pwd)
    if command_string != expanded_string:
        logger.debug(f"Expanded shell variables: '{command_string}' -> '{expanded_string}' (PWD: '{current_pwd}')")
    return expanded_string

# --- Normal Input Handler ---
def normal_input_accept_handler(buff):
    """Callback function triggered when Enter is pressed in the normal input mode."""
    asyncio.create_task(handle_input_async(buff.text))

def restore_normal_input_handler():
    """Resets the input field prompt and handler after categorization flow ends."""
    global input_field, current_directory, categorization_flow_active
    categorization_flow_active = False
    if input_field:
        home_dir = os.path.expanduser("~")
        max_prompt_len = config.get('ui', {}).get('max_prompt_length', 20) 
        
        if current_directory == home_dir:
            dir_for_prompt = "~"
        elif current_directory.startswith(home_dir + os.sep):
            relative_path = current_directory[len(home_dir)+1:]
            full_rel_prompt = "~/" + relative_path
            if len(full_rel_prompt) <= max_prompt_len:
                dir_for_prompt = full_rel_prompt
            else:
                chars_to_keep_at_end = max_prompt_len - 5 # For "~/.../"
                dir_for_prompt = "~/" + "..." + relative_path[-chars_to_keep_at_end:] if chars_to_keep_at_end > 0 else "~/... "
        else:
            path_basename = os.path.basename(current_directory)
            if len(path_basename) <= max_prompt_len:
                dir_for_prompt = path_basename
            else:
                chars_to_keep_at_end = max_prompt_len - 3 # For "..."
                dir_for_prompt = "..." + path_basename[-chars_to_keep_at_end:] if chars_to_keep_at_end > 0 else "..."
        
        input_field.prompt = f"({dir_for_prompt}) > "
        input_field.buffer.accept_handler = normal_input_accept_handler
        input_field.multiline = True

# --- AI Command Validation ---
async def is_valid_linux_command_according_to_ai(command_text: str) -> bool | None:
    """Asks the Validator AI model if the given text is a valid Linux command."""
    if not command_text or len(command_text) < 2 or len(command_text) > 200:
        logger.debug(f"Skipping AI validation for command_text of length {len(command_text)}: '{command_text}'")
        return None
    validator_system_prompt = config['prompts']['validator']['system']
    validator_user_prompt = config['prompts']['validator']['user_template'].format(command_text=command_text)
    validator_model = config['ai_models']['validator']
    validator_attempts = config['behavior']['validator_ai_attempts']
    retry_delay = config['behavior']['ai_retry_delay_seconds'] / 2  
    responses = []
    for i in range(validator_attempts):
        logger.info(f"To Validator AI (model: {validator_model}, attempt {i+1}/{validator_attempts}): '{command_text}'")
        try:
            response = await asyncio.to_thread(ollama.chat, model=validator_model, messages=[{'role': 'system', 'content': validator_system_prompt}, {'role': 'user', 'content': validator_user_prompt}])
            ai_answer = response['message']['content'].strip().lower()
            logger.debug(f"Validator AI response (attempt {i+1}) for '{command_text}': '{ai_answer}'")
            is_yes = re.search(r'\byes\b', ai_answer, re.IGNORECASE) is not None; is_no = re.search(r'\bno\b', ai_answer, re.IGNORECASE) is not None
            if is_yes and not is_no: responses.append(True)
            elif is_no and not is_yes: responses.append(False)
            else: responses.append(None); logger.warning(f"Validator AI unclear answer (attempt {i+1}): '{ai_answer}'")
        except Exception as e: logger.error(f"Error calling Validator AI (attempt {i+1}) for '{command_text}': {e}", exc_info=True); responses.append(None)
        if i < validator_attempts - 1 and (len(responses) <= i+1 or responses[-1] is None): await asyncio.sleep(retry_delay)
    yes_count = responses.count(True); no_count = responses.count(False)
    logger.debug(f"Validator AI responses for '{command_text}': Yes: {yes_count}, No: {no_count}, Unclear/Error: {responses.count(None)}")
    if yes_count >= (validator_attempts // 2 + 1): return True
    elif no_count >= (validator_attempts // 2 + 1): return False
    else: logger.warning(f"Validator AI result inconclusive for '{command_text}' after {validator_attempts} attempts."); return None

# --- Update Command Helper ---
def get_file_hash(filepath):
    """Calculates SHA256 hash of a file."""
    if not os.path.exists(filepath): return None
    hasher = hashlib.sha256();
    with open(filepath, 'rb') as f: hasher.update(f.read())
    return hasher.hexdigest()

async def handle_update_command():
    """Handles the /update command to fetch latest changes from git."""
    append_output("🔄 Checking for updates...", style_class='info') # UI Enhancement
    logger.info("Update command received.")
    if get_app().is_running: get_app().invalidate()
    if not shutil.which("git"): append_output("❌ Update failed: 'git' not found.", style_class='error'); logger.error("Update failed: git not found."); return # UI Enhancement
    original_req_hash = get_file_hash(REQUIREMENTS_FILE_PATH); requirements_changed = False
    try:
        branch_process = await asyncio.to_thread(subprocess.run, ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=SCRIPT_DIR, capture_output=True, text=True, check=True)
        current_branch = branch_process.stdout.strip()
        append_output(f"ℹ️ On branch: '{current_branch}'. Fetching updates...", style_class='info'); logger.info(f"Current git branch: {current_branch}") # UI Enhancement
        if get_app().is_running: get_app().invalidate()
        pull_process = await asyncio.to_thread(subprocess.run, ['git', 'pull', 'origin', current_branch], cwd=SCRIPT_DIR, capture_output=True, text=True)
        if pull_process.returncode == 0:
            append_output(f"✅ Git pull successful.\nOutput:\n{pull_process.stdout.strip()}", style_class='success'); logger.info(f"Git pull output: {pull_process.stdout.strip()}") # UI Enhancement
            if "Already up to date." in pull_process.stdout: append_output("✅ micro_X is up to date.", style_class='success') # UI Enhancement
            else:
                append_output("✅ Updates downloaded.", style_class='success') # UI Enhancement
                if original_req_hash != get_file_hash(REQUIREMENTS_FILE_PATH): requirements_changed = True; append_output("⚠️ requirements.txt changed.", style_class='warning'); logger.info("requirements.txt changed.") # UI Enhancement
                append_output("💡 Restart micro_X for changes.", style_class='info') # UI Enhancement
                if requirements_changed: append_output(f"💡 After restart, update dependencies:\n    cd \"{SCRIPT_DIR}\"\n    source .venv/bin/activate\n    pip install -r {REQUIREMENTS_FILENAME}", style_class='info') # UI Enhancement
        else: append_output(f"❌ Git pull failed.\nError:\n{pull_process.stderr.strip()}", style_class='error'); logger.error(f"Git pull failed. Stderr: {pull_process.stderr.strip()}") # UI Enhancement
    except subprocess.CalledProcessError as e: append_output(f"❌ Update failed: git error.\n{e.stderr}", style_class='error'); logger.error(f"Update git error: {e}", exc_info=True) # UI Enhancement
    except FileNotFoundError: append_output("❌ Update failed: 'git' not found.", style_class='error'); logger.error("Update failed: git not found.") # UI Enhancement
    except Exception as e: append_output(f"❌ Unexpected error during update: {e}", style_class='error'); logger.error(f"Unexpected update error: {e}", exc_info=True) # UI Enhancement
    finally:
        if get_app().is_running: get_app().invalidate()

# --- Utils Command Helper ---
async def handle_utils_command_async(full_command_str: str):
    """Handles /utils subcommands to run scripts from the utils directory."""
    logger.info(f"Handling /utils command: {full_command_str}")
    append_output(f"🛠️ Processing /utils command...", style_class='info') # UI Enhancement
    if get_app().is_running: get_app().invalidate()

    try:
        parts = shlex.split(full_command_str)
    except ValueError as e:
        append_output(f"❌ Error parsing /utils command: {e}", style_class='error') # UI Enhancement
        logger.warning(f"shlex error for /utils '{full_command_str}': {e}")
        if get_app().is_running: get_app().invalidate()
        return

    utils_help_message = "ℹ️ Usage: /utils <script_name_no_ext> [args...] | list | help"

    if len(parts) < 2: # Only "/utils"
        append_output(utils_help_message, style_class='info') # UI Enhancement
        logger.debug("Insufficient arguments for /utils command.")
        if get_app().is_running: get_app().invalidate()
        return

    subcommand_or_script_name = parts[1]
    args = parts[2:]
    
    if subcommand_or_script_name.lower() in ["list", "help"]:
        try:
            if not os.path.exists(UTILS_DIR_PATH) or not os.path.isdir(UTILS_DIR_PATH):
                append_output(f"❌ Utility directory '{UTILS_DIR_NAME}' not found at '{UTILS_DIR_PATH}'.", style_class='error') # UI Enhancement
                logger.error(f"Utility directory not found: {UTILS_DIR_PATH}")
                if get_app().is_running: get_app().invalidate()
                return

            available_scripts = [
                f[:-3] for f in os.listdir(UTILS_DIR_PATH) 
                if os.path.isfile(os.path.join(UTILS_DIR_PATH, f)) and f.endswith(".py") and f != "__init__.py"
            ]
            if available_scripts:
                append_output("Available utility scripts (run with /utils <script_name>):", style_class='info') # UI Enhancement
                for script_name in sorted(available_scripts):
                    append_output(f"  - {script_name}", style_class='info') # UI Enhancement
            else:
                append_output(f"No executable Python utility scripts found in '{UTILS_DIR_NAME}'.", style_class='info') # UI Enhancement
            logger.info(f"Listed utils scripts: {available_scripts}")
        except Exception as e:
            append_output(f"❌ Error listing utility scripts: {e}", style_class='error') # UI Enhancement
            logger.error(f"Error listing utility scripts: {e}", exc_info=True)
        finally:
            if get_app().is_running: get_app().invalidate()
        return

    script_filename = f"{subcommand_or_script_name}.py"
    script_path = os.path.join(UTILS_DIR_PATH, script_filename) 

    if not os.path.isfile(script_path):
        append_output(f"❌ Utility script not found: {script_filename} in '{UTILS_DIR_NAME}' directory.", style_class='error') # UI Enhancement
        logger.warning(f"Utility script not found: {script_path}")
        append_output(utils_help_message, style_class='info') 
        if get_app().is_running: get_app().invalidate()
        return

    command_to_execute_list = [sys.executable, script_path] + args
    command_str_for_display = f"{sys.executable} {script_path} {' '.join(args)}"

    append_output(f"🚀 Executing utility: {command_str_for_display}\n    (Working directory: {SCRIPT_DIR})", style_class='info') # UI Enhancement
    logger.info(f"Executing utility script: {command_to_execute_list} with cwd={SCRIPT_DIR}")
    if get_app().is_running: get_app().invalidate()

    try:
        process = await asyncio.to_thread(
            subprocess.run,
            command_to_execute_list,
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR, 
            check=False,    
            errors='replace'
        )
        
        output_prefix = f"Output from '{script_filename}':\n"
        has_output = False
        if process.stdout:
            append_output(f"{output_prefix}{process.stdout.strip()}") # Default style for script output
            has_output = True
        if process.stderr:
            append_output(f"Stderr from '{script_filename}':\n{process.stderr.strip()}", style_class='warning') # UI Enhancement: stderr as warning
            has_output = True
        
        if not has_output and process.returncode == 0:
            append_output(f"{output_prefix}(No output)", style_class='info') # UI Enhancement

        if process.returncode != 0:
            append_output(f"⚠️ Utility '{script_filename}' exited with code {process.returncode}.", style_class='warning') # UI Enhancement
            logger.warning(f"Utility script '{script_path}' exited with code {process.returncode}. Args: {args}")
        else:
            if not process.stderr: 
                append_output(f"✅ Utility '{script_filename}' completed.", style_class='success') # UI Enhancement
            logger.info(f"Utility script '{script_path}' completed with code {process.returncode}. Args: {args}")

    except FileNotFoundError:  
        append_output(f"❌ Error: Python interpreter ('{sys.executable}') or script ('{script_filename}') not found.", style_class='error') # UI Enhancement
        logger.error(f"FileNotFoundError executing utility: {command_to_execute_list}", exc_info=True)
    except Exception as e:
        append_output(f"❌ Unexpected error executing utility '{script_filename}': {e}", style_class='error') # UI Enhancement
        logger.error(f"Error executing utility script '{script_path}': {e}", exc_info=True)
    finally:
        if get_app().is_running: get_app().invalidate()


# --- General Help Function (UI Enhancement) ---
def display_general_help():
    """Displays the general help message for micro_X with improved formatting."""
    help_text_styled = [
        ('class:help-title', "micro_X AI-Enhanced Shell - Help\n\n"),
        ('class:help-text', "Welcome to micro_X! An intelligent shell that blends traditional command execution with AI capabilities.\n"),
        ('class:help-header', "\nAvailable Commands:\n"),
        ('class:help-command', "  /ai <query>             "), ('class:help-description', "- Translate natural language <query> into a Linux command.\n"),
        ('class:help-example', "                            Example: /ai list all text files in current folder\n"),
        ('class:help-command', "  /command <subcommand>   "), ('class:help-description', "- Manage command categorizations (simple, semi_interactive, interactive_tui).\n"),
        ('class:help-example', "                            Type '/command help' for detailed options.\n"),
        ('class:help-command', "  /utils <script> [args]  "), ('class:help-description', "- Run a utility script from the 'utils' directory.\n"),
        ('class:help-example', "                            Type '/utils list' or '/utils help' for available scripts.\n"),
        ('class:help-command', "  /update                 "), ('class:help-description', "- Check for and download updates for micro_X from its repository.\n"),
        ('class:help-command', "  /help                   "), ('class:help-description', "- Display this help message.\n"),
        ('class:help-command', "  exit | quit             "), ('class:help-description', "- Exit the micro_X shell.\n"),
        ('class:help-header', "\nDirect Commands:\n"),
        ('class:help-text', "  You can type standard Linux commands directly (e.g., 'ls -l', 'cd my_folder').\n"),
        ('class:help-text', "  Unknown commands will trigger an interactive categorization flow.\n"),
        ('class:help-header', "\nKeybindings:\n"),
        ('class:help-text', "  Common keybindings are displayed at the bottom of the screen.\n"),
        ('class:help-text', "  Ctrl+C / Ctrl+D: Exit micro_X or cancel current categorization.\n"),
        ('class:help-text', "  Ctrl+N: Insert a newline in the input field.\n"),
        ('class:help-header', "\nConfiguration:\n"),
        ('class:help-text', "  AI models and some behaviors can be customized in 'config/user_config.json'.\n"),
        ('class:help-text', "  Command categorizations are saved in 'config/user_command_categories.json'.\n"),
        ('class:help-text', "\nHappy shelling!\n")
    ]
    
    help_output_string = ""
    for style_class, text_content in help_text_styled:
        help_output_string += text_content
    
    append_output(help_output_string, style_class='help-base') 
    logger.info("Displayed general help.")

# --- Command Handling Logic ---
async def handle_input_async(user_input: str):
    """Main asynchronous function to process user input."""
    global current_directory, categorization_flow_active
    if categorization_flow_active: logger.warning("Input ignored: categorization active."); return
    user_input_stripped = user_input.strip(); logger.info(f"Received input: '{user_input_stripped}'")
    if not user_input_stripped: return

    if user_input_stripped.lower() in {"/help", "help"}:
        display_general_help()
        return

    if user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
        append_output("Exiting micro_X Shell 🚪", style_class='info'); logger.info("Exit command received.") 
        if get_app().is_running: get_app().exit(); return
    
    if user_input_stripped.lower() == "/update":  
        await handle_update_command()
        return
    
    if user_input_stripped.startswith("/utils"): 
        await handle_utils_command_async(user_input_stripped)
        return

    if user_input_stripped.startswith("/ai "):
        human_query = user_input_stripped[len("/ai "):].strip()
        if not human_query: append_output("⚠️ AI query empty.", style_class='warning'); return 
        append_output(f"🤖 AI Query: {human_query}", style_class='ai-query') 
        append_output(f"🧠 Thinking...", style_class='ai-thinking') 
        if get_app().is_running: get_app().invalidate()
        linux_command, ai_raw_candidate = await get_validated_ai_command(human_query)
        if linux_command:
            append_output(f"🤖 AI Suggests (validated): {linux_command}", style_class='ai-response') 
            await process_command(linux_command, f"/ai {human_query} -> {linux_command}", ai_raw_candidate, None)
        else: append_output("🤔 AI could not produce a validated command.", style_class='warning') 
        return
    
    if user_input_stripped.startswith("/command"):  
        handle_command_subsystem_input(user_input_stripped)
        return
    
    category = classify_command(user_input_stripped) 
    if category != UNKNOWN_CATEGORY_SENTINEL:
        logger.debug(f"Direct input '{user_input_stripped}' is known: '{category}'.")
        await process_command(user_input_stripped, user_input_stripped, None, None)
    else:
        logger.debug(f"Direct input '{user_input_stripped}' unknown. Validating with AI.")
        append_output(f"🔎 Validating '{user_input_stripped}' with AI...", style_class='info'); 
        if get_app().is_running: get_app().invalidate()
        is_cmd_ai_says = await is_valid_linux_command_according_to_ai(user_input_stripped)
        has_space = ' ' in user_input_stripped; is_path_indicator = user_input_stripped.startswith(('/', './', '../'))
        has_double_hyphen = '--' in user_input_stripped; has_single_hyphen_option = bool(re.search(r'(?:^|\s)-\w', user_input_stripped))
        is_problematic_leading_dollar = False
        if user_input_stripped.startswith('$'):
            if len(user_input_stripped) == 1: is_problematic_leading_dollar = True
            elif len(user_input_stripped) > 1 and user_input_stripped[1].isalnum() and user_input_stripped[1] != '{': is_problematic_leading_dollar = True
        is_command_syntax_present = is_path_indicator or has_double_hyphen or has_single_hyphen_option or ('$' in user_input_stripped and not is_problematic_leading_dollar)
        user_input_looks_like_phrase = False
        if is_problematic_leading_dollar: user_input_looks_like_phrase = True
        elif not has_space: user_input_looks_like_phrase = False
        elif is_command_syntax_present: user_input_looks_like_phrase = False
        else: user_input_looks_like_phrase = True
        logger.debug(f"Input: '{user_input_stripped}', Validator AI: {is_cmd_ai_says}, Heuristic phrase: {user_input_looks_like_phrase}")
        if is_cmd_ai_says is True and not user_input_looks_like_phrase:
            append_output(f"✅ AI believes '{user_input_stripped}' is direct command. Categorizing.", style_class='success') 
            logger.info(f"Validator AI confirmed '{user_input_stripped}' as command (not phrase).")
            await process_command(user_input_stripped, user_input_stripped, None, None)
        else:
            log_msg = ""; ui_msg = ""; ui_style = 'ai-thinking' 
            if is_cmd_ai_says is False: log_msg = f"Validator AI suggests '{user_input_stripped}' not command."; ui_msg = f"💬 AI suggests '{user_input_stripped}' not direct command. Trying as NL query..."
            elif is_cmd_ai_says is True and user_input_looks_like_phrase: log_msg = f"Validator AI confirmed '{user_input_stripped}' as command, but heuristic overrides."; ui_msg = f"💬 AI validated '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."
            else: log_msg = f"Validator AI for '{user_input_stripped}' inconclusive."; ui_msg = f"⚠️ AI validation for '{user_input_stripped}' inconclusive. Trying as NL query..."; ui_style = 'warning' 
            logger.info(f"{log_msg} Treating as natural language."); append_output(ui_msg, style_class=ui_style)
            if get_app().is_running: get_app().invalidate()
            linux_command, ai_raw_candidate = await get_validated_ai_command(user_input_stripped)
            if linux_command:
                append_output(f"🤖 AI Translated & Validated to: {linux_command}", style_class='ai-response') 
                original_direct_for_prompt = user_input_stripped if linux_command != user_input_stripped else None
                await process_command(linux_command, f"'{user_input_stripped}' -> {linux_command}", ai_raw_candidate, original_direct_for_prompt)
            else:
                append_output(f"🤔 AI could not produce validated command for '{user_input_stripped}'. Trying original as direct command.", style_class='warning') 
                logger.info(f"Validated AI translation failed for '{user_input_stripped}'. Categorizing original input.")
                await process_command(user_input_stripped, user_input_stripped, ai_raw_candidate, None)

# --- process_command and categorization flow (UI Enhancements for Categorization) ---
async def process_command(command_str_original: str, original_user_input_for_display: str,
                          ai_raw_candidate: str | None = None,
                          original_direct_input_if_different: str | None = None):
    """Processes a command: categorizes (if unknown), expands, sanitizes, and executes."""
    global current_directory
    if command_str_original.strip().startswith("cd "): handle_cd_command(command_str_original); return
    command_for_classification = command_str_original; category = classify_command(command_for_classification)
    command_to_be_added_if_new = command_for_classification 
    
    if category == UNKNOWN_CATEGORY_SENTINEL:
        logger.info(f"Command '{command_for_classification}' uncategorized. Starting interactive flow.")
        categorization_result = await prompt_for_categorization(command_for_classification, ai_raw_candidate, original_direct_input_if_different)
        
        if categorization_result.get('action') == 'cancel_execution':
            append_output(f"Execution of '{command_for_classification}' cancelled.", style_class='info'); logger.info(f"Execution of '{command_for_classification}' cancelled."); return 
        elif categorization_result.get('action') == 'categorize_and_execute':
            command_to_be_added_if_new = categorization_result['command'] 
            chosen_cat_for_json = categorization_result['category']
            add_command_to_category(command_to_be_added_if_new, chosen_cat_for_json) 
            category = chosen_cat_for_json 
            logger.info(f"Command '{command_to_be_added_if_new}' categorized as '{category}'.")
            if command_to_be_added_if_new != command_str_original: 
                logger.info(f"Using '{command_to_be_added_if_new}' for execution, overriding '{command_str_original}'.")
                command_str_original = command_to_be_added_if_new 
        else: 
            category = config['behavior']['default_category_for_unclassified']
            append_output(f"Executing '{command_for_classification}' as default '{category}'.", style_class='info'); logger.info(f"Command '{command_for_classification}' executed with default category '{category}'.") 
    
    command_to_execute_expanded = expand_shell_variables(command_str_original, current_directory)
    if command_str_original != command_to_execute_expanded:
        logger.info(f"Expanded command: '{command_to_execute_expanded}' (original: '{command_str_original}')")
        if command_to_execute_expanded != command_for_classification and command_to_execute_expanded != command_to_be_added_if_new:
                 append_output(f"Expanded for execution: {command_to_execute_expanded}", style_class='info') 
    
    command_to_execute_sanitized = sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
    if not command_to_execute_sanitized:
        append_output(f"Command '{command_to_execute_expanded}' blocked by sanitization.", style_class='security-warning'); logger.warning(f"Command '{command_to_execute_expanded}' blocked."); return 
    
    logger.info(f"Final command: '{command_to_execute_sanitized}', Category: '{category}'"); append_output(f"▶️ Executing ({category} - {CATEGORY_DESCRIPTIONS.get(category, 'Unknown')}): {command_to_execute_sanitized}", style_class='executing') 
    if category == "simple": execute_shell_command(command_to_execute_sanitized, original_user_input_for_display)
    else: execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category)

async def prompt_for_categorization(command_initially_proposed: str, ai_raw_candidate_for_suggestions: str | None, original_direct_input_if_different: str | None) -> dict:
    """Manages the interactive flow for categorizing an unknown command."""
    global categorization_flow_active, categorization_flow_state, input_field
    categorization_flow_active = True; categorization_flow_state = {'command_initially_proposed': command_initially_proposed, 'ai_raw_candidate': ai_raw_candidate_for_suggestions,'original_direct_input': original_direct_input_if_different, 'command_to_add_final': command_initially_proposed, 'step': 0.5}
    flow_completion_future = asyncio.Future(); categorization_flow_state['future'] = flow_completion_future
    if input_field: input_field.multiline = False 
    _ask_step_0_5_confirm_command_base()
    try: return await flow_completion_future
    finally: restore_normal_input_handler(); logger.debug("Categorization flow ended.")

def _ask_step_0_5_confirm_command_base():
    """Step 0.5: If AI/system changed input, confirm which version to use."""
    global categorization_flow_state; proposed = categorization_flow_state['command_initially_proposed']; original = categorization_flow_state['original_direct_input']
    if original and original.strip() != proposed.strip():
        append_output(f"\nSystem processed to: '{proposed}'\nOriginal input was: '{original}'", style_class='categorize-info') 
        append_output(f"Which version to categorize?\n  1: Processed ('{proposed}')\n  2: Original ('{original}')\n  3: Modify/Enter new command\n  4: Cancel categorization", style_class='categorize-prompt') 
        if input_field: input_field.prompt = "[Categorize] Choice (1-4): "; input_field.buffer.accept_handler = _handle_step_0_5_response; get_app().invalidate()
    else: categorization_flow_state['command_to_add_final'] = proposed; categorization_flow_state['step'] = 1; _ask_step_1_main_action()

def _handle_step_0_5_response(buff):
    """Handles response for step 0.5."""
    global categorization_flow_state; response = buff.text.strip(); proposed = categorization_flow_state['command_initially_proposed']; original = categorization_flow_state['original_direct_input']
    if response == '1': categorization_flow_state['command_to_add_final'] = proposed; append_output(f"Using processed: '{proposed}'", style_class='categorize-info'); categorization_flow_state['step'] = 1; _ask_step_1_main_action() 
    elif response == '2' and original: categorization_flow_state['command_to_add_final'] = original; append_output(f"Using original: '{original}'", style_class='categorize-info'); categorization_flow_state['step'] = 1; _ask_step_1_main_action() 
    elif response == '3': categorization_flow_state['step'] = 3.5; _ask_step_3_5_enter_custom_command_for_categorization()
    elif response == '4': categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else: append_output("Invalid choice (1-4). Please try again.", style_class='error'); _ask_step_0_5_confirm_command_base(); return 
    if response in ['1', '2', '3', '4'] and input_field: input_field.buffer.reset()

def _ask_step_1_main_action():
    """Step 1: Ask user how to categorize the confirmed command."""
    global categorization_flow_state, input_field; cmd_display = categorization_flow_state['command_to_add_final']; default_cat_name = config['behavior']['default_category_for_unclassified']
    append_output(f"\nCommand to categorize: '{cmd_display}'", style_class='categorize-info') 
    append_output(f"How to categorize this command?\n"
                  f"  1: simple           ({CATEGORY_DESCRIPTIONS['simple']})\n" 
                  f"  2: semi_interactive  ({CATEGORY_DESCRIPTIONS['semi_interactive']})\n" 
                  f"  3: interactive_tui   ({CATEGORY_DESCRIPTIONS['interactive_tui']})\n" 
                  f"  M: Modify command before categorizing\n"
                  f"  D: Execute as default '{default_cat_name}' (once, no save)\n"
                  f"  C: Cancel categorization & execution", style_class='categorize-prompt') 
    if input_field: input_field.prompt = "[Categorize] Action (1-3/M/D/C): "; input_field.buffer.accept_handler = _handle_step_1_main_action_response; get_app().invalidate()

def _handle_step_1_main_action_response(buff):
    """Handles response for step 1."""
    global categorization_flow_state; response = buff.text.strip().lower(); cmd_to_add = categorization_flow_state['command_to_add_final']
    if response in ['1', '2', '3']: chosen_category = CATEGORY_MAP.get(response); categorization_flow_state.get('future').set_result({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category})
    elif response == 'm': categorization_flow_state['step'] = 4; _ask_step_4_enter_modified_command(base_command=cmd_to_add)
    elif response == 'd': categorization_flow_state.get('future').set_result({'action': 'execute_as_default'})
    elif response == 'c': categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else: append_output("Invalid choice. Please enter 1-3, M, D, or C.", style_class='error'); _ask_step_1_main_action(); return 
    if response in ['1', '2', '3', 'm', 'd', 'c'] and input_field: input_field.buffer.reset()

def _ask_step_3_5_enter_custom_command_for_categorization():
    """Step 3.5: User enters a completely new command string."""
    global categorization_flow_state, input_field; append_output("\nEnter the new command string you want to categorize:", style_class='categorize-prompt') 
    if input_field: input_field.prompt = "[Categorize] New command: "; input_field.buffer.text = ""; input_field.buffer.accept_handler = _handle_step_3_5_response; get_app().invalidate()

def _handle_step_3_5_response(buff):
    """Handles custom command from step 3.5."""
    global categorization_flow_state; custom_command = buff.text.strip()
    if not custom_command: append_output("⚠️ Command cannot be empty. Please enter a command or Ctrl+C to cancel.", style_class='warning'); _ask_step_3_5_enter_custom_command_for_categorization(); return 
    categorization_flow_state['command_to_add_final'] = custom_command; append_output(f"New command for categorization: '{custom_command}'", style_class='categorize-info'); categorization_flow_state['step'] = 1; _ask_step_1_main_action() 
    if input_field: input_field.buffer.reset()

def _ask_step_4_enter_modified_command(base_command: str):
    """Step 4: User modifies the existing command string."""
    global categorization_flow_state, input_field; append_output(f"\nCurrent command: '{base_command}'\nEnter your modified command below:", style_class='categorize-prompt') 
    if input_field: input_field.prompt = f"[Categorize] Modified Cmd: "; input_field.buffer.text = base_command; input_field.buffer.cursor_position = len(base_command); input_field.buffer.accept_handler = _handle_step_4_modified_command_response; get_app().invalidate()

def _handle_step_4_modified_command_response(buff):
    """Handles modified command from step 4."""
    global categorization_flow_state; modified_command = buff.text.strip()
    if not modified_command: append_output("⚠️ Modified command empty. Using previous command for categorization.", style_class='warning') 
    else: categorization_flow_state['command_to_add_final'] = modified_command
    categorization_flow_state['step'] = 4.5; _ask_step_4_5_category_for_modified()

def _ask_step_4_5_category_for_modified():
    """Step 4.5: Ask category for the (potentially) modified command."""
    global categorization_flow_state, input_field; cmd_to_categorize = categorization_flow_state['command_to_add_final']
    append_output(f"\nCategory for command: '{cmd_to_categorize}'", style_class='categorize-info') 
    append_output(f"  1: simple           ({CATEGORY_DESCRIPTIONS['simple']})\n" 
                  f"  2: semi_interactive  ({CATEGORY_DESCRIPTIONS['semi_interactive']})\n" 
                  f"  3: interactive_tui   ({CATEGORY_DESCRIPTIONS['interactive_tui']})", style_class='categorize-prompt') 
    if input_field: input_field.prompt = "[Categorize] Category (1-3): "; input_field.buffer.reset(); input_field.buffer.accept_handler = _handle_step_4_5_response; get_app().invalidate()

def _handle_step_4_5_response(buff):
    """Handles category choice for modified command (step 4.5)."""
    global categorization_flow_state; response = buff.text.strip(); chosen_category = CATEGORY_MAP.get(response)
    if chosen_category: categorization_flow_state.get('future').set_result({'action': 'categorize_and_execute', 'command': categorization_flow_state['command_to_add_final'], 'category': chosen_category})
    else: append_output("Invalid category. Please enter 1, 2, or 3.", style_class='error'); _ask_step_4_5_category_for_modified() 
    if input_field: input_field.buffer.reset() 

# --- Built-in Command Handlers ---
def handle_cd_command(full_cd_command: str):
    """Handles the 'cd' command to change the current working directory."""
    global current_directory, input_field
    try:
        parts = full_cd_command.split(" ", 1); target_dir_str = parts[1].strip() if len(parts) > 1 else "~"
        expanded_dir_arg = os.path.expanduser(os.path.expandvars(target_dir_str))
        new_dir_abs = os.path.abspath(os.path.join(current_directory, expanded_dir_arg)) if not os.path.isabs(expanded_dir_arg) else expanded_dir_arg
        if os.path.isdir(new_dir_abs):
            current_directory = new_dir_abs
            if input_field: 
                home_dir = os.path.expanduser("~")
                max_prompt_len = config.get('ui', {}).get('max_prompt_length', 20) 
                if current_directory == home_dir: dir_for_prompt = "~"
                elif current_directory.startswith(home_dir + os.sep):
                    relative_path = current_directory[len(home_dir)+1:]; full_rel_prompt = "~/" + relative_path
                    dir_for_prompt = full_rel_prompt if len(full_rel_prompt) <= max_prompt_len else "~/" + "..." + relative_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
                else:
                    path_basename = os.path.basename(current_directory)
                    dir_for_prompt = path_basename if len(path_basename) <= max_prompt_len else "..." + path_basename[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."
                input_field.prompt = f"({dir_for_prompt}) > "
                if get_app().is_running: get_app().invalidate()
            append_output(f"📂 Changed directory to: {current_directory}", style_class='info'); logger.info(f"Directory changed to: {current_directory}") 
        else: append_output(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.", style_class='error'); logger.warning(f"Failed cd to '{new_dir_abs}'.") 
    except Exception as e: append_output(f"❌ Error processing 'cd' command: {e}", style_class='error'); logger.exception(f"Error in handle_cd_command for '{full_cd_command}'") 

# --- Command Execution ---
def sanitize_and_validate(command: str, original_input_for_log: str) -> str | None:
    """Performs basic checks for potentially dangerous command patterns."""
    dangerous_patterns = [r'\brm\s+(-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\S*', r'\bmkfs\b', r'\bdd\b\s+if=/dev/random', r'\bdd\b\s+if=/dev/zero', r'\b(shutdown|reboot|halt|poweroff)\b', r'>\s*/dev/sd[a-z]+', r':\(\)\{:\|:&};:', r'\b(wget|curl)\s+.*\s*\|\s*(sh|bash|python|perl)\b']
    for pattern in dangerous_patterns:
        if re.search(pattern, command): logger.warning(f"DANGEROUS command blocked ('{pattern}'): '{command}' (from '{original_input_for_log}')"); append_output(f"🛡️ Command blocked for security: {command}", style_class='security-critical'); return None 
    return command

def execute_command_in_tmux(command_to_execute: str, original_user_input_display: str, category: str):
    """Executes a command within a new tmux window."""
    try:
        unique_id = str(uuid.uuid4())[:8]; window_name = f"micro_x_{unique_id}"
        if shutil.which("tmux") is None: append_output("❌ Error: tmux not found. Cannot execute semi_interactive or interactive_tui commands.", style_class='error'); logger.error("tmux not found."); return 
        
        tmux_poll_timeout = config['timeouts']['tmux_poll_seconds']
        tmux_sleep_after = config['timeouts']['tmux_semi_interactive_sleep_seconds']
        tmux_log_base = config.get('paths', {}).get('tmux_log_base_path', '/tmp') 

        if category == "semi_interactive":
            os.makedirs(tmux_log_base, exist_ok=True) 
            log_path = os.path.join(tmux_log_base, f"micro_x_output_{unique_id}.log") 
            
            replacement_for_single_quote = "'\"'\"'"; escaped_command_str = command_to_execute.replace("'", replacement_for_single_quote)
            wrapped_command = f"bash -c '{escaped_command_str}' |& tee {log_path}; sleep {tmux_sleep_after}"
            # Corrected: tmux_cmd_list was defined but then process was called with it again.
            # subprocess.run is blocking, so Popen might be better if we want to poll,
            # but the original logic used subprocess.run for the initial launch.
            # For semi-interactive, we launch detached and then poll.
            tmux_cmd_list_launch = ["tmux", "new-window", "-d", "-n", window_name, wrapped_command]
            logger.info(f"Executing semi_interactive tmux: {tmux_cmd_list_launch} (log: {log_path})")
            subprocess.run(tmux_cmd_list_launch, check=True, cwd=current_directory)

            append_output(f"⚡ Launched semi-interactive command in tmux (window: {window_name}). Waiting for output (max {tmux_poll_timeout}s)...", style_class='info') 
            start_time = time.time(); output_captured = False; window_closed_or_cmd_done = False 

            while time.time() - start_time < tmux_poll_timeout:
                time.sleep(1) 
                try:
                    result = subprocess.run(["tmux", "list-windows", "-F", "#{window_name}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore", check=True)
                    if window_name not in result.stdout:
                        logger.info(f"Tmux window '{window_name}' closed or command finished.")
                        window_closed_or_cmd_done = True
                        break 
                except (subprocess.CalledProcessError, FileNotFoundError) as tmux_err:
                    logger.warning(f"Error checking tmux windows (assuming closed or command done): {tmux_err}")
                    window_closed_or_cmd_done = True
                    break
                
                if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                     pass # Log content is checked after loop

            if not window_closed_or_cmd_done: append_output(f"⚠️ Tmux window '{window_name}' poll timed out. Output might be incomplete or command still running.", style_class='warning'); logger.warning(f"Tmux poll for '{window_name}' timed out.") 
            
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f: output_content = f.read().strip()
                    if output_content: append_output(f"Output from '{original_user_input_display}':\n{output_content}"); output_captured = True
                    elif window_closed_or_cmd_done: append_output(f"Output from '{original_user_input_display}': (No output captured)", style_class='info'); output_captured = True 
                except Exception as e: logger.error(f"Error reading tmux log {log_path}: {e}"); append_output(f"❌ Error reading tmux log: {e}", style_class='error') 
                finally:
                    try: os.remove(log_path)
                    except OSError as e_del: logger.error(f"Error deleting tmux log {log_path}: {e_del}")
            elif window_closed_or_cmd_done: append_output(f"Output from '{original_user_input_display}': (Tmux window closed, no log found)", style_class='info') 
            
            if not output_captured and not window_closed_or_cmd_done: append_output(f"Output from '{original_user_input_display}': (Tmux window may still be running or timed out without output)", style_class='warning') 

        else: # interactive_tui
            tmux_cmd_list = ["tmux", "new-window", "-n", window_name, command_to_execute]
            logger.info(f"Executing interactive_tui tmux: {tmux_cmd_list}"); append_output(f"⚡ Launching interactive command in tmux (window: {window_name}). micro_X will wait.", style_class='info') 
            try:
                subprocess.run(tmux_cmd_list, check=True, cwd=current_directory) 
                append_output(f"✅ Interactive tmux session for '{original_user_input_display}' ended.", style_class='success') 
            except subprocess.CalledProcessError as e: append_output(f"❌ Error or non-zero exit in tmux session '{window_name}': {e}", style_class='error'); logger.error(f"Error reported by tmux run for cmd '{command_to_execute}': {e}") 
            except FileNotFoundError: append_output("❌ Error: tmux not found. Cannot execute interactive_tui command.", style_class='error'); logger.error("tmux not found for interactive_tui.") 
            except Exception as e_run: append_output(f"❌ Unexpected error running interactive tmux: {e_run}", style_class='error'); logger.exception(f"Unexpected error running interactive tmux: {e_run}") 
    except subprocess.CalledProcessError as e: append_output(f"❌ Error setting up tmux: {e.stderr or e}", style_class='error'); logger.exception(f"CalledProcessError during tmux setup: {e}") 
    except Exception as e: append_output(f"❌ Unexpected error interacting with tmux: {e}", style_class='error'); logger.exception(f"Unexpected error during tmux interaction: {e}") 

def execute_shell_command(command_to_execute: str, original_user_input_display: str):
    """Executes a 'simple' command directly using subprocess."""
    global current_directory
    try:
        if not command_to_execute.strip(): append_output("⚠️ Empty command cannot be executed.", style_class='warning'); logger.warning(f"Attempted to execute empty command: '{command_to_execute}'"); return 
        process = subprocess.Popen(['bash', '-c', command_to_execute], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=current_directory, text=True, errors='replace')
        stdout, stderr = process.communicate(); output_prefix = f"Output from '{original_user_input_display}':\n"
        if stdout: append_output(f"{output_prefix}{stdout.strip()}") 
        if stderr: append_output(f"Stderr from '{original_user_input_display}':\n{stderr.strip()}", style_class='warning') 
        if not stdout and not stderr and process.returncode == 0: append_output(f"{output_prefix}(No output)", style_class='info') 
        if process.returncode != 0:
            logger.warning(f"Command '{command_to_execute}' exited with code {process.returncode}")
            if not stderr: append_output(f"⚠️ Command '{original_user_input_display}' exited with code {process.returncode}.", style_class='warning') 
    except FileNotFoundError: append_output(f"❌ Shell (bash) not found. Cannot execute command.", style_class='error'); logger.error(f"Shell (bash) not found for: {command_to_execute}") 
    except Exception as e: append_output(f"❌ Error executing '{command_to_execute}': {e}", style_class='error'); logger.exception(f"Error executing shell command: {e}") 

# --- AI Integration ---
_COMMAND_PATTERN_STRING = (r"<bash>\s*'(.*?)'\s*</bash>|<bash>\s*(.*?)\s*</bash>|<bash>\s*`(.*?)`\s*</bash>|```bash\s*\n([\s\S]*?)\n```|<code>\s*'(.*?)'\s*</code>|<code>\s*(.*?)\s*</code>|<pre>\s*'(.*?)'\s*</pre>|<pre>\s*(.*?)\s*</pre>|<command>\s*'(.*?)'\s*</command>|<command>\s*(.*?)\s*</command>|<cmd>\s*'(.*?)'\s*</cmd>|<cmd>\s*(.*?)\s*</cmd>|```\s*([\s\S]*?)\s*```|<unsafe>\s*([\s\S]*?)\s*</unsafe>")
try:
    COMMAND_PATTERN = re.compile(_COMMAND_PATTERN_STRING, re.IGNORECASE | re.DOTALL); EXPECTED_GROUPS = _COMMAND_PATTERN_STRING.count('|') + 1
    logger.debug(f"COMMAND_PATTERN compiled with {COMMAND_PATTERN.groups} groups (expected {EXPECTED_GROUPS}).")
    if COMMAND_PATTERN.groups != EXPECTED_GROUPS: logger.error(f"CRITICAL: COMMAND_PATTERN groups mismatch: {COMMAND_PATTERN.groups} vs {EXPECTED_GROUPS}.")
except re.error as e: logger.critical(f"Failed to compile COMMAND_PATTERN regex: {e}", exc_info=True); COMMAND_PATTERN = None
_COMMAND_EXTRACT_GROUPS = list(range(1, EXPECTED_GROUPS)); _UNSAFE_TAG_CONTENT_GROUP = EXPECTED_GROUPS
_INNER_TAG_EXTRACT_PATTERN = re.compile(r"^\s*<([a-zA-Z0-9_:]+)(?:\s+[^>]*)?>([\s\S]*?)<\/\1>\s*$", re.DOTALL)

def _clean_extracted_command(extracted_candidate: str) -> str:
    """Applies common cleaning steps to a potential command string."""
    processed_candidate = extracted_candidate.strip(); original_for_log = processed_candidate
    inner_match = _INNER_TAG_EXTRACT_PATTERN.match(processed_candidate)
    if inner_match:
        tag_name = inner_match.group(1).lower()
        if tag_name in ["bash", "code", "cmd", "command", "pre"]:
            extracted_content = inner_match.group(2).strip(); logger.debug(f"Stripped inner tag <{tag_name}>: '{original_for_log}' -> '{extracted_content}'"); processed_candidate = extracted_content
        else: logger.debug(f"Inner tag <{tag_name}> found but not one of expected types to strip. Original: '{original_for_log}'")
    if len(processed_candidate) >= 2:
        if processed_candidate.startswith("'") and processed_candidate.endswith("'"): processed_candidate = processed_candidate[1:-1].strip(); logger.debug(f"Stripped outer single quotes: '{original_for_log}' -> '{processed_candidate}'")
        elif processed_candidate.startswith("`") and processed_candidate.endswith("`"): processed_candidate = processed_candidate[1:-1].strip(); logger.debug(f"Stripped outer backticks: '{original_for_log}' -> '{processed_candidate}'")
    if (processed_candidate.lower().startswith("bash ") or processed_candidate.lower().startswith("sh ")) and len(processed_candidate) > 6:
        prefix_len = 5 if processed_candidate.lower().startswith("bash ") else 3; potential_inner_cmd = processed_candidate[prefix_len:].strip()
        if potential_inner_cmd.startswith("<") and potential_inner_cmd.endswith(">") and len(potential_inner_cmd) >=2:
            inner_cmd_content = potential_inner_cmd[1:-1].strip()
            if not any(c in inner_cmd_content for c in '<>|&;'): logger.debug(f"Stripped '{processed_candidate[:prefix_len]}<cmd>' pattern: '{original_for_log}' -> '{inner_cmd_content}'"); processed_candidate = inner_cmd_content
            else: logger.debug(f"Retained '{processed_candidate[:prefix_len]}<cmd>' structure due to special chars: '{original_for_log}'")
    if len(processed_candidate) >= 2 and processed_candidate.startswith("<") and processed_candidate.endswith(">"):
        inner_content = processed_candidate[1:-1].strip()
        if not any(c in inner_content for c in '<>|&;'): logger.debug(f"Stripped general angle brackets: '{original_for_log}' -> '{inner_content}'"); processed_candidate = inner_content
        else: logger.debug(f"Retained general angle brackets due to special chars: '{original_for_log}'")
    cleaned_linux_command = processed_candidate.strip()
    if cleaned_linux_command.startswith('/') and '/' not in cleaned_linux_command[1:]: cleaned_linux_command = cleaned_linux_command[1:]; logger.debug(f"Stripped leading slash: '{original_for_log}' -> '{cleaned_linux_command}'")
    logger.debug(f"After cleaning (reverted logic): '{original_for_log}' -> '{cleaned_linux_command}'")
    if cleaned_linux_command and not cleaned_linux_command.lower().startswith(("sorry", "i cannot", "unable to", "cannot translate")): return cleaned_linux_command
    else:
        if cleaned_linux_command: logger.debug(f"Command discarded after cleaning (AI refusal): '{original_for_log}' -> '{cleaned_linux_command}'")
        return ""

async def _interpret_and_clean_tagged_ai_output(human_input: str) -> tuple[str | None, str | None]:
    """Calls primary translation AI, parses, and cleans."""
    if COMMAND_PATTERN is None: logger.error("COMMAND_PATTERN regex not compiled."); return None, None
    raw_candidate_from_regex = None; ollama_model = config['ai_models']['primary_translator']
    system_prompt = config['prompts']['primary_translator']['system']; user_prompt_template = config['prompts']['primary_translator']['user_template']
    retry_delay = config['behavior']['ai_retry_delay_seconds']
    ollama_call_retries = config.get('behavior', {}).get('ollama_api_call_retries', 2) 
    last_exception_in_ollama_call = None
    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None
        try:
            logger.info(f"To Primary AI (model: {ollama_model}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'"); user_prompt = user_prompt_template.format(human_input=human_input)
            response = await asyncio.to_thread(ollama.chat, model=ollama_model, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}])
            ai_response = response['message']['content'].strip(); logger.debug(f"Raw Primary AI response (attempt {attempt + 1}): {ai_response}")
            match = COMMAND_PATTERN.search(ai_response)
            if match:
                if COMMAND_PATTERN.groups >= _UNSAFE_TAG_CONTENT_GROUP and match.group(_UNSAFE_TAG_CONTENT_GROUP) is not None:
                    unsafe_message = match.group(_UNSAFE_TAG_CONTENT_GROUP).strip(); logger.warning(f"Primary AI unsafe query: '{human_input}'. Msg: '{unsafe_message}'"); append_output(f"⚠️ AI (Primary) Refusal: {unsafe_message}", style_class='ai-unsafe'); return None, ai_response 
                for group_index in _COMMAND_EXTRACT_GROUPS:
                    if COMMAND_PATTERN.groups >= group_index and (extracted_candidate := match.group(group_index)) is not None:
                        if raw_candidate_from_regex is None: raw_candidate_from_regex = extracted_candidate.strip()
                        cleaned_linux_command = _clean_extracted_command(extracted_candidate)
                        if cleaned_linux_command: logger.debug(f"_interpret_and_clean_tagged_ai_output returning: Cleaned='{cleaned_linux_command}', Raw='{raw_candidate_from_regex}'"); return cleaned_linux_command, raw_candidate_from_regex
                logger.warning(f"Primary AI matched pattern but no valid cmd extracted. Raw: {ai_response}, Match: '{match.group(0)}'")
            else: logger.error(f"Primary AI response did not match patterns. Response: {ai_response}")
            if attempt < ollama_call_retries: logger.info(f"Retrying Primary AI call (parsing/match fail) (attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'."); await asyncio.sleep(retry_delay); continue
            else: logger.error(f"Primary AI parsing/match failed after {ollama_call_retries+1} attempts. Last response: {ai_response}"); return None, raw_candidate_from_regex if raw_candidate_from_regex is not None else ai_response
        except ollama.ResponseError as e_resp: current_attempt_exception = e_resp; append_output(f"❌ Ollama API Error (Primary): {e_resp.error if hasattr(e_resp, 'error') else e_resp}", style_class='error'); logger.error(f"Ollama API Error (Primary): {e_resp}", exc_info=True); return None, raw_candidate_from_regex 
        except ollama.RequestError as e_req: current_attempt_exception = e_req; append_output(f"❌ Ollama Connection Error (Primary): {e_req}", style_class='error'); logger.error(f"Ollama Connection Error (Primary): {e_req}", exc_info=True) 
        except Exception as e_gen: current_attempt_exception = e_gen; append_output(f"❌ AI Processing Error (Primary): {e_gen}", style_class='error'); logger.exception(f"Unexpected error in _interpret_and_clean_tagged_ai_output for '{human_input}'") 
        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries: logger.info(f"Retrying Primary AI call after error '{type(current_attempt_exception).__name__}' (attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'."); await asyncio.sleep(retry_delay)
            else: logger.error(f"All Primary AI call attempts failed for '{human_input}'. Last error: {current_attempt_exception}"); return None, raw_candidate_from_regex
    logger.error(f"_interpret_and_clean_tagged_ai_output exhausted retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}"); return None, raw_candidate_from_regex

async def _get_direct_ai_output(human_input: str) -> tuple[str | None, str | None]:
    """Calls secondary translation AI, cleans response."""
    direct_translator_model = config['ai_models'].get('direct_translator')
    if not direct_translator_model: logger.info("_get_direct_ai_output skipped: No direct_translator_model configured."); return None, None
    system_prompt = config['prompts']['direct_translator']['system']; user_prompt_template = config['prompts']['direct_translator']['user_template']
    retry_delay = config['behavior']['ai_retry_delay_seconds']
    ollama_call_retries = config.get('behavior', {}).get('ollama_api_call_retries', 2) 
    raw_response_content = None; last_exception_in_ollama_call = None
    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None
        try:
            logger.info(f"To Direct AI (model: {direct_translator_model}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'"); user_prompt = user_prompt_template.format(human_input=human_input)
            response = await asyncio.to_thread(ollama.chat, model=direct_translator_model, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}])
            raw_response_content = response['message']['content'].strip(); logger.debug(f"Raw Direct AI response (attempt {attempt + 1}): {raw_response_content}")
            cleaned_linux_command = _clean_extracted_command(raw_response_content)
            if cleaned_linux_command: logger.debug(f"_get_direct_ai_output returning: Cleaned='{cleaned_linux_command}', Raw='{raw_response_content}'"); return cleaned_linux_command, raw_response_content
            else:
                logger.warning(f"Direct AI response resulted in empty command after cleaning. Raw: {raw_response_content}")
                if attempt < ollama_call_retries: await asyncio.sleep(retry_delay); continue
                else: return None, raw_response_content
        except ollama.ResponseError as e_resp: current_attempt_exception = e_resp; append_output(f"❌ Ollama API Error (Direct): {e_resp.error if hasattr(e_resp, 'error') else e_resp}", style_class='error'); logger.error(f"Ollama API Error (Direct): {e_resp}", exc_info=True); return None, raw_response_content 
        except ollama.RequestError as e_req: current_attempt_exception = e_req; append_output(f"❌ Ollama Connection Error (Direct): {e_req}", style_class='error'); logger.error(f"Ollama Connection Error (Direct): {e_req}", exc_info=True) 
        except Exception as e_gen: current_attempt_exception = e_gen; append_output(f"❌ AI Processing Error (Direct): {e_gen}", style_class='error'); logger.exception(f"Unexpected error in _get_direct_ai_output for '{human_input}'") 
        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries: logger.info(f"Retrying Direct AI call after error '{type(current_attempt_exception).__name__}' (attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'."); await asyncio.sleep(retry_delay)
            else: logger.error(f"All Direct AI call attempts failed for '{human_input}'. Last error: {current_attempt_exception}"); return None, raw_response_content
    logger.error(f"_get_direct_ai_output exhausted retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}"); return None, raw_response_content

async def get_validated_ai_command(human_query: str) -> tuple[str | None, str | None]:
    """Attempts to get a validated Linux command using primary and secondary AI translators."""
    logger.info(f"Attempting validated translation for: '{human_query}'"); last_raw_candidate_primary = None; last_raw_candidate_secondary = None; last_cleaned_command_attempt = None
    translation_cycles = config['behavior']['translation_validation_cycles']; retry_delay = config['behavior']['ai_retry_delay_seconds']
    primary_model_name = config['ai_models']['primary_translator']; secondary_model_name = config['ai_models'].get('direct_translator')
    for i in range(translation_cycles):
        append_output(f"🧠 AI translation & validation cycle {i+1}/{translation_cycles} for: '{human_query}'", style_class='ai-thinking') 
        if get_app().is_running : get_app().invalidate()
        append_output(f"    P-> Trying Primary Translator ({primary_model_name})...", style_class='ai-thinking-detail') 
        logger.debug(f"Cycle {i+1}: Trying primary translator.")
        cleaned_command_p, raw_candidate_p = await _interpret_and_clean_tagged_ai_output(human_query)
        if raw_candidate_p is not None: last_raw_candidate_primary = raw_candidate_p
        if cleaned_command_p:
            last_cleaned_command_attempt = cleaned_command_p; append_output(f"  P-> Primary Translated to: '{cleaned_command_p}'. Validating...", style_class='ai-thinking-detail') 
            if get_app().is_running : get_app().invalidate()
            is_valid_by_validator = await is_valid_linux_command_according_to_ai(cleaned_command_p)
            if is_valid_by_validator is True: logger.info(f"Validator confirmed primary: '{cleaned_command_p}'"); append_output(f"  P-> ✅ AI Validator confirmed: '{cleaned_command_p}'", style_class='success'); return cleaned_command_p, raw_candidate_p 
            elif is_valid_by_validator is False: logger.warning(f"Validator rejected primary: '{cleaned_command_p}'"); append_output(f"  P-> ❌ AI Validator rejected: '{cleaned_command_p}'.", style_class='warning') 
            else: logger.warning(f"Validator inconclusive for primary: '{cleaned_command_p}'"); append_output(f"  P-> ⚠️ AI Validator inconclusive for: '{cleaned_command_p}'.", style_class='warning') 
        else: logger.warning(f"Primary AI translation (cycle {i+1}) failed. Raw: {raw_candidate_p}"); append_output(f"  P-> Primary translation failed.", style_class='warning') 
        if secondary_model_name:
            append_output(f"    S-> Trying Secondary Translator ({secondary_model_name})...", style_class='ai-thinking-detail') 
            logger.debug(f"Cycle {i+1}: Trying secondary translator.")
            cleaned_command_s, raw_candidate_s = await _get_direct_ai_output(human_query)
            if raw_candidate_s is not None: last_raw_candidate_secondary = raw_candidate_s
            if cleaned_command_s:
                last_cleaned_command_attempt = cleaned_command_s; append_output(f"  S-> Secondary Translated to: '{cleaned_command_s}'. Validating...", style_class='ai-thinking-detail') 
                if get_app().is_running : get_app().invalidate()
                is_valid_by_validator = await is_valid_linux_command_according_to_ai(cleaned_command_s)
                if is_valid_by_validator is True: logger.info(f"Validator confirmed secondary: '{cleaned_command_s}'"); append_output(f"  S-> ✅ AI Validator confirmed: '{cleaned_command_s}'", style_class='success'); return cleaned_command_s, raw_candidate_s 
                elif is_valid_by_validator is False: logger.warning(f"Validator rejected secondary: '{cleaned_command_s}'"); append_output(f"  S-> ❌ AI Validator rejected: '{cleaned_command_s}'.", style_class='warning') 
                else: logger.warning(f"Validator inconclusive for secondary: '{cleaned_command_s}'"); append_output(f"  S-> ⚠️ AI Validator inconclusive for: '{cleaned_command_s}'.", style_class='warning') 
            else: logger.warning(f"Secondary AI translation (cycle {i+1}) failed. Raw: {raw_candidate_s}"); append_output(f"  S-> Secondary translation failed.", style_class='warning') 
        else: logger.debug(f"Cycle {i+1}: Secondary translator not configured.")
        if i < translation_cycles - 1: append_output(f"Retrying translation & validation cycle {i+2}/{translation_cycles}...", style_class='ai-thinking'); await asyncio.sleep(retry_delay) 
        else:
            logger.error(f"All {translation_cycles} translation cycles failed for '{human_query}'."); append_output(f"❌ AI failed to produce validated command after {translation_cycles} cycles.", style_class='error') 
            final_raw_candidate = last_raw_candidate_secondary if last_raw_candidate_secondary is not None else last_raw_candidate_primary
            if last_cleaned_command_attempt: append_output(f"ℹ️ Offering last unvalidated attempt for categorization: '{last_cleaned_command_attempt}'", style_class='info') 
            return last_cleaned_command_attempt, final_raw_candidate
    return None, None 

# --- Command Categorization Subsystem ---
def _load_single_category_file(file_path: str) -> dict:
    """Loads a single category JSON file, ensuring structure."""
    categories = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f: loaded_data = json.load(f)
            for cat_name_key in set(CATEGORY_MAP.values()): 
                if cat_name_key not in loaded_data: categories[cat_name_key] = []
                elif not isinstance(loaded_data[cat_name_key], list): 
                    logger.warning(f"Category '{cat_name_key}' in {file_path} not list. Resetting."); categories[cat_name_key] = []
                else: 
                    categories[cat_name_key] = [str(cmd) for cmd in loaded_data[cat_name_key] if isinstance(cmd, str)]
            logger.info(f"Loaded categories from {file_path}")
            return categories
        except json.JSONDecodeError as e: logger.error(f"Error decoding JSON from {file_path}: {e}. Returning empty.", exc_info=True)
        except Exception as e: logger.error(f"Error loading categories from {file_path}: {e}. Returning empty.", exc_info=True)
    else: logger.info(f"{file_path} not found. Returning empty.")
    return {cat_name: [] for cat_name in set(CATEGORY_MAP.values())} 

def load_and_merge_command_categories():
    """Loads default and user categories, merges them, and updates the global cache."""
    global _CURRENTLY_LOADED_CATEGORIES
    default_categories = _load_single_category_file(DEFAULT_CATEGORY_PATH)
    if not os.path.exists(DEFAULT_CATEGORY_PATH): 
        logger.info(f"{DEFAULT_CATEGORY_FILENAME} not found. Creating empty one.")
        try:
            with open(DEFAULT_CATEGORY_PATH, "w") as f: json.dump({cat_name: [] for cat_name in set(CATEGORY_MAP.values())}, f, indent=2)
        except Exception as e_create: logger.error(f"Could not create empty {DEFAULT_CATEGORY_FILENAME}: {e_create}")
    user_categories = _load_single_category_file(USER_CATEGORY_PATH)
    merged_categories = {k: list(v) for k, v in default_categories.items()} 
    for category_name, user_cmds_in_category in user_categories.items():
        if category_name not in merged_categories: merged_categories[category_name] = [] 
        for user_cmd in user_cmds_in_category:
            for cat_list in merged_categories.values(): 
                if user_cmd in cat_list: cat_list.remove(user_cmd)
            if user_cmd not in merged_categories[category_name]: 
                merged_categories[category_name].append(user_cmd)
    _CURRENTLY_LOADED_CATEGORIES = merged_categories
    logger.info("Default and user command categories loaded/merged.")

def classify_command(cmd: str) -> str:
    """Checks the loaded & merged categories to find the classification."""
    if not _CURRENTLY_LOADED_CATEGORIES: load_and_merge_command_categories() 
    if not cmd: return UNKNOWN_CATEGORY_SENTINEL
    for category_name, full_commands_in_category in _CURRENTLY_LOADED_CATEGORIES.items():
        if cmd in full_commands_in_category: return category_name
    return UNKNOWN_CATEGORY_SENTINEL

def _save_user_command_categories(user_data: dict):
    """Saves data to the user command categories JSON file."""
    try:
        with open(USER_CATEGORY_PATH, "w") as f: json.dump(user_data, f, indent=2)
        logger.info(f"User command categories saved to {USER_CATEGORY_PATH}")
    except Exception as e: logger.error(f"Failed to save user categories to {USER_CATEGORY_PATH}: {e}", exc_info=True); append_output(f"❌ Error saving user categories: {e}", style_class='error') 

def add_command_to_category(full_cmd_to_add: str, category_input: str):
    """Adds or updates a command's category in the USER FILE."""
    if not full_cmd_to_add: append_output("⚠️ Cannot add empty command.", style_class='warning'); return 
    target_category_name = CATEGORY_MAP.get(category_input.lower(), category_input if category_input in CATEGORY_MAP.values() else None)
    if not target_category_name: append_output(f"❌ Invalid category: '{category_input}'. Valid: simple, semi_interactive, interactive_tui.", style_class='error'); return 
    user_categories = _load_single_category_file(USER_CATEGORY_PATH); cmd_found_in_user_file_old_cat = None
    for cat_name, cmds_list in user_categories.items(): 
        if full_cmd_to_add in cmds_list:
            if cat_name != target_category_name: cmds_list.remove(full_cmd_to_add); cmd_found_in_user_file_old_cat = cat_name
            else: append_output(f"ℹ️ Command '{full_cmd_to_add}' already set as '{target_category_name}' by user.", style_class='info'); load_and_merge_command_categories(); return 
    if target_category_name not in user_categories: user_categories[target_category_name] = [] 
    if full_cmd_to_add not in user_categories[target_category_name]: user_categories[target_category_name].append(full_cmd_to_add)
    _save_user_command_categories(user_categories); load_and_merge_command_categories() 
    if cmd_found_in_user_file_old_cat: append_output(f"✅ Command '{full_cmd_to_add}' moved from '{cmd_found_in_user_file_old_cat}' to '{target_category_name}' in your settings.", style_class='success') 
    else: append_output(f"✅ Command '{full_cmd_to_add}' set as '{target_category_name}' in your settings.", style_class='success') 

def remove_command_from_category(full_cmd_to_remove: str):
    """Removes a command from the user's explicit categorizations."""
    if not full_cmd_to_remove: append_output("⚠️ Cannot remove empty command.", style_class='warning'); return 
    user_categories = _load_single_category_file(USER_CATEGORY_PATH); found_and_removed_from_user = False
    for category_name, commands_in_category in user_categories.items():
        if full_cmd_to_remove in commands_in_category: commands_in_category.remove(full_cmd_to_remove); found_and_removed_from_user = True 
    if found_and_removed_from_user:
        _save_user_command_categories(user_categories); load_and_merge_command_categories()
        append_output(f"🗑️ Command '{full_cmd_to_remove}' removed from your explicit settings. May revert to default.", style_class='info') 
    else: append_output(f"⚠️ Command '{full_cmd_to_remove}' not found in your explicit user settings.", style_class='warning') 

def list_categorized_commands():
    """Displays all categorized commands (merged view)."""
    if not _CURRENTLY_LOADED_CATEGORIES: load_and_merge_command_categories()
    append_output("📄 Current command categories (defaults + user overrides):", style_class='info-header') 
    for cat_name in sorted(list(set(CATEGORY_MAP.values()))):
        full_commands_in_cat = sorted(_CURRENTLY_LOADED_CATEGORIES.get(cat_name, []))
        append_output(f"\n🔹 {cat_name} ({CATEGORY_DESCRIPTIONS.get(cat_name, '')}):", style_class='info-subheader') 
        if full_commands_in_cat:
            for cmd in full_commands_in_cat:
                 append_output(f"  - {cmd}", style_class='info-item') 
        else: append_output("  (No commands in this category)", style_class='info-item-empty') 
    append_output("") 

def move_command_category(full_cmd_to_move: str, new_category_input: str):
    """Moves a command to a new category in the user's settings."""
    add_command_to_category(full_cmd_to_move, new_category_input) 

def handle_command_subsystem_input(input_str: str):
    """Parses and handles '/command' subcommands."""
    try: parts = shlex.split(input_str.strip())
    except ValueError as e: append_output(f"❌ Error parsing /command: {e}", style_class='error'); logger.warning(f"shlex error for /command '{input_str}': {e}"); return 
    cmd_help = (f"ℹ️ /command usage:\n" 
                  f"  add \"<cmd>\" <cat>   - Add command to a category.\n"
                  f"  remove \"<cmd>\"      - Remove command from your settings.\n"
                  f"  list                - List all categorized commands.\n"
                  f"  move \"<cmd>\" <new_cat> - Move command to a new category.\n"
                  f"  help                - Show this help message.\n"
                  f"Categories: 1/simple, 2/semi_interactive, 3/interactive_tui\n"
                  f"  simple: {CATEGORY_DESCRIPTIONS['simple']}\n"
                  f"  semi_interactive: {CATEGORY_DESCRIPTIONS['semi_interactive']}\n"
                  f"  interactive_tui: {CATEGORY_DESCRIPTIONS['interactive_tui']}")
    if len(parts) < 2 or parts[0] != "/command": append_output(f"❌ Invalid /command.\n{cmd_help}", style_class='error'); return 
    subcmd = parts[1].lower()
    if subcmd == "add":
        if len(parts) == 4: add_command_to_category(parts[2], parts[3])
        else: append_output(f"❌ Usage: /command add \"<cmd>\" <cat>\n{cmd_help}", style_class='error') 
    elif subcmd == "remove":
        if len(parts) == 3: remove_command_from_category(parts[2])
        else: append_output(f"❌ Usage: /command remove \"<cmd>\"\n{cmd_help}", style_class='error') 
    elif subcmd == "list":
        if len(parts) == 2: list_categorized_commands()
        else: append_output(f"❌ Usage: /command list\n{cmd_help}", style_class='error') 
    elif subcmd == "move":
        if len(parts) == 4: move_command_category(parts[2], parts[3])
        else: append_output(f"❌ Usage: /command move \"<cmd>\" <new_cat>\n{cmd_help}", style_class='error') 
    elif subcmd == "help": append_output(cmd_help, style_class='help-base') 
    else: append_output(f"❌ Unknown /command subcommand '{subcmd}'.\n{cmd_help}", style_class='error') 

# --- Main Application Setup and Run ---
def run_shell():
    """Sets up and runs the prompt_toolkit application."""
    global output_field, input_field, key_help_field, app, auto_scroll, current_directory
    load_and_merge_command_categories() 
    history = FileHistory(HISTORY_FILE_PATH)
    home_dir = os.path.expanduser("~")
    max_prompt_len = config.get('ui', {}).get('max_prompt_length', 20) 

    if current_directory == home_dir: initial_prompt_dir = "~"
    elif current_directory.startswith(home_dir + os.sep):
        rel_path = current_directory[len(home_dir)+1:]; full_rel_prompt = "~/" + rel_path
        initial_prompt_dir = full_rel_prompt if len(full_rel_prompt) <= max_prompt_len else "~/" + "..." + rel_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
    else:
        base_name = os.path.basename(current_directory)
        initial_prompt_dir = base_name if len(base_name) <= max_prompt_len else "..." + base_name[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."
    
    initial_welcome_message = (
        "Welcome to micro_X Shell 🚀\n"
        "Type a Linux command, or try '/ai your query' (e.g., /ai list text files).\n"
        "Key shortcuts are shown below. For more help, type '/help'.\n"
        "Use '/command help' for category options, '/utils help' for utilities, or '/update' to get new code.\n"
    )
    
    global output_buffer
    output_buffer = [('class:welcome', initial_welcome_message)] # Initialize with styled welcome message

    # FIX: Initialize TextArea with text from buffer directly
    output_field = TextArea(
        text="".join([content for _, content in output_buffer]), # Set initial text here
        style='class:output-field', 
        scrollbar=True, 
        focusable=False, 
        wrap_lines=True, 
        read_only=True
    )
    # REMOVE: output_field.buffer.text = "".join([content for _, content in output_buffer]) 
    # This line was causing the EditReadOnlyBuffer error.

    input_field = TextArea(
        prompt=f"({initial_prompt_dir}) > ", 
        style='class:input-field', 
        multiline=True, 
        wrap_lines=False, 
        history=history, 
        accept_handler=normal_input_accept_handler, 
        height=config['behavior']['input_field_height']
    )
    
    key_help_text = "Ctrl+N: Newline | Enter: Submit | Ctrl+C/D: Exit/Cancel | Tab: Complete/Indent | ↑/↓: History/Lines | PgUp/PgDn: Scroll"
    key_help_field = Window(content=FormattedTextControl(key_help_text), height=1, style='class:key-help')
    layout_components = [output_field, Window(height=1, char='─', style='class:line'), input_field, key_help_field]
    root_container = HSplit(layout_components); layout = Layout(root_container, focused_element=input_field)
    
    base_style = Style.from_dict({
        'output-field': 'bg:#282c34 #abb2bf', 
        'input-field': 'bg:#21252b #d19a66', 
        'key-help': 'bg:#282c34 #5c6370', 
        'line': '#3e4451', 
        'prompt': 'bg:#21252b #61afef', 
        'scrollbar.background': 'bg:#282c34', 
        'scrollbar.button': 'bg:#3e4451',
        'default': '#abb2bf', 
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
    final_style = base_style
    
    def on_output_cursor_pos_changed(_=None):
        """Manages auto-scroll behavior for the output field."""
        global auto_scroll, categorization_flow_active
        if categorization_flow_active: 
            if output_field and output_field.buffer: output_field.buffer.cursor_position = len(output_field.buffer.text)
            return
        if not (output_field and output_field.window and output_field.window.render_info): return
        doc = output_field.buffer.document; render_info = output_field.window.render_info
        if doc.line_count > render_info.window_height and doc.cursor_position_row < (doc.line_count - render_info.window_height + 1):
            if auto_scroll: logger.debug("Auto-scroll disabled (user scrolled up)."); auto_scroll = False
        else: 
            if not auto_scroll: logger.debug("Auto-scroll enabled (cursor near bottom or not scrollable)."); auto_scroll = True
    output_field.buffer.on_cursor_position_changed += on_output_cursor_pos_changed
    input_field.buffer.accept_handler = normal_input_accept_handler
    
    app = Application(layout=layout, key_bindings=kb, style=final_style, full_screen=True, mouse_support=True)
    
    logger.info("micro_X Shell application starting.")
    try: app.run()
    except (EOFError, KeyboardInterrupt): print("\nExiting micro_X Shell. 👋"); logger.info("Exiting due to EOF or KeyboardInterrupt at app level.")
    except Exception as e: print(f"\nUnexpected critical error: {e}"); logger.critical("Critical error during app.run()", exc_info=True)
    finally: logger.info("micro_X Shell application stopped.")

if __name__ == "__main__":
    run_shell()
