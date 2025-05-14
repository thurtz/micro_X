#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.application import get_app
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.dimension import D

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

# --- Configuration Constants ---
LOG_DIR = "logs"
CONFIG_DIR = "config"
CATEGORY_FILENAME = "command_categories.json"
HISTORY_FILENAME = ".micro_x_history"
REQUIREMENTS_FILENAME = "requirements.txt" # Added for the update command
OLLAMA_MODEL = 'llama3.2:3b' # Primary model for translation (expects tags)
OLLAMA_DIRECT_TRANSLATOR_MODEL = 'vitali87/shell-commands-qwen2-1.5b' # Secondary model (direct output)
OLLAMA_VALIDATOR_MODEL = 'herawen/lisa:latest' # Validator model
TMUX_POLL_TIMEOUT_SECONDS = 300 # How long to wait for semi-interactive tmux output
TMUX_SEMI_INTERACTIVE_SLEEP_SECONDS = 1 # Grace period after semi-interactive command finishes in tmux
INPUT_FIELD_HEIGHT = 3 # Height of the input text area
UNKNOWN_CATEGORY_SENTINEL = "##UNKNOWN_CATEGORY##" # Internal marker for uncategorized commands
DEFAULT_CATEGORY_FOR_UNCLASSIFIED = "simple" # Category to use if user skips categorization
VALIDATOR_AI_ATTEMPTS = 3 # Number of times to ask the validator AI for a single validation decision
TRANSLATION_VALIDATION_CYCLES = 3 # How many times to try getting a validated translation
AI_RETRY_DELAY_SECONDS = 1 # Delay between AI call retries within functions

# --- Path Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Ensure log and config directories exist relative to the script location
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True)
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
CATEGORY_PATH = os.path.join(SCRIPT_DIR, CONFIG_DIR, CATEGORY_FILENAME)
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME)
REQUIREMENTS_FILE_PATH = os.path.join(SCRIPT_DIR, REQUIREMENTS_FILENAME) # Added

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG, # Log detailed information
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE), # Log to a file
    ]
)
logger = logging.getLogger(__name__)

# --- Command Category Mapping ---
# Allows using numbers or names for categories
CATEGORY_MAP = {
    "1": "simple", "2": "semi_interactive", "3": "interactive_tui",
    "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
}

# --- Global Variables ---
output_buffer = [] # Stores lines of text for the output area
output_field = None # prompt_toolkit widget for displaying output
input_field = None # prompt_toolkit widget for user input
key_help_field = None # prompt_toolkit widget for showing keybindings
app = None # The main prompt_toolkit Application instance
auto_scroll = True # Flag to control automatic scrolling of the output area
current_directory = os.getcwd() # Track the current working directory
categorization_flow_active = False # Flag indicating if the interactive categorization is active
categorization_flow_state = {} # Dictionary to hold state during categorization

# --- Keybindings ---
kb = KeyBindings()

@kb.add('c-c')
@kb.add('c-d')
def _handle_exit_or_cancel(event):
    """Handles Ctrl+C and Ctrl+D. Exits the app or cancels categorization."""
    global categorization_flow_active, categorization_flow_state
    if categorization_flow_active:
        append_output("\n⚠️ Categorization cancelled by user.")
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
        event.current_buffer.insert_text('    ')

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
        if doc.cursor_position_row == 0:
            if buff.history_backward():
                buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                event.app.invalidate()
        else:
            buff.cursor_up()

@kb.add('down')
def _handle_down_arrow(event):
    """Handles Down Arrow key. Navigates history or moves cursor down."""
    buff = event.current_buffer
    doc = buff.document
    if not categorization_flow_active:
        if doc.cursor_position_row == doc.line_count - 1:
            if buff.history_forward():
                buff.document = Document(text=buff.text, cursor_position=len(buff.text))
                event.app.invalidate()
        else:
            buff.cursor_down()

# --- Output Area Management ---
def append_output(text: str):
    """Appends text to the output buffer and updates the output TextArea widget."""
    global output_buffer, output_field, auto_scroll
    if not text.endswith('\n'):
        text += '\n'
    output_buffer.append(text)

    if output_field:
        new_text = ''.join(output_buffer)
        buffer = output_field.buffer
        current_cursor_pos = buffer.cursor_position
        buffer.set_document(Document(new_text, cursor_position=len(new_text)), bypass_readonly=True)

        if auto_scroll or categorization_flow_active:
            buffer.cursor_position = len(new_text)
        else:
            if current_cursor_pos < len(new_text):
                buffer.cursor_position = current_cursor_pos
            else:
                 buffer.cursor_position = len(new_text)

        if get_app().is_running:
            get_app().invalidate()
        else:
            logger.debug(f"Output appended while app not running (no invalidation): {text.strip()}")


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
        max_prompt_len = 20
        if current_directory == home_dir:
            dir_for_prompt = "~"
        elif current_directory.startswith(home_dir + os.sep):
            relative_path = current_directory[len(home_dir)+1:]
            full_rel_prompt = "~/" + relative_path
            if len(full_rel_prompt) <= max_prompt_len:
                dir_for_prompt = full_rel_prompt
            else:
                chars_to_keep_at_end = max_prompt_len - 5
                dir_for_prompt = "~/" + "..." + relative_path[-chars_to_keep_at_end:] if chars_to_keep_at_end > 0 else "~/... "
        else:
            path_basename = os.path.basename(current_directory)
            if len(path_basename) <= max_prompt_len:
                dir_for_prompt = path_basename
            else:
                chars_to_keep_at_end = max_prompt_len - 3
                dir_for_prompt = "..." + path_basename[-chars_to_keep_at_end:] if chars_to_keep_at_end > 0 else "..."

        input_field.prompt = f"({dir_for_prompt}) > "
        input_field.buffer.accept_handler = normal_input_accept_handler
        input_field.multiline = True

# --- AI Command Validation ---
async def is_valid_linux_command_according_to_ai(command_text: str) -> bool | None:
    """
    Asks the Validator AI model if the given text is a valid Linux command.
    """
    if not command_text or len(command_text) < 2 or len(command_text) > 200:
        logger.debug(f"Skipping AI validation for command_text of length {len(command_text)}: '{command_text}'")
        return None

    validator_system_prompt = "You are a Linux command validation assistant. Your task is to determine if a given string is likely a valid Linux command. If the string looks like a phrase rather than a linux command then the answer is no. If the string looks like a Linux command rather than a phrase then the answer is yes. Answer only with 'yes' or 'no'."
    validator_user_prompt = f"Is the following string likely a Linux command: '{command_text}'"

    responses = []
    for i in range(VALIDATOR_AI_ATTEMPTS):
        logger.info(f"To Validator AI (model: {OLLAMA_VALIDATOR_MODEL}, attempt {i+1}/{VALIDATOR_AI_ATTEMPTS}): '{command_text}'")
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_VALIDATOR_MODEL,
                messages=[
                    {'role': 'system', 'content': validator_system_prompt},
                    {'role': 'user', 'content': validator_user_prompt}
                ]
            )
            ai_answer = response['message']['content'].strip().lower()
            logger.debug(f"Validator AI response (attempt {i+1}) for '{command_text}': '{ai_answer}'")

            is_yes = re.search(r'\byes\b', ai_answer, re.IGNORECASE) is not None
            is_no = re.search(r'\bno\b', ai_answer, re.IGNORECASE) is not None

            if is_yes and not is_no:
                responses.append(True)
            elif is_no and not is_yes:
                responses.append(False)
            else:
                responses.append(None)
                logger.warning(f"Validator AI unclear answer (attempt {i+1}): '{ai_answer}'")
        except Exception as e:
            logger.error(f"Error calling Validator AI (attempt {i+1}) for '{command_text}': {e}", exc_info=True)
            responses.append(None)

        if i < VALIDATOR_AI_ATTEMPTS - 1 and (len(responses) <= i+1 or responses[-1] is None):
             await asyncio.sleep(AI_RETRY_DELAY_SECONDS / 2)

    yes_count = responses.count(True)
    no_count = responses.count(False)
    logger.debug(f"Validator AI responses for '{command_text}': Yes: {yes_count}, No: {no_count}, Unclear/Error: {responses.count(None)}")

    if yes_count >= (VALIDATOR_AI_ATTEMPTS // 2 + 1):
        return True
    elif no_count >= (VALIDATOR_AI_ATTEMPTS // 2 + 1):
        return False
    else:
        logger.warning(f"Validator AI result inconclusive for '{command_text}' after {VALIDATOR_AI_ATTEMPTS} attempts.")
        return None

# --- Update Command Helper ---
def get_file_hash(filepath):
    """Calculates SHA256 hash of a file."""
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

async def handle_update_command():
    """Handles the /update command to fetch latest changes from git."""
    append_output("🔄 Checking for updates...")
    logger.info("Update command received. Checking for git.")
    if get_app().is_running: get_app().invalidate()


    if not shutil.which("git"):
        append_output("❌ Update failed: 'git' command not found. Please ensure git is installed and in your PATH.")
        logger.error("Update command failed: git not found.")
        return

    original_req_hash = get_file_hash(REQUIREMENTS_FILE_PATH)
    requirements_changed = False

    try:
        # Determine current branch
        branch_process = await asyncio.to_thread(
            subprocess.run,
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=SCRIPT_DIR, # Run git commands in the script's directory
            capture_output=True,
            text=True,
            check=True # Raise exception for non-zero exit code
        )
        current_branch = branch_process.stdout.strip()
        append_output(f"ℹ️ Currently on branch: '{current_branch}'. Fetching updates...")
        logger.info(f"Current git branch: {current_branch}")
        if get_app().is_running: get_app().invalidate()


        # Perform git pull
        pull_process = await asyncio.to_thread(
            subprocess.run,
            ['git', 'pull', 'origin', current_branch],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True
            # Not using check=True here to handle output messages for "Already up to date"
        )

        if pull_process.returncode == 0:
            append_output(f"✅ Git pull successful.\nOutput:\n{pull_process.stdout.strip()}")
            logger.info(f"Git pull output: {pull_process.stdout.strip()}")

            if "Already up to date." in pull_process.stdout:
                append_output("✅ micro_X is already up to date.")
            else:
                append_output("✅ Updates downloaded.")
                # Check if requirements.txt changed
                new_req_hash = get_file_hash(REQUIREMENTS_FILE_PATH)
                if original_req_hash != new_req_hash:
                    requirements_changed = True
                    append_output("⚠️ requirements.txt has changed.")
                    logger.info("requirements.txt changed during update.")

                append_output("💡 Please restart micro_X for changes to take effect.")
                if requirements_changed:
                    append_output("💡 After restarting, you may need to update dependencies by running from your terminal (outside micro_X):")
                    append_output(f"   cd \"{SCRIPT_DIR}\"")
                    append_output(f"   source .venv/bin/activate")
                    append_output(f"   pip install -r {REQUIREMENTS_FILENAME}")
        else:
            append_output(f"❌ Git pull failed.\nError:\n{pull_process.stderr.strip()}")
            logger.error(f"Git pull failed. Stderr: {pull_process.stderr.strip()}")

    except subprocess.CalledProcessError as e:
        append_output(f"❌ Update failed: Error executing git command.\n{e.stderr}")
        logger.error(f"Update command git error: {e}", exc_info=True)
    except FileNotFoundError: # Should be caught by shutil.which earlier, but as a safeguard
        append_output("❌ Update failed: 'git' command not found.")
        logger.error("Update command failed: git not found (redundant check).")
    except Exception as e:
        append_output(f"❌ An unexpected error occurred during update: {e}")
        logger.error(f"Unexpected error during update: {e}", exc_info=True)
    finally:
        if get_app().is_running: get_app().invalidate()


# --- Command Handling Logic ---
async def handle_input_async(user_input: str):
    """Main asynchronous function to process user input."""
    global current_directory, categorization_flow_active
    if categorization_flow_active:
        logger.warning("handle_input_async called while categorization_flow_active. Ignoring.")
        return

    user_input_stripped = user_input.strip()
    logger.info(f"Received user input: '{user_input_stripped}'")
    if not user_input_stripped:
        return

    if user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
        append_output("Exiting micro_X Shell 🚪")
        logger.info("Exit command received.")
        if get_app().is_running:
            get_app().exit()
        return

    # ADDED: Handle /update command
    if user_input_stripped.lower() == "/update":
        await handle_update_command()
        return

    if user_input_stripped.startswith("/ai "):
        human_query = user_input_stripped[len("/ai "):].strip()
        if not human_query:
            append_output("⚠️ AI query is empty.")
            return
        append_output(f"🤖 AI Query: {human_query}\n🧠 Thinking...")
        if get_app().is_running: get_app().invalidate()

        linux_command, ai_raw_candidate = await get_validated_ai_command(human_query)

        if linux_command:
            append_output(f"🤖 AI Suggests (validated): {linux_command}")
            await process_command(
                command_str_original=linux_command,
                original_user_input_for_display=f"/ai {human_query} -> {linux_command}",
                ai_raw_candidate=ai_raw_candidate,
                original_direct_input_if_different=None
            )
        else:
            append_output("🤔 AI could not produce a validated command for your query.")
        return

    if user_input_stripped.startswith("/command"):
        handle_command_subsystem_input(user_input_stripped)
        return

    category = classify_command(user_input_stripped)

    if category != UNKNOWN_CATEGORY_SENTINEL:
        logger.debug(f"Direct input '{user_input_stripped}' is a known command in category '{category}'.")
        await process_command(
            command_str_original=user_input_stripped,
            original_user_input_for_display=user_input_stripped,
            ai_raw_candidate=None,
            original_direct_input_if_different=None
        )
    else:
        logger.debug(f"Direct input '{user_input_stripped}' is unknown. Querying Validator AI.")
        append_output(f"🔎 Validating '{user_input_stripped}' with AI...")
        if get_app().is_running: get_app().invalidate()

        is_cmd_ai_says = await is_valid_linux_command_according_to_ai(user_input_stripped)

        has_space = ' ' in user_input_stripped
        is_path_indicator = user_input_stripped.startswith(('/', './', '../'))
        has_double_hyphen = '--' in user_input_stripped
        has_single_hyphen_option = bool(re.search(r'(?:^|\s)-\w', user_input_stripped))
        is_problematic_leading_dollar = False
        if user_input_stripped.startswith('$'):
            if len(user_input_stripped) == 1:
                is_problematic_leading_dollar = True
            elif len(user_input_stripped) > 1 and user_input_stripped[1].isalnum() and user_input_stripped[1] != '{':
                 is_problematic_leading_dollar = True

        is_command_syntax_present = is_path_indicator or \
                                    has_double_hyphen or \
                                    has_single_hyphen_option or \
                                    ('$' in user_input_stripped and not is_problematic_leading_dollar)

        user_input_looks_like_phrase = False
        if is_problematic_leading_dollar:
            user_input_looks_like_phrase = True
        elif not has_space:
            user_input_looks_like_phrase = False
        elif is_command_syntax_present:
            user_input_looks_like_phrase = False
        else:
            user_input_looks_like_phrase = True

        logger.debug(f"Input: '{user_input_stripped}', Validator AI: {is_cmd_ai_says}, Looks like phrase (heuristic): {user_input_looks_like_phrase}")

        if is_cmd_ai_says is True and not user_input_looks_like_phrase:
            append_output(f"✅ AI believes '{user_input_stripped}' is a direct command. Proceeding to categorize.")
            logger.info(f"Validator AI confirmed '{user_input_stripped}' as a command (and it doesn't look like a phrase).")
            await process_command(
                command_str_original=user_input_stripped,
                original_user_input_for_display=user_input_stripped,
                ai_raw_candidate=None,
                original_direct_input_if_different=None
            )
        else:
            log_msg = ""
            ui_msg = ""
            if is_cmd_ai_says is False:
                log_msg = f"Validator AI suggests '{user_input_stripped}' is not a command."
                ui_msg = f"💬 AI suggests '{user_input_stripped}' is not a direct command. Attempting as natural language query..."
            elif is_cmd_ai_says is True and user_input_looks_like_phrase:
                log_msg = f"Validator AI confirmed '{user_input_stripped}' as command, but heuristic overrides due to phrase-like structure."
                ui_msg = f"💬 AI validated '{user_input_stripped}' as command, but it looks like a phrase. Attempting as natural language query..."
            else: # is_cmd_ai_says is None
                log_msg = f"Validator AI response for '{user_input_stripped}' inconclusive."
                ui_msg = f"⚠️ AI validation for '{user_input_stripped}' was inconclusive. Attempting as natural language query..."

            logger.info(f"{log_msg} Treating as natural language.")
            append_output(ui_msg)
            if get_app().is_running: get_app().invalidate()

            linux_command, ai_raw_candidate = await get_validated_ai_command(user_input_stripped)

            if linux_command:
                append_output(f"🤖 AI Translated & Validated to: {linux_command}")
                original_direct_for_prompt = user_input_stripped if linux_command != user_input_stripped else None
                await process_command(
                    command_str_original=linux_command,
                    original_user_input_for_display=f"'{user_input_stripped}' -> {linux_command}",
                    ai_raw_candidate=ai_raw_candidate,
                    original_direct_input_if_different=original_direct_for_prompt
                )
            else:
                append_output(f"🤔 AI could not produce a validated command for '{user_input_stripped}'. Treating original input as a potential direct command.")
                logger.info(f"Validated AI translation failed for '{user_input_stripped}'. Proceeding to categorize original input directly.")
                await process_command(
                    command_str_original=user_input_stripped,
                    original_user_input_for_display=user_input_stripped,
                    ai_raw_candidate=ai_raw_candidate,
                    original_direct_input_if_different=None
                )


async def process_command(command_str_original: str, original_user_input_for_display: str,
                          ai_raw_candidate: str | None = None,
                          original_direct_input_if_different: str | None = None):
    """
    Processes a command string after initial handling/translation/validation.
    """
    global current_directory
    if command_str_original.strip().startswith("cd "):
        handle_cd_command(command_str_original)
        return

    command_for_classification = command_str_original
    category = classify_command(command_for_classification)
    command_to_be_added_if_new = command_for_classification

    if category == UNKNOWN_CATEGORY_SENTINEL:
        logger.info(f"Command '{command_for_classification}' is not categorized. Initiating interactive flow.")
        categorization_result = await prompt_for_categorization(
            command_initially_proposed=command_for_classification,
            ai_raw_candidate_for_suggestions=ai_raw_candidate,
            original_direct_input_if_different=original_direct_input_if_different
        )

        if categorization_result.get('action') == 'cancel_execution':
            append_output(f"Execution of '{command_for_classification}' cancelled.")
            logger.info(f"Execution of '{command_for_classification}' cancelled by user.")
            return
        elif categorization_result.get('action') == 'categorize_and_execute':
            command_to_be_added_if_new = categorization_result['command']
            chosen_cat_for_json = categorization_result['category']
            add_command_to_category(command_to_be_added_if_new, chosen_cat_for_json)
            category = chosen_cat_for_json
            logger.info(f"Command '{command_to_be_added_if_new}' categorized as '{category}'.")
            if command_to_be_added_if_new != command_str_original:
                 logger.info(f"Using '{command_to_be_added_if_new}' for execution based on categorization choice, overriding '{command_str_original}'.")
                 command_str_original = command_to_be_added_if_new
        else:
            category = DEFAULT_CATEGORY_FOR_UNCLASSIFIED
            append_output(f"Executing '{command_for_classification}' as default category '{category}'.")
            logger.info(f"Command '{command_for_classification}' will be executed with default category '{category}'.")

    command_to_execute_expanded = expand_shell_variables(command_str_original, current_directory)

    if command_str_original != command_to_execute_expanded:
        logger.info(f"Command after variable expansion for execution: '{command_to_execute_expanded}' (original for expansion: '{command_str_original}')")
        if command_to_execute_expanded != command_for_classification and command_to_execute_expanded != command_to_be_added_if_new:
             append_output(f"Expanded for execution: {command_to_execute_expanded}")

    command_to_execute_sanitized = sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
    if not command_to_execute_sanitized:
        append_output(f"Command '{command_to_execute_expanded}' blocked by sanitization after variable expansion.")
        logger.warning(f"Command '{command_to_execute_expanded}' (from '{original_user_input_for_display}') blocked by post-expansion sanitization.")
        return

    logger.info(f"Final command for execution: '{command_to_execute_sanitized}', Category: '{category}'")
    append_output(f"▶️ Executing ({category}): {command_to_execute_sanitized}")

    if category == "simple":
        execute_shell_command(command_to_execute_sanitized, original_user_input_for_display)
    else:
        execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category)

# --- Interactive Categorization Flow ---
async def prompt_for_categorization(command_initially_proposed: str,
                                  ai_raw_candidate_for_suggestions: str | None,
                                  original_direct_input_if_different: str | None) -> dict:
    """
    Initiates and manages the interactive flow for categorizing an unknown command.
    """
    global categorization_flow_active, categorization_flow_state, input_field
    categorization_flow_active = True
    categorization_flow_state = {
        'command_initially_proposed': command_initially_proposed,
        'ai_raw_candidate': ai_raw_candidate_for_suggestions,
        'original_direct_input': original_direct_input_if_different,
        'command_to_add_final': command_initially_proposed,
        'step': 0.5
    }
    flow_completion_future = asyncio.Future()
    categorization_flow_state['future'] = flow_completion_future
    if input_field: input_field.multiline = False

    _ask_step_0_5_confirm_command_base()

    try:
        return await flow_completion_future
    finally:
        restore_normal_input_handler()
        logger.debug("Categorization flow ended.")

def _ask_step_0_5_confirm_command_base():
    """Step 0.5: If AI translation changed the input, ask user which version to use."""
    global categorization_flow_state
    proposed = categorization_flow_state['command_initially_proposed']
    original = categorization_flow_state['original_direct_input']

    if original and original.strip() != proposed.strip():
        append_output(f"\nSystem processed input to: '{proposed}'")
        append_output(f"Your original input was: '{original}'")
        append_output("Which version to use as a base for categorization?")
        append_output(f"  1: Processed ('{proposed}')")
        append_output(f"  2: Original ('{original}')")
        append_output("  3: Modify a new command string")
        append_output("  4: Cancel execution")
        if input_field:
            input_field.prompt = "[Categorize] Choice (1-4): "
            input_field.buffer.accept_handler = _handle_step_0_5_response
            get_app().invalidate()
    else:
        categorization_flow_state['command_to_add_final'] = proposed
        categorization_flow_state['step'] = 1
        _ask_step_1_main_action()

def _handle_step_0_5_response(buff):
    """Handles the user's response from step 0.5."""
    global categorization_flow_state
    response = buff.text.strip()
    proposed = categorization_flow_state['command_initially_proposed']
    original = categorization_flow_state['original_direct_input']

    if response == '1':
        categorization_flow_state['command_to_add_final'] = proposed
        append_output(f"Using processed: '{proposed}'")
        categorization_flow_state['step'] = 1
        _ask_step_1_main_action()
    elif response == '2' and original:
        categorization_flow_state['command_to_add_final'] = original
        append_output(f"Using original: '{original}'")
        categorization_flow_state['step'] = 1
        _ask_step_1_main_action()
    elif response == '3':
        categorization_flow_state['step'] = 3.5
        _ask_step_3_5_enter_custom_command_for_categorization()
    elif response == '4':
        categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else:
        append_output("Invalid choice. Please enter 1-4.")
        _ask_step_0_5_confirm_command_base()
        return

    if response in ['1', '2', '3', '4']:
       if input_field: input_field.buffer.reset()

def _ask_step_1_main_action():
    """Step 1: Ask the user how to categorize the confirmed command string."""
    global categorization_flow_state, input_field
    cmd_display = categorization_flow_state['command_to_add_final']
    append_output(f"\nCommand '{cmd_display}' is not categorized. Choose an action:")
    append_output("  1: Add to 'simple' (Direct execution, output captured)")
    append_output("  2: Add to 'semi_interactive' (Runs in tmux, output captured after exit)")
    append_output("  3: Add to 'interactive_tui' (Runs interactively in tmux)")
    append_output(f"  M: Modify this command string ('{cmd_display}') before adding")
    append_output("  D: Do not categorize (execute as default 'simple' this time only)")
    append_output("  C: Cancel execution")
    if input_field:
        input_field.prompt = "[Categorize] Action (1-3/M/D/C): "
        input_field.buffer.accept_handler = _handle_step_1_main_action_response
        get_app().invalidate()

def _handle_step_1_main_action_response(buff):
    """Handles the user's response from step 1."""
    global categorization_flow_state
    response = buff.text.strip().lower()
    cmd_to_add = categorization_flow_state['command_to_add_final']

    if response in ['1', '2', '3']:
        category_map_key = response
        chosen_category = CATEGORY_MAP.get(category_map_key)
        categorization_flow_state.get('future').set_result({
            'action': 'categorize_and_execute',
            'command': cmd_to_add,
            'category': chosen_category
        })
    elif response == 'm':
        categorization_flow_state['step'] = 4
        _ask_step_4_enter_modified_command(base_command=cmd_to_add)
    elif response == 'd':
        categorization_flow_state.get('future').set_result({'action': 'execute_as_default'})
    elif response == 'c':
        categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else:
        append_output("Invalid choice. Please enter 1-3, M, D, or C.")
        _ask_step_1_main_action()
        return

    if response in ['1', '2', '3', 'm', 'd', 'c']:
        if input_field: input_field.buffer.reset()


def _ask_step_3_5_enter_custom_command_for_categorization():
    """Step 3.5: Ask user to enter a new command string (if chosen in step 0.5)."""
    global categorization_flow_state, input_field
    append_output("\nEnter the new command string you want to categorize:")
    if input_field:
        input_field.prompt = "[Categorize] New command string: "
        input_field.buffer.text = ""
        input_field.buffer.accept_handler = _handle_step_3_5_response
        get_app().invalidate()

def _handle_step_3_5_response(buff):
    """Handles the custom command entered in step 3.5."""
    global categorization_flow_state
    custom_command = buff.text.strip()
    if not custom_command:
        append_output("⚠️ Command cannot be empty. Please try again or cancel (Ctrl+C).")
        _ask_step_3_5_enter_custom_command_for_categorization()
        return

    categorization_flow_state['command_to_add_final'] = custom_command
    append_output(f"Proceeding to categorize: '{custom_command}'")
    categorization_flow_state['step'] = 1
    _ask_step_1_main_action()
    if input_field: input_field.buffer.reset()


def _ask_step_4_enter_modified_command(base_command: str):
    """Step 4: Ask user to modify the existing command string (if chosen in step 1)."""
    global categorization_flow_state, input_field
    append_output(f"\nEnter the modified command string (based on '{base_command}'):")
    if input_field:
        input_field.prompt = f"[Categorize] Modified Command: "
        input_field.buffer.text = base_command
        input_field.buffer.cursor_position = len(base_command)
        input_field.buffer.accept_handler = _handle_step_4_modified_command_response
        get_app().invalidate()

def _handle_step_4_modified_command_response(buff):
    """Handles the modified command entered in step 4."""
    global categorization_flow_state
    modified_command = buff.text.strip()
    if not modified_command:
        append_output("⚠️ Modified command cannot be empty. Using previous.")
    else:
        categorization_flow_state['command_to_add_final'] = modified_command

    categorization_flow_state['step'] = 4.5
    _ask_step_4_5_category_for_modified()

def _ask_step_4_5_category_for_modified():
    """Step 4.5: Ask for the category for the modified command."""
    global categorization_flow_state, input_field
    cmd_to_categorize = categorization_flow_state['command_to_add_final']
    append_output(f"Choose category for the modified command '{cmd_to_categorize}':")
    append_output("  1: simple")
    append_output("  2: semi_interactive")
    append_output("  3: interactive_tui")
    if input_field:
        input_field.prompt = "[Categorize] Category (1-3): "
        input_field.buffer.reset()
        input_field.buffer.accept_handler = _handle_step_4_5_response
        get_app().invalidate()

def _handle_step_4_5_response(buff):
    """Handles the category choice for the modified command (step 4.5)."""
    global categorization_flow_state
    response = buff.text.strip()
    chosen_category = CATEGORY_MAP.get(response)

    if chosen_category:
        categorization_flow_state.get('future').set_result({
            'action': 'categorize_and_execute',
            'command': categorization_flow_state['command_to_add_final'],
            'category': chosen_category
        })
        if input_field: input_field.buffer.reset()
    else:
        append_output("Invalid category choice. Please enter 1, 2, or 3.")
        _ask_step_4_5_category_for_modified()

# --- Built-in Command Handlers ---

def handle_cd_command(full_cd_command: str):
    """Handles the 'cd' command to change the current working directory."""
    global current_directory, input_field
    try:
        parts = full_cd_command.split(" ", 1)
        target_dir_str = parts[1].strip() if len(parts) > 1 else "~"
        expanded_dir_arg = os.path.expanduser(os.path.expandvars(target_dir_str))
        if os.path.isabs(expanded_dir_arg):
            new_dir_abs = expanded_dir_arg
        else:
            new_dir_abs = os.path.abspath(os.path.join(current_directory, expanded_dir_arg))

        if os.path.isdir(new_dir_abs):
            current_directory = new_dir_abs
            if input_field:
                home_dir = os.path.expanduser("~"); max_prompt_len = 20
                if current_directory == home_dir: dir_for_prompt = "~"
                elif current_directory.startswith(home_dir + os.sep):
                    relative_path = current_directory[len(home_dir)+1:]
                    full_rel_prompt = "~/" + relative_path
                    dir_for_prompt = full_rel_prompt if len(full_rel_prompt) <= max_prompt_len else "~/" + "..." + relative_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
                else:
                    path_basename = os.path.basename(current_directory)
                    dir_for_prompt = path_basename if len(path_basename) <= max_prompt_len else "..." + path_basename[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."
                input_field.prompt = f"({dir_for_prompt}) > "
                if get_app().is_running: get_app().invalidate()

            append_output(f"📂 Changed directory to: {current_directory}")
            logger.info(f"Directory changed to: {current_directory}")
        else:
            append_output(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.")
            logger.warning(f"Failed cd to '{new_dir_abs}' (from '{target_dir_str}').")
    except Exception as e:
        append_output(f"❌ Error processing 'cd' command: {e}")
        logger.exception(f"Error in handle_cd_command for input '{full_cd_command}'")

def sanitize_and_validate(command: str, original_input_for_log: str) -> str | None:
    """
    Performs basic checks for potentially dangerous command patterns.
    """
    dangerous_patterns = [
        r'\brm\s+(-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\S*',
        r'\bmkfs\b', r'\bdd\b\s+if=/dev/random', r'\bdd\b\s+if=/dev/zero',
        r'\b(shutdown|reboot|halt|poweroff)\b', r'>\s*/dev/sd[a-z]+',
        r':\(\)\{:\|:&};:', r'\b(wget|curl)\s+.*\s*\|\s*(sh|bash|python|perl)\b',
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            logger.warning(f"DANGEROUS command blocked ('{pattern}'): '{command}' (from '{original_input_for_log}')")
            append_output(f"⚠️ Command blocked for security: {command}")
            return None
    return command

# --- Command Execution ---

def execute_command_in_tmux(command_to_execute: str, original_user_input_display: str, category: str):
    """Executes a command within a new tmux window."""
    try:
        unique_id = str(uuid.uuid4())[:8]
        window_name = f"micro_x_{unique_id}"
        if shutil.which("tmux") is None:
            append_output("Error: tmux not found. Please ensure tmux is installed. ❌")
            logger.error("tmux not found.")
            return

        if category == "semi_interactive":
            log_path = f"/tmp/micro_x_output_{unique_id}.log"
            replacement_for_single_quote = "'\"'\"'"
            escaped_command_str = command_to_execute.replace("'", replacement_for_single_quote)
            wrapped_command = f"bash -c '{escaped_command_str}' |& tee {log_path}; sleep {TMUX_SEMI_INTERACTIVE_SLEEP_SECONDS}"
            tmux_cmd_list = ["tmux", "new-window", "-n", window_name, wrapped_command]
            logger.info(f"Executing semi_interactive tmux: {tmux_cmd_list}")
            process = subprocess.Popen(tmux_cmd_list)
            append_output(f"⚡ Launched semi-interactive command in tmux (window: {window_name}). Waiting for completion (max {TMUX_POLL_TIMEOUT_SECONDS}s)...")
            start_time = time.time()
            output_captured = False
            window_closed = False
            while time.time() - start_time < TMUX_POLL_TIMEOUT_SECONDS:
                try:
                    result = subprocess.run(["tmux", "list-windows", "-F", "#{window_name}"],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, errors="ignore", check=True)
                    if window_name not in result.stdout:
                        logger.info(f"Tmux window '{window_name}' closed.")
                        window_closed = True
                        break
                except (subprocess.CalledProcessError, FileNotFoundError) as tmux_err:
                     logger.warning(f"Error checking tmux windows (continuing poll): {tmux_err}")
                time.sleep(1)

            if not window_closed:
                append_output(f"⚠️ Tmux window '{window_name}' timed out after {TMUX_POLL_TIMEOUT_SECONDS}s. Output might be incomplete.")
                logger.warning(f"Tmux poll for '{window_name}' timed out.")

            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        output_content = f.read().strip()
                    if output_content:
                        append_output(f"Output from '{original_user_input_display}':\n{output_content}")
                        output_captured = True
                    elif window_closed:
                        append_output(f"Output from '{original_user_input_display}': (No output captured)")
                        output_captured = True
                except Exception as e:
                    logger.error(f"Error reading tmux log {log_path}: {e}")
                    append_output(f"❌ Error reading tmux log: {e}")
                finally:
                    try:
                        os.remove(log_path)
                    except OSError as e_del:
                        logger.error(f"Error deleting tmux log {log_path}: {e_del}")
            elif window_closed:
                 append_output(f"Output from '{original_user_input_display}': (Tmux window closed, no log found)")
        else: # category == "interactive_tui"
            tmux_cmd_list = ["tmux", "new-window", "-n", window_name, command_to_execute]
            logger.info(f"Executing interactive_tui tmux: {tmux_cmd_list}")
            append_output(f"⚡ Launching interactive command in tmux (window: {window_name}). micro_X will pause.")
            try:
                subprocess.run(tmux_cmd_list, check=True)
                append_output(f"✅ Interactive tmux session for '{original_user_input_display}' ended.")
            except subprocess.CalledProcessError as e:
                append_output(f"❌ Error or non-zero exit in tmux session '{window_name}': {e}")
                logger.error(f"Error reported by tmux run for cmd '{command_to_execute}': {e}")
            except FileNotFoundError:
                append_output("Error: tmux not found. Cannot launch interactive command. ❌")
                logger.error("tmux not found for interactive_tui execution.")
            except Exception as e_run:
                 append_output(f"❌ Unexpected error running interactive tmux: {e_run}")
                 logger.exception(f"Unexpected error running interactive tmux: {e_run}")
    except subprocess.CalledProcessError as e:
        append_output(f"❌ Error setting up tmux for '{command_to_execute}': {e}")
        logger.exception(f"CalledProcessError during tmux setup: {e}")
    except Exception as e:
        append_output(f"❌ Unexpected error interacting with tmux: {e}")
        logger.exception(f"Unexpected error during tmux interaction: {e}")

def execute_shell_command(command_to_execute: str, original_user_input_display: str):
    """Executes a 'simple' command directly using subprocess, now via bash -c for chain support."""
    global current_directory
    try:
        if not command_to_execute.strip():
            append_output("⚠️ Empty command.")
            logger.warning(f"Attempted to execute empty command: '{command_to_execute}'")
            return

        process = subprocess.Popen(
            ['bash', '-c', command_to_execute],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=current_directory,
            text=True,
            errors='replace'
        )
        stdout, stderr = process.communicate()
        output_prefix = f"Output from '{original_user_input_display}':\n"
        if stdout:
            append_output(f"{output_prefix}{stdout.strip()}")
        if stderr:
            append_output(f"Stderr from '{original_user_input_display}':\n{stderr.strip()}")
        if not stdout and not stderr and process.returncode == 0:
            append_output(f"{output_prefix}(No output)")
        if process.returncode != 0:
            logger.warning(f"Command '{command_to_execute}' (from '{original_user_input_display}') exited with code {process.returncode}")
            if not stderr:
                 append_output(f"⚠️ Command '{original_user_input_display}' exited with code {process.returncode}.")
    except FileNotFoundError:
        append_output(f"❌ Shell (bash) not found. Cannot execute command.")
        logger.error(f"Shell (bash) not found when trying to execute: {command_to_execute}")
    except Exception as e:
        append_output(f"❌ Error executing '{command_to_execute}': {e}")
        logger.exception(f"Error executing shell command: {e}")

# --- AI Integration (Ollama) ---

_COMMAND_PATTERN_STRING = (
    r"<bash>\s*'(.*?)'\s*</bash>"
    r"|<bash>\s*(.*?)\s*</bash>"
    r"|<bash>\s*`(.*?)`\s*</bash>"
    r"|```bash\s*\n([\s\S]*?)\n```"
    r"|<code>\s*'(.*?)'\s*</code>"
    r"|<code>\s*(.*?)\s*</code>"
    r"|<pre>\s*'(.*?)'\s*</pre>"
    r"|<pre>\s*(.*?)\s*</pre>"
    r"|<command>\s*'(.*?)'\s*</command>"
    r"|<command>\s*(.*?)\s*</command>"
    r"|<cmd>\s*'(.*?)'\s*</cmd>"
    r"|<cmd>\s*(.*?)\s*</cmd>"
    r"|```\s*([\s\S]*?)\s*```"
    r"|<unsafe>\s*([\s\S]*?)\s*</unsafe>"
)
try:
    COMMAND_PATTERN = re.compile(_COMMAND_PATTERN_STRING, re.IGNORECASE | re.DOTALL)
    EXPECTED_GROUPS = 14
    logger.debug(f"COMMAND_PATTERN compiled with {COMMAND_PATTERN.groups} groups (expected {EXPECTED_GROUPS}).")
    if COMMAND_PATTERN.groups != EXPECTED_GROUPS:
        logger.error(f"CRITICAL: COMMAND_PATTERN groups mismatch: {COMMAND_PATTERN.groups} vs {EXPECTED_GROUPS}. Extraction might fail.")
except re.error as e:
    logger.critical(f"Failed to compile COMMAND_PATTERN regex: {e}", exc_info=True)
    COMMAND_PATTERN = None

_COMMAND_EXTRACT_GROUPS = list(range(1, 14))
_UNSAFE_TAG_CONTENT_GROUP = 14
_INNER_TAG_EXTRACT_PATTERN = re.compile(r"^\s*<([a-zA-Z0-9_:]+)(?:\s+[^>]*)?>([\s\S]*?)<\/\1>\s*$", re.DOTALL)

def _clean_extracted_command(extracted_candidate: str) -> str:
    """Applies common cleaning steps to a potential command string."""
    processed_candidate = extracted_candidate.strip()
    original_for_log = processed_candidate

    inner_match = _INNER_TAG_EXTRACT_PATTERN.match(processed_candidate)
    if inner_match:
        tag_name = inner_match.group(1).lower()
        if tag_name in ["bash", "code", "cmd", "command", "pre"]:
            extracted_content = inner_match.group(2).strip()
            logger.debug(f"Stripped inner tag <{tag_name}>: '{original_for_log}' -> '{extracted_content}'")
            processed_candidate = extracted_content
        else:
            logger.debug(f"Inner tag <{tag_name}> found but not one of the expected types to strip. Original: '{original_for_log}'")

    if len(processed_candidate) >= 2:
        if processed_candidate.startswith("'") and processed_candidate.endswith("'"):
            processed_candidate = processed_candidate[1:-1].strip()
            logger.debug(f"Stripped outer quotes from '{original_for_log}': -> '{processed_candidate}'")
        elif processed_candidate.startswith("`") and processed_candidate.endswith("`"):
            processed_candidate = processed_candidate[1:-1].strip()
            logger.debug(f"Stripped outer backticks from '{original_for_log}': -> '{processed_candidate}'")

    if (processed_candidate.lower().startswith("bash ") or processed_candidate.lower().startswith("sh ")) and len(processed_candidate) > 6:
         prefix_len = 5 if processed_candidate.lower().startswith("bash ") else 3
         potential_inner_cmd = processed_candidate[prefix_len:].strip()
         if potential_inner_cmd.startswith("<") and potential_inner_cmd.endswith(">") and len(potential_inner_cmd) >=2:
             inner_cmd_content = potential_inner_cmd[1:-1].strip()
             if not any(c in inner_cmd_content for c in '<>|&;'):
                 logger.debug(f"Stripped '{processed_candidate[:prefix_len]}<cmd>' pattern: '{original_for_log}' -> '{inner_cmd_content}'")
                 processed_candidate = inner_cmd_content
             else:
                 logger.debug(f"Retained '{processed_candidate[:prefix_len]}<cmd>' structure due to special chars: '{original_for_log}'")

    if len(processed_candidate) >= 2 and processed_candidate.startswith("<") and processed_candidate.endswith(">"):
        inner_content = processed_candidate[1:-1].strip()
        if not any(c in inner_content for c in '<>|&;'):
            logger.debug(f"Stripped general angle brackets: '{original_for_log}' -> '{inner_content}'")
            processed_candidate = inner_content
        else:
            logger.debug(f"Retained general angle brackets due to special chars: '{original_for_log}'")

    cleaned_linux_command = processed_candidate.strip()
    if cleaned_linux_command.startswith('/') and '/' not in cleaned_linux_command[1:]:
        original_slash_log = cleaned_linux_command
        cleaned_linux_command = cleaned_linux_command[1:]
        logger.debug(f"Stripped leading slash: '{original_slash_log}' -> '{cleaned_linux_command}'")

    logger.debug(f"After cleaning (multi-command truncation removed): '{cleaned_linux_command}'")

    if cleaned_linux_command and not cleaned_linux_command.lower().startswith(("sorry", "i cannot", "unable to", "cannot translate")):
        return cleaned_linux_command
    else:
        if not cleaned_linux_command:
             logger.debug(f"Command discarded after cleaning (empty or refusal): '{original_for_log}'")
        return ""

async def _interpret_and_clean_tagged_ai_output(human_input: str) -> tuple[str | None, str | None]:
    """
    Calls the primary translation AI (expects tags), parses the response, and cleans the extracted command.
    """
    if COMMAND_PATTERN is None:
        logger.error("COMMAND_PATTERN regex is not compiled. Cannot interpret tagged AI output.")
        return None, None

    raw_candidate_from_regex = None
    ollama_call_retries = 2
    last_exception_in_ollama_call = None

    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None
        try:
            logger.info(f"To Primary Translation AI (model: {OLLAMA_MODEL}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'")
            system_prompt = """You are a helpful assistant that translates human language queries into a single, precise Linux command.
Strictly enclose the Linux command within <bash></bash> tags.
Do not add any other explanations, apologies, or text outside these tags.
If the request is ambiguous, unsafe, or cannot be translated into a single command, respond with only "<unsafe>Cannot translate safely</unsafe>" or a similar message within <unsafe> tags."""

            response = await asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f'Translate to a single Linux command: "{human_input}".'}
                ]
            )
            ai_response = response['message']['content'].strip()
            logger.debug(f"Raw Primary Translation AI response (attempt {attempt + 1}): {ai_response}")

            match = COMMAND_PATTERN.search(ai_response)
            if match:
                if COMMAND_PATTERN.groups >= _UNSAFE_TAG_CONTENT_GROUP and match.group(_UNSAFE_TAG_CONTENT_GROUP) is not None:
                    unsafe_message = match.group(_UNSAFE_TAG_CONTENT_GROUP).strip()
                    logger.warning(f"Primary Translation AI indicated unsafe query: '{human_input}'. AI Msg: '{unsafe_message}'")
                    append_output(f"⚠️ AI (Primary): {unsafe_message}")
                    return None, None

                for group_index in _COMMAND_EXTRACT_GROUPS:
                    if COMMAND_PATTERN.groups >= group_index and (extracted_candidate := match.group(group_index)) is not None:
                        if raw_candidate_from_regex is None:
                             raw_candidate_from_regex = extracted_candidate.strip()
                        cleaned_linux_command = _clean_extracted_command(extracted_candidate)
                        if cleaned_linux_command:
                            logger.debug(f"_interpret_and_clean_tagged_ai_output returning: Cleaned='{cleaned_linux_command}', Raw='{raw_candidate_from_regex}'")
                            return cleaned_linux_command, raw_candidate_from_regex

                logger.warning(f"Primary Translation AI response matched pattern but no valid cmd extracted after cleaning. Response: {ai_response}")
            else:
                logger.error(f"Primary Translation AI response did not match expected patterns. Response: {ai_response}")

            if attempt < ollama_call_retries:
                logger.info(f"Retrying Primary Translation AI call due to parsing/match failure (internal attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'.")
                await asyncio.sleep(AI_RETRY_DELAY_SECONDS)
                continue
            else:
                logger.error(f"Primary Translation AI parsing/match failed for '{human_input}' after {ollama_call_retries+1} internal attempts. Last AI response: {ai_response}")
                return None, raw_candidate_from_regex
        except ollama.ResponseError as e_resp:
            current_attempt_exception = e_resp
            append_output(f"❌ Ollama API Error (Primary Translator): {e_resp}")
            logger.error(f"Ollama API Error (Primary Translator): {e_resp}", exc_info=True)
            return None, raw_candidate_from_regex
        except ollama.RequestError as e_req:
            current_attempt_exception = e_req
            append_output(f"❌ Ollama Connection Error (Primary Translator): {e_req}")
            logger.error(f"Ollama Connection Error (Primary Translator): {e_req}", exc_info=True)
        except Exception as e_gen:
            current_attempt_exception = e_gen
            append_output(f"❌ AI Processing Error (Primary Translator): {e_gen}")
            logger.exception(f"Unexpected error in _interpret_and_clean_tagged_ai_output for '{human_input}'")

        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries and not isinstance(current_attempt_exception, ollama.ResponseError):
                logger.info(f"Retrying Primary Translation AI call after error '{type(current_attempt_exception).__name__}' (internal attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'.")
                await asyncio.sleep(AI_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"All Primary Translation AI call attempts failed for '{human_input}'. Last error: {current_attempt_exception}")
                return None, raw_candidate_from_regex

    logger.error(f"_interpret_and_clean_tagged_ai_output exhausted all internal retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}")
    return None, raw_candidate_from_regex

async def _get_direct_ai_output(human_input: str) -> tuple[str | None, str | None]:
    """
    Calls the secondary translation AI (expects direct command output), cleans the response.
    """
    if not OLLAMA_DIRECT_TRANSLATOR_MODEL:
        logger.warning("_get_direct_ai_output called but OLLAMA_DIRECT_TRANSLATOR_MODEL is not set.")
        return None, None

    ollama_call_retries = 2
    last_exception_in_ollama_call = None
    raw_response = None

    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None
        try:
            logger.info(f"To Direct Translation AI (model: {OLLAMA_DIRECT_TRANSLATOR_MODEL}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'")
            direct_translator_system_prompt = "Translate the following user request into a single Linux command. Output only the command. Do not include any other text, explanations, or markdown formatting."

            messages = [
                {'role': 'system', 'content': direct_translator_system_prompt},
                {'role': 'user', 'content': f'Translate to a single Linux command: "{human_input}".'}
            ]

            response = await asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_DIRECT_TRANSLATOR_MODEL,
                messages=messages
            )
            raw_response = response['message']['content'].strip()
            logger.debug(f"Raw Direct Translation AI response (attempt {attempt + 1}): {raw_response}")

            cleaned_linux_command = _clean_extracted_command(raw_response)

            if cleaned_linux_command:
                logger.debug(f"_get_direct_ai_output returning: Cleaned='{cleaned_linux_command}', Raw='{raw_response}'")
                return cleaned_linux_command, raw_response
            else:
                logger.warning(f"Direct Translation AI response resulted in empty command after cleaning. Raw: {raw_response}")
                if attempt < ollama_call_retries:
                    await asyncio.sleep(AI_RETRY_DELAY_SECONDS)
                    continue
                else:
                    return None, raw_response
        except ollama.ResponseError as e_resp:
            current_attempt_exception = e_resp
            append_output(f"❌ Ollama API Error (Direct Translator): {e_resp}")
            logger.error(f"Ollama API Error (Direct Translator): {e_resp}", exc_info=True)
            return None, raw_response
        except ollama.RequestError as e_req:
            current_attempt_exception = e_req
            append_output(f"❌ Ollama Connection Error (Direct Translator): {e_req}")
            logger.error(f"Ollama Connection Error (Direct Translator): {e_req}", exc_info=True)
        except Exception as e_gen:
            current_attempt_exception = e_gen
            append_output(f"❌ AI Processing Error (Direct Translator): {e_gen}")
            logger.exception(f"Unexpected error in _get_direct_ai_output for '{human_input}'")

        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries and not isinstance(current_attempt_exception, ollama.ResponseError):
                logger.info(f"Retrying Direct Translation AI call after error '{type(current_attempt_exception).__name__}' (internal attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'.")
                await asyncio.sleep(AI_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"All Direct Translation AI call attempts failed for '{human_input}'. Last error: {current_attempt_exception}")
                return None, raw_response

    logger.error(f"_get_direct_ai_output exhausted all internal retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}")
    return None, raw_response


async def get_validated_ai_command(human_query: str) -> tuple[str | None, str | None]:
    """
    Attempts to get a validated Linux command using primary (tagged) and secondary (direct) AI translators.
    """
    logger.info(f"Attempting validated translation for: '{human_query}' (using primary/secondary translators)")
    last_raw_candidate_primary = None
    last_raw_candidate_secondary = None
    last_cleaned_command_attempt = None

    for i in range(TRANSLATION_VALIDATION_CYCLES):
        append_output(f"🧠 AI translation & validation cycle {i+1}/{TRANSLATION_VALIDATION_CYCLES} for: '{human_query}'")
        if get_app().is_running : get_app().invalidate()

        append_output(f"   P-> Trying Primary Translator ({OLLAMA_MODEL})...")
        logger.debug(f"Cycle {i+1}: Trying primary translator.")
        cleaned_command_p, raw_candidate_p = await _interpret_and_clean_tagged_ai_output(human_query)
        last_raw_candidate_primary = raw_candidate_p

        if cleaned_command_p:
            last_cleaned_command_attempt = cleaned_command_p
            append_output(f"  P-> Primary Translated to: '{cleaned_command_p}'. Validating...")
            if get_app().is_running : get_app().invalidate()
            is_valid_by_validator = await is_valid_linux_command_according_to_ai(cleaned_command_p)
            if is_valid_by_validator is True:
                logger.info(f"Validator AI confirmed primary translated command: '{cleaned_command_p}'")
                append_output(f"  P-> ✅ AI Validator confirmed: '{cleaned_command_p}'")
                return cleaned_command_p, raw_candidate_p
            elif is_valid_by_validator is False:
                logger.warning(f"Validator AI rejected primary translated command '{cleaned_command_p}'.")
                append_output(f"  P-> ❌ AI Validator rejected: '{cleaned_command_p}'.")
            else:
                logger.warning(f"Validator AI inconclusive for primary translated command '{cleaned_command_p}'.")
                append_output(f"  P-> ⚠️ AI Validator inconclusive for: '{cleaned_command_p}'.")
        else:
            logger.warning(f"Primary AI translation (cycle {i+1}) failed to produce a command for '{human_query}'.")
            append_output(f"  P-> Primary translation failed.")

        if OLLAMA_DIRECT_TRANSLATOR_MODEL:
            append_output(f"  S-> Trying Secondary Translator ({OLLAMA_DIRECT_TRANSLATOR_MODEL})...")
            logger.debug(f"Cycle {i+1}: Trying secondary translator.")
            cleaned_command_s, raw_candidate_s = await _get_direct_ai_output(human_query)
            last_raw_candidate_secondary = raw_candidate_s

            if cleaned_command_s:
                last_cleaned_command_attempt = cleaned_command_s
                append_output(f"  S-> Secondary Translated to: '{cleaned_command_s}'. Validating...")
                if get_app().is_running : get_app().invalidate()
                is_valid_by_validator = await is_valid_linux_command_according_to_ai(cleaned_command_s)
                if is_valid_by_validator is True:
                    logger.info(f"Validator AI confirmed secondary translated command: '{cleaned_command_s}'")
                    append_output(f"  S-> ✅ AI Validator confirmed: '{cleaned_command_s}'")
                    return cleaned_command_s, raw_candidate_s
                elif is_valid_by_validator is False:
                    logger.warning(f"Validator AI rejected secondary translated command '{cleaned_command_s}'.")
                    append_output(f"  S-> ❌ AI Validator rejected: '{cleaned_command_s}'.")
                else:
                    logger.warning(f"Validator AI inconclusive for secondary translated command '{cleaned_command_s}'.")
                    append_output(f"  S-> ⚠️ AI Validator inconclusive for: '{cleaned_command_s}'.")
            else:
                logger.warning(f"Secondary AI translation (cycle {i+1}) failed to produce a command for '{human_query}'.")
                append_output(f"  S-> Secondary translation failed.")

        if i < TRANSLATION_VALIDATION_CYCLES - 1:
             append_output(f"Retrying translation & validation cycle {i+2}/{TRANSLATION_VALIDATION_CYCLES} for '{human_query}'...")
             await asyncio.sleep(AI_RETRY_DELAY_SECONDS)
        else:
            logger.error(f"All {TRANSLATION_VALIDATION_CYCLES} translation & validation cycles failed for '{human_query}'.")
            append_output(f"❌ AI failed to produce a validated command for '{human_query}' after {TRANSLATION_VALIDATION_CYCLES} cycles.")
            final_raw_candidate = last_raw_candidate_secondary if last_raw_candidate_secondary is not None else last_raw_candidate_primary
            return last_cleaned_command_attempt, final_raw_candidate

    return None, None


# --- Command Categorization Subsystem (Now uses full command strings) ---

def load_command_categories() -> dict:
    """Loads the command categories from the JSON file."""
    if os.path.exists(CATEGORY_PATH):
        try:
            with open(CATEGORY_PATH, "r") as f:
                categories = json.load(f)
            for cat_name_key in set(CATEGORY_MAP.values()):
                if cat_name_key not in categories:
                    categories[cat_name_key] = []
                elif not isinstance(categories[cat_name_key], list):
                    logger.warning(f"Category '{cat_name_key}' in JSON is not a list. Resetting.")
                    categories[cat_name_key] = []
            return categories
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {CATEGORY_PATH}: {e}. Defaulting.", exc_info=True)
        except Exception as e:
            logger.error(f"Error loading categories from {CATEGORY_PATH}: {e}. Defaulting.", exc_info=True)
    else:
        logger.info(f"{CATEGORY_PATH} not found. Starting with default empty categories.")
    return {cat_name: [] for cat_name in set(CATEGORY_MAP.values())}

def save_command_categories(data: dict):
    """Saves the command categories dictionary to the JSON file."""
    try:
        os.makedirs(os.path.dirname(CATEGORY_PATH), exist_ok=True)
        with open(CATEGORY_PATH, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Command categories saved to {CATEGORY_PATH}")
    except Exception as e:
        logger.error(f"Failed to save command categories to {CATEGORY_PATH}: {e}", exc_info=True)
        append_output(f"❌ Error saving command categories: {e}")

def classify_command(cmd: str) -> str:
    """
    Checks the loaded categories to find the classification of a given command string.
    """
    if not cmd: return UNKNOWN_CATEGORY_SENTINEL
    known_categories = load_command_categories()
    for category_name, full_commands_in_category in known_categories.items():
        if cmd in full_commands_in_category:
            return category_name
    return UNKNOWN_CATEGORY_SENTINEL

def add_command_to_category(full_cmd_to_add: str, category_input: str):
    """Adds or updates the category for a given command string."""
    known_categories = load_command_categories()
    if not full_cmd_to_add:
        append_output("⚠️ Cannot add empty command.")
        return

    target_category_name = CATEGORY_MAP.get(category_input.lower(),
                                           category_input if category_input in CATEGORY_MAP.values() else None)
    if not target_category_name:
        append_output(f"❌ Invalid category specified: '{category_input}'. Use 1/simple, 2/semi_interactive, or 3/interactive_tui.")
        return

    removed_from_old = False
    for cat_name, cmds_list in known_categories.items():
        if full_cmd_to_add in cmds_list and cat_name != target_category_name:
            cmds_list.remove(full_cmd_to_add)
            append_output(f"ℹ️ Command '{full_cmd_to_add}' removed from previous category '{cat_name}'.")
            removed_from_old = True
            break

    if target_category_name not in known_categories:
        known_categories[target_category_name] = []

    if full_cmd_to_add in known_categories[target_category_name]:
        if not removed_from_old:
            append_output(f"⚠️ Command '{full_cmd_to_add}' is already classified as '{target_category_name}'. No changes made.")
        return
    else:
        known_categories[target_category_name].append(full_cmd_to_add)
        save_command_categories(known_categories)
        append_output(f"✅ Command '{full_cmd_to_add}' added to category '{target_category_name}'.")

def remove_command_from_category(full_cmd_to_remove: str):
    """Removes a command string from its category."""
    known_categories = load_command_categories()
    if not full_cmd_to_remove:
        append_output("⚠️ Cannot remove empty command.")
        return

    found_and_removed = False
    for category_name, commands_in_category in known_categories.items():
        if full_cmd_to_remove in commands_in_category:
            commands_in_category.remove(full_cmd_to_remove)
            save_command_categories(known_categories)
            append_output(f"🗑️ Command '{full_cmd_to_remove}' removed from category '{category_name}'.")
            found_and_removed = True
            break

    if not found_and_removed:
        append_output(f"⚠️ Command '{full_cmd_to_remove}' not found in any category.")

def list_categorized_commands():
    """Displays all categorized commands, grouped by category."""
    known_categories = load_command_categories()
    output_lines = ["📄 Current command categories:"]
    for cat_name in sorted(list(set(CATEGORY_MAP.values()))):
        full_commands_in_cat = sorted(known_categories.get(cat_name, []))
        output_lines.append(f"\n🔹 {cat_name}:")
        if full_commands_in_cat:
            output_lines.extend([f"  - {cmd}" for cmd in full_commands_in_cat])
        else:
            output_lines.append("  (No commands)")
    append_output("\n".join(output_lines))

def move_command_category(full_cmd_to_move: str, new_category_input: str):
    """Moves a command from its current category to a new one."""
    known_categories = load_command_categories()
    if not full_cmd_to_move:
        append_output("⚠️ Cannot move empty command.")
        return

    new_target_category_name = CATEGORY_MAP.get(new_category_input.lower(),
                                                new_category_input if new_category_input in CATEGORY_MAP.values() else None)
    if not new_target_category_name:
        append_output(f"❌ Invalid new category specified: '{new_category_input}'.")
        return

    current_category_of_cmd = None
    found_in_a_category = False
    for cat_name, cmds_list in known_categories.items():
        if full_cmd_to_move in cmds_list:
            current_category_of_cmd = cat_name
            found_in_a_category = True
            if cat_name == new_target_category_name:
                append_output(f"⚠️ Command '{full_cmd_to_move}' is already in category '{new_target_category_name}'. No changes needed.")
                return
            cmds_list.remove(full_cmd_to_move)
            break

    if not found_in_a_category:
        append_output(f"⚠️ Command '{full_cmd_to_move}' not found in any category to move.")
        return

    if new_target_category_name not in known_categories:
        known_categories[new_target_category_name] = []
    if full_cmd_to_move not in known_categories[new_target_category_name]:
        known_categories[new_target_category_name].append(full_cmd_to_move)
    else:
        logger.warning(f"Command '{full_cmd_to_move}' was already present in target category '{new_target_category_name}' during move.")

    save_command_categories(known_categories)
    append_output(f"🔄 Command '{full_cmd_to_move}' moved from '{current_category_of_cmd}' to '{new_target_category_name}'.")

def handle_command_subsystem_input(input_str: str):
    """Parses and handles '/command' subcommands (add, remove, list, move, help)."""
    try:
        parts = shlex.split(input_str.strip())
    except ValueError as e:
        append_output(f"❌ Error parsing /command arguments (check quotes?): {e}")
        logger.warning(f"shlex parsing error for /command input '{input_str}': {e}")
        return

    cmd_help = ("ℹ️ /command usage:\n"
                "  add \"<full command>\" <cat_id|name> | remove \"<full command>\" | list\n"
                "  move \"<full command>\" <new_cat_id|name> | help\n"
                "  Note: Wrap commands containing spaces in double quotes.\n"
                "  Categories: 1/simple, 2/semi_interactive, 3/interactive_tui")

    if len(parts) < 2 or parts[0] != "/command":
        append_output(f"❌ Invalid /command structure.\n{cmd_help}")
        return

    subcmd = parts[1].lower()

    if subcmd == "add":
        if len(parts) == 4:
            add_command_to_category(parts[2], parts[3])
        else:
            append_output(f"❌ Usage: /command add \"<full_command>\" <category>\n{cmd_help}")
    elif subcmd == "remove":
        if len(parts) == 3:
            remove_command_from_category(parts[2])
        else:
            append_output(f"❌ Usage: /command remove \"<full_command>\"\n{cmd_help}")
    elif subcmd == "list":
        if len(parts) == 2:
            list_categorized_commands()
        else:
            append_output(f"❌ Usage: /command list\n{cmd_help}")
    elif subcmd == "move":
        if len(parts) == 4:
            move_command_category(parts[2], parts[3])
        else:
            append_output(f"❌ Usage: /command move \"<full_command>\" <new_category>\n{cmd_help}")
    elif subcmd == "help":
        append_output(cmd_help)
    else:
        append_output(f"❌ Unknown /command subcommand '{subcmd}' or wrong number of arguments.\n{cmd_help}")


# --- Main Application Setup and Run ---
def run_shell():
    """Sets up and runs the prompt_toolkit application."""
    global output_field, input_field, key_help_field, app, auto_scroll, current_directory

    history = FileHistory(HISTORY_FILE_PATH)
    home_dir, max_prompt_len = os.path.expanduser("~"), 20
    if current_directory == home_dir: initial_prompt_dir = "~"
    elif current_directory.startswith(home_dir + os.sep):
        rel_path = current_directory[len(home_dir)+1:]
        full_rel_prompt = "~/" + rel_path
        initial_prompt_dir = full_rel_prompt if len(full_rel_prompt) <= max_prompt_len else "~/" + "..." + rel_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
    else:
        base_name = os.path.basename(current_directory)
        initial_prompt_dir = base_name if len(base_name) <= max_prompt_len else "..." + base_name[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."

    output_field = TextArea(
        text="Welcome to micro_X Shell 🚀\nType '/ai query' or a command. '/command help' for options. '/update' to check for new code.\n", # Updated welcome
        style='class:output-field',
        scrollbar=True,
        focusable=False,
        wrap_lines=True,
        read_only=True
    )
    if not output_buffer:
        output_buffer.append(output_field.text)

    input_field = TextArea(
        prompt=f"({initial_prompt_dir}) > ",
        style='class:input-field',
        multiline=True,
        wrap_lines=False,
        history=history,
        accept_handler=normal_input_accept_handler,
        height=INPUT_FIELD_HEIGHT
    )

    key_help_text = "Ctrl+N: Newline | Enter: Submit | Ctrl+C/D: Exit/Cancel | Tab: Complete/Indent | ↑/↓: History/Lines | PgUp/PgDn: Scroll"
    key_help_field = Window(
        content=FormattedTextControl(key_help_text),
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
        'output-field': 'bg:#282c34 #abb2bf', 'input-field': 'bg:#21252b #d19a66',
        'key-help': 'bg:#282c34 #5c6370', 'line': '#3e4451', 'prompt': 'bg:#21252b #61afef',
        'scrollbar.background': 'bg:#282c34', 'scrollbar.button': 'bg:#3e4451',
    })

    def on_output_cursor_pos_changed(_):
        global auto_scroll, categorization_flow_active
        if categorization_flow_active:
            if output_field and output_field.buffer:
                output_field.buffer.cursor_position = len(output_field.buffer.text)
            return
        if not (output_field and output_field.window and output_field.window.render_info):
            return
        doc = output_field.buffer.document
        render_info = output_field.window.render_info
        if doc.line_count > render_info.window_height and \
           doc.cursor_position_row < (doc.line_count - render_info.window_height):
            if auto_scroll:
                logger.debug("Auto-scroll disabled (user scrolled up).")
                auto_scroll = False
        else:
            if not auto_scroll:
                logger.debug("Auto-scroll enabled (cursor near bottom).")
                auto_scroll = True

    output_field.buffer.on_cursor_position_changed += on_output_cursor_pos_changed
    input_field.buffer.accept_handler = normal_input_accept_handler
    app = Application(
        layout=Layout(layout, focused_element=input_field),
        key_bindings=kb,
        style=style,
        full_screen=True,
        mouse_support=True
    )

    logger.info("micro_X Shell application starting.")
    try:
        app.run()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting micro_X Shell. 👋")
        logger.info("Exiting due to EOF or KeyboardInterrupt.")
    except Exception as e:
        print(f"\nUnexpected critical error occurred: {e}")
        logger.critical("Critical error during app.run()", exc_info=True)
    finally:
        logger.info("micro_X Shell application stopped.")

if __name__ == "__main__":
    run_shell()
