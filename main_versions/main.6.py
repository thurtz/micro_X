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

# --- Configuration Constants ---
LOG_DIR = "logs"
CONFIG_DIR = "config"
CATEGORY_FILENAME = "command_categories.json"
HISTORY_FILENAME = ".micro_x_history" 
OLLAMA_MODEL = 'herawen/lisa' # Main model for translation
OLLAMA_VALIDATOR_MODEL = 'herawen/lisa' # Can be the same or a faster/simpler model
TMUX_POLL_TIMEOUT_SECONDS = 300 
TMUX_SEMI_INTERACTIVE_SLEEP_SECONDS = 1 
INPUT_FIELD_HEIGHT = 3 
UNKNOWN_CATEGORY_SENTINEL = "##UNKNOWN_CATEGORY##" 
DEFAULT_CATEGORY_FOR_UNCLASSIFIED = "simple" 
VALIDATOR_AI_ATTEMPTS = 3 # Number of times to ask the validator AI for a single validation

# --- Path Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True) 
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True) 
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
CATEGORY_PATH = os.path.join(SCRIPT_DIR, CONFIG_DIR, CATEGORY_FILENAME)
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME) 

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger(__name__)

# --- Command Category Mapping ---
CATEGORY_MAP = {
    "1": "simple", "2": "semi_interactive", "3": "interactive_tui",
    "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
}

# --- Global Variables ---
output_buffer = [] 
output_field = None 
input_field = None 
key_help_field = None 
app = None 
auto_scroll = True 
current_directory = os.getcwd() 
categorization_flow_active = False 
categorization_flow_state = {} 

# --- Keybindings ---
kb = KeyBindings()

@kb.add('c-c')
@kb.add('c-d')
def _(event):
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
def _(event):
    if not categorization_flow_active: 
        event.current_buffer.insert_text('\n')

@kb.add('enter')
def _(event):
    buff = event.current_buffer
    if not buff.complete_state: 
        buff.validate_and_handle()


@kb.add('tab')
def _(event):
    buff = event.current_buffer
    if buff.complete_state: 
        event.app.current_buffer.complete_next()
    else: 
        event.current_buffer.insert_text('    ')

@kb.add('pageup')
def _(event):
    if output_field and output_field.window.render_info:
        output_field.window._scroll_up()
        event.app.invalidate() 

@kb.add('pagedown')
def _(event):
    if output_field and output_field.window.render_info:
        output_field.window._scroll_down()
        event.app.invalidate() 

@kb.add('c-up')
def _(event):
    if not categorization_flow_active:
        event.current_buffer.cursor_up(count=1)

@kb.add('c-down')
def _(event):
    if not categorization_flow_active:
        event.current_buffer.cursor_down(count=1)

@kb.add('up')
def _(event):
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
def _(event):
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
    asyncio.create_task(handle_input_async(buff.text))

def restore_normal_input_handler():
    global input_field, current_directory, categorization_flow_active
    categorization_flow_active = False 
    if input_field:
        home_dir = os.path.expanduser("~"); max_prompt_len = 20
        if current_directory == home_dir: dir_for_prompt = "~"
        elif current_directory.startswith(home_dir + os.sep):
            relative_path = current_directory[len(home_dir)+1:]
            dir_for_prompt = "~/" + relative_path if len("~/" + relative_path) <= max_prompt_len else "~/" + "..." + relative_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
        else:
            path_basename = os.path.basename(current_directory)
            dir_for_prompt = path_basename if len(path_basename) <= max_prompt_len else "..." + path_basename[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."
        input_field.prompt = f"({dir_for_prompt}) > "
        input_field.buffer.accept_handler = normal_input_accept_handler
        input_field.multiline = True

# --- AI Command Validation ---
async def is_valid_linux_command_according_to_ai(command_text: str) -> bool | None:
    if not command_text or len(command_text) < 2 or len(command_text) > 200:
        logger.debug(f"Skipping AI validation for command_text of length {len(command_text)}: '{command_text}'")
        return None 

    prompt = f"Is the following string a valid Linux command or a path to an executable? Answer with only the single word 'yes' or 'no'. Do not provide any explanation or other text. String: '{command_text}'"
    
    responses = []
    for i in range(VALIDATOR_AI_ATTEMPTS):
        logger.info(f"To Validator AI (model: {OLLAMA_VALIDATOR_MODEL}, attempt {i+1}/{VALIDATOR_AI_ATTEMPTS}): '{command_text}'")
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_VALIDATOR_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            ai_answer = response['message']['content'].strip().lower()
            logger.debug(f"Validator AI response (attempt {i+1}) for '{command_text}': '{ai_answer}'")
            
            is_yes = re.search(r'\byes\b', ai_answer, re.IGNORECASE)
            is_no = re.search(r'\bno\b', ai_answer, re.IGNORECASE)

            if is_yes and not is_no: responses.append(True)
            elif is_no and not is_yes: responses.append(False)
            else: responses.append(None); logger.warning(f"Validator AI unclear answer (attempt {i+1}): '{ai_answer}'")
        except Exception as e:
            logger.error(f"Error calling Validator AI (attempt {i+1}) for '{command_text}': {e}", exc_info=True)
            responses.append(None) 
        
        if i < VALIDATOR_AI_ATTEMPTS - 1 and len(responses) <= i+1 and responses[-1] is None: 
             await asyncio.sleep(0.5)

    yes_count = responses.count(True)
    no_count = responses.count(False)
    logger.debug(f"Validator AI responses for '{command_text}': Yes: {yes_count}, No: {no_count}, Unclear/Error: {responses.count(None)}")

    if yes_count >= (VALIDATOR_AI_ATTEMPTS // 2 + 1): return True
    elif no_count >= (VALIDATOR_AI_ATTEMPTS // 2 + 1): return False
    else: logger.warning(f"Validator AI result inconclusive for '{command_text}' after {VALIDATOR_AI_ATTEMPTS} attempts."); return None

# --- Command Handling Logic ---
async def handle_input_async(user_input: str): 
    global current_directory, categorization_flow_active
    if categorization_flow_active:
        logger.warning("handle_input_async called while categorization_flow_active. Ignoring."); return

    user_input_stripped = user_input.strip()
    logger.info(f"Received user input: '{user_input_stripped}'")
    if not user_input_stripped: return 

    if user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
        append_output("Exiting micro_X Shell 🚪"); logger.info("Exit command received.");
        if get_app().is_running: get_app().exit(); return

    if user_input_stripped.startswith("/ai "): 
        human_query = user_input_stripped[len("/ai "):].strip()
        if not human_query: append_output("⚠️ AI query is empty."); return
        append_output(f"🤖 AI Query: {human_query}\n🧠 Thinking..."); 
        if get_app().is_running: get_app().invalidate() 
        
        # For /ai, we always want to translate. interpret_human_input does cleaning.
        linux_command, ai_raw_candidate = await interpret_human_input(human_query) 
        
        if linux_command:
            append_output(f"🤖 AI Suggests: {linux_command}")
            await process_command(linux_command, 
                                  original_user_input_for_display=f"/ai {human_query} -> {linux_command}", 
                                  ai_raw_candidate=ai_raw_candidate)
        else: append_output("🤔 AI could not process the request.")
        return

    if user_input_stripped.startswith("/command"): 
        handle_command_subsystem_input(user_input_stripped); return

    # For direct input that is not /ai or /command:
    category = classify_command(user_input_stripped) 

    if category != UNKNOWN_CATEGORY_SENTINEL:
        # Known command, proceed directly
        logger.debug(f"Direct input '{user_input_stripped}' is a known command in category '{category}'.")
        await process_command(user_input_stripped, original_user_input_for_display=user_input_stripped, ai_raw_candidate=None)
    else:
        # Input is not a known categorized command. Query Validator AI.
        logger.debug(f"Direct input '{user_input_stripped}' is unknown. Querying Validator AI.")
        append_output(f"🔎 Validating '{user_input_stripped}' with AI...")
        if get_app().is_running: get_app().invalidate()

        is_cmd_ai_says = await is_valid_linux_command_according_to_ai(user_input_stripped)
        
        user_input_looks_like_phrase = ' ' in user_input_stripped.strip() and \
                                       not user_input_stripped.strip().startswith(('/', './', '../')) 

        if is_cmd_ai_says is True:
            # Validator AI confidently says it's a command. Trust it and proceed to categorize original input.
            # The phrase_like heuristic is removed from this "True" path.
            append_output(f"✅ AI believes '{user_input_stripped}' is a direct command. Proceeding to categorize.")
            logger.info(f"Validator AI confirmed '{user_input_stripped}' as a command.")
            await process_command(user_input_stripped, original_user_input_for_display=user_input_stripped, ai_raw_candidate=None)
        
        else: # This covers "is False" AND "is None" (inconclusive/error from Validator)
              # Default to treating as natural language if validator doesn't confirm it's a command.
            if is_cmd_ai_says is False:
                log_msg = f"Validator AI suggests '{user_input_stripped}' is not a command."
                ui_msg = f"💬 AI suggests '{user_input_stripped}' is not a direct command. Attempting as natural language query..."
            else: # is_cmd_ai_says is None
                log_msg = f"Validator AI response for '{user_input_stripped}' inconclusive."
                ui_msg = f"⚠️ AI validation for '{user_input_stripped}' was inconclusive. Attempting as natural language query..."
            
            logger.info(f"{log_msg} Treating as natural language.")
            append_output(ui_msg)
            if get_app().is_running: get_app().invalidate()

            linux_command, ai_raw_candidate = await interpret_human_input(user_input_stripped) 

            if linux_command:
                append_output(f"🤖 AI Translated to: {linux_command}")
                await process_command(linux_command,
                                      original_user_input_for_display=f"'{user_input_stripped}' -> {linux_command}",
                                      ai_raw_candidate=ai_raw_candidate)
            else:
                append_output(f"🤔 AI could not translate '{user_input_stripped}' into a command. Try '/ai {user_input_stripped}' or rephrase.")


async def process_command(command_str_original: str, original_user_input_for_display: str, ai_raw_candidate: str | None = None):
    global current_directory
    if command_str_original.startswith("cd "):
        handle_cd_command(command_str_original); return

    command_for_classification = command_str_original 
    category = classify_command(command_for_classification) 

    if category == UNKNOWN_CATEGORY_SENTINEL:
        logger.info(f"Command '{command_for_classification}' is not categorized. Initiating interactive flow.")
        categorization_result = await prompt_for_categorization(command_for_classification, ai_raw_candidate)
        
        if categorization_result.get('action') == 'cancel_execution':
            append_output(f"Execution of '{command_for_classification}' cancelled.")
            logger.info(f"Execution of '{command_for_classification}' cancelled by user.")
            return
        elif categorization_result.get('action') == 'categorize_and_execute':
            cmd_added_to_json = categorization_result['command'] 
            chosen_cat_for_json = categorization_result['category']
            add_command_to_category(cmd_added_to_json, chosen_cat_for_json)
            category = chosen_cat_for_json 
            logger.info(f"Command '{cmd_added_to_json}' categorized as '{category}' and will be used for this execution.")
            if cmd_added_to_json != command_str_original:
                 logger.info(f"Using '{cmd_added_to_json}' for execution based on categorization choice.")
                 command_str_original = cmd_added_to_json 
        else: 
            category = DEFAULT_CATEGORY_FOR_UNCLASSIFIED
            append_output(f"Executing '{command_for_classification}' as default category '{category}'.")
            logger.info(f"Command '{command_for_classification}' will be executed with default category '{category}'.")

    command_to_execute_expanded = expand_shell_variables(command_str_original, current_directory)
    if command_str_original != command_to_execute_expanded:
        logger.info(f"Command after variable expansion for execution: '{command_to_execute_expanded}' (original for expansion: '{command_str_original}')")
        if command_to_execute_expanded != command_for_classification: 
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
async def prompt_for_categorization(command_to_categorize_cleaned: str, ai_raw_candidate_for_suggestions: str | None) -> dict:
    global categorization_flow_active, categorization_flow_state, input_field
    categorization_flow_active = True
    categorization_flow_state = {
        'command_cleaned_for_display': command_to_categorize_cleaned, 
        'ai_raw_candidate': ai_raw_candidate_for_suggestions,      
        'command_to_add_final': command_to_categorize_cleaned,     
        'step': 1 
    }
    flow_completion_future = asyncio.Future()
    categorization_flow_state['future'] = flow_completion_future
    if input_field: input_field.multiline = False
    
    _ask_step_1_add_or_not() 
    
    try: return await flow_completion_future
    finally: restore_normal_input_handler(); logger.debug("Categorization flow ended.")

def _ask_step_1_add_or_not():
    global categorization_flow_state, input_field
    cmd_display = categorization_flow_state['command_cleaned_for_display']
    append_output(f"\nCommand '{cmd_display}' is not categorized.")
    append_output("Add to a category? (y/n/c=cancel execution)")
    if input_field:
        input_field.prompt = "[Categorize] Add? (y/n/c): "
        input_field.buffer.accept_handler = _handle_step_1_response
        get_app().invalidate()

def _handle_step_1_response(buff):
    global categorization_flow_state
    response = buff.text.strip().lower()
    if response == 'y':
        categorization_flow_state['step'] = 1.5 
        _ask_step_1_5_check_suggestions()
    elif response == 'n': categorization_flow_state.get('future').set_result({'action': 'execute_as_default'})
    elif response == 'c': categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else: append_output("Invalid. (y/n/c)"); _ask_step_1_add_or_not()

def _ask_step_1_5_check_suggestions():
    global categorization_flow_state
    cmd_cleaned = categorization_flow_state['command_cleaned_for_display']
    raw_candidate = categorization_flow_state.get('ai_raw_candidate')
    suggestions = []

    if raw_candidate:
        all_known_cmds = []
        for cmd_list in load_command_categories().values():
            all_known_cmds.extend(cmd_list)
        
        for known_cmd in set(all_known_cmds): 
            if known_cmd and known_cmd in raw_candidate and known_cmd != cmd_cleaned:
                suggestions.append(known_cmd)
    
    categorization_flow_state['suggestions'] = suggestions
    if suggestions:
        append_output(f"The AI's raw output was: '{raw_candidate[:100]}{'...' if len(raw_candidate)>100 else ''}'")
        append_output("Found these known commands in it:")
        for i, sug_cmd in enumerate(suggestions):
            append_output(f"  {i+1}: {sug_cmd}")
        append_output(f"Use one of these (1-{len(suggestions)}), or (n)one to categorize '{cmd_cleaned}' as is?")
        if input_field:
            input_field.prompt = f"[Categorize] Suggestion (1-{len(suggestions)}/n): "
            input_field.buffer.accept_handler = _handle_step_1_5_response
            get_app().invalidate()
    else: 
        categorization_flow_state['step'] = 2
        _ask_step_2_category_choice()


def _handle_step_1_5_response(buff):
    global categorization_flow_state
    response = buff.text.strip().lower()
    suggestions = categorization_flow_state.get('suggestions', [])

    if response == 'n':
        categorization_flow_state['command_to_add_final'] = categorization_flow_state['command_cleaned_for_display']
        categorization_flow_state['step'] = 2
        _ask_step_2_category_choice()
    else:
        try:
            choice_idx = int(response) - 1
            if 0 <= choice_idx < len(suggestions):
                chosen_suggestion = suggestions[choice_idx]
                append_output(f"Selected suggested command: '{chosen_suggestion}'")
                categorization_flow_state['command_to_add_final'] = chosen_suggestion
                categorization_flow_state['step'] = 2 
                _ask_step_2_category_choice()
            else:
                append_output("Invalid suggestion number.")
                _ask_step_1_5_check_suggestions() 
        except ValueError:
            append_output("Invalid input. Enter a number or 'n'.")
            _ask_step_1_5_check_suggestions() 


def _ask_step_2_category_choice():
    global categorization_flow_state, input_field
    cmd_for_cat_prompt = categorization_flow_state['command_to_add_final'] 
    append_output(f"Enter category for '{cmd_for_cat_prompt}':")
    append_output("(1: simple, 2: semi_interactive, 3: interactive_tui, or full name)")
    if input_field:
        input_field.prompt = "[Categorize] Category: "
        input_field.buffer.accept_handler = _handle_step_2_response
        get_app().invalidate()

def _handle_step_2_response(buff): 
    global categorization_flow_state
    response = buff.text.strip().lower()
    chosen_category = CATEGORY_MAP.get(response, response if response in CATEGORY_MAP.values() else None)
    if chosen_category and chosen_category in set(CATEGORY_MAP.values()):
        categorization_flow_state['chosen_category'] = chosen_category
        categorization_flow_state['step'] = 3; _ask_step_3_modify_command()
    else: append_output(f"Invalid category '{response}'."); _ask_step_2_category_choice()

def _ask_step_3_modify_command(): 
    global categorization_flow_state, input_field
    cmd_to_add_default = categorization_flow_state['command_to_add_final'] 
    append_output(f"The command to be added is currently: '{cmd_to_add_default}'")
    append_output("Modify this command string for categorization (e.g., make it more general, remove specific args)? (y/n)")
    if input_field:
        input_field.prompt = "[Categorize] Modify cmd string? (y/n): "
        input_field.buffer.accept_handler = _handle_step_3_response
        get_app().invalidate()

def _handle_step_3_response(buff): 
    global categorization_flow_state
    response = buff.text.strip().lower()
    if response == 'y': categorization_flow_state['step'] = 4; _ask_step_4_enter_modified_command()
    elif response == 'n':
        categorization_flow_state.get('future').set_result({
            'action': 'categorize_and_execute',
            'command': categorization_flow_state['command_to_add_final'], 
            'category': categorization_flow_state['chosen_category']
        })
    else: append_output("Invalid. (y/n)"); _ask_step_3_modify_command()

def _ask_step_4_enter_modified_command(): 
    global categorization_flow_state, input_field
    default_cmd_for_editing = categorization_flow_state['command_to_add_final']
    append_output(f"Enter the command string to save for categorization (default: '{default_cmd_for_editing}')")
    if input_field:
        input_field.prompt = f"[Categorize] Command to save (default: '{default_cmd_for_editing}'): "
        input_field.buffer.text = default_cmd_for_editing 
        input_field.buffer.cursor_position = len(default_cmd_for_editing)
        input_field.buffer.accept_handler = _handle_step_4_response
        get_app().invalidate()

def _handle_step_4_response(buff): 
    global categorization_flow_state
    final_command_str_to_add = buff.text.strip()
    if not final_command_str_to_add: 
        final_command_str_to_add = categorization_flow_state['command_to_add_final'] 
        append_output(f"Empty input, using: '{final_command_str_to_add}'")
    
    categorization_flow_state['command_to_add_final'] = final_command_str_to_add 
    categorization_flow_state.get('future').set_result({
        'action': 'categorize_and_execute',
        'command': final_command_str_to_add, 
        'category': categorization_flow_state['chosen_category']
    })

def handle_cd_command(full_cd_command: str):
    global current_directory, input_field
    try:
        target_dir_str = full_cd_command.split(" ", 1)[1].strip() if len(full_cd_command.split()) > 1 else "~"
        expanded_dir_arg = os.path.expanduser(os.path.expandvars(target_dir_str))
        new_dir_abs = os.path.abspath(os.path.join(current_directory, expanded_dir_arg)) if not os.path.isabs(expanded_dir_arg) else expanded_dir_arg
        
        if os.path.isdir(new_dir_abs):
            current_directory = new_dir_abs
            if input_field: 
                home_dir = os.path.expanduser("~"); max_prompt_len = 20
                if current_directory == home_dir: dir_for_prompt = "~"
                elif current_directory.startswith(home_dir + os.sep):
                    relative_path = current_directory[len(home_dir)+1:]
                    dir_for_prompt = "~/" + relative_path if len("~/" + relative_path) <= max_prompt_len else "~/" + "..." + relative_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
                else:
                    path_basename = os.path.basename(current_directory)
                    dir_for_prompt = path_basename if len(path_basename) <= max_prompt_len else "..." + path_basename[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."
                input_field.prompt = f"({dir_for_prompt}) > "
            append_output(f"📂 Changed directory to: {current_directory}")
            logger.info(f"Directory changed to: {current_directory}")
        else:
            append_output(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.")
            logger.warning(f"Failed cd to '{new_dir_abs}' (from '{target_dir_str}').")
    except Exception as e:
        append_output(f"❌ Error processing 'cd' command: {e}")
        logger.exception(f"Error in handle_cd_command for input '{full_cd_command}'")

def sanitize_and_validate(command: str, original_input_for_log: str):
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

def execute_command_in_tmux(command_to_execute: str, original_user_input_display: str, category: str):
    try:
        unique_id = str(uuid.uuid4())[:8]; window_name = f"micro_x_{unique_id}"
        if shutil.which("tmux") is None: 
            append_output("Error: tmux not found. Please ensure tmux is installed. ❌"); logger.error("tmux not found."); return
        
        if category == "semi_interactive":
            log_path = f"/tmp/micro_x_output_{unique_id}.log" 
            wrapped_command = f"bash -c '{command_to_execute} |& tee {log_path}; sleep {TMUX_SEMI_INTERACTIVE_SLEEP_SECONDS}'"
            tmux_cmd_list = ["tmux", "new-window", "-d", "-n", window_name, wrapped_command] 
            logger.info(f"Executing semi_interactive tmux: {tmux_cmd_list}")
            subprocess.run(tmux_cmd_list, check=True) 
            append_output(f"⏳ Launched semi-interactive in tmux (window: {window_name}). Waiting (max {TMUX_POLL_TIMEOUT_SECONDS}s)...")
            start_time = time.time(); output_captured, window_closed = False, False
            while time.time() - start_time < TMUX_POLL_TIMEOUT_SECONDS:
                if window_name not in subprocess.run(["tmux", "list-windows", "-F", "#{window_name}"], stdout=subprocess.PIPE, text=True, errors="ignore").stdout:
                    logger.info(f"Tmux window '{window_name}' closed."); window_closed = True; break 
                time.sleep(1) 
            if not window_closed: append_output(f"⚠️ Tmux window '{window_name}' timed out."); logger.warning(f"Tmux poll for '{window_name}' timed out.")
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f: output_content = f.read().strip()
                    if output_content: append_output(f"Output from '{original_user_input_display}':\n{output_content}"); output_captured = True
                    elif window_closed: append_output(f"Output from '{original_user_input_display}': (No output)"); output_captured = True
                except Exception as e: logger.error(f"Error reading tmux log {log_path}: {e}"); append_output(f"❌ Error reading tmux log: {e}")
                finally: 
                    try: os.remove(log_path)
                    except OSError as e_del: logger.error(f"Error deleting tmux log {log_path}: {e_del}")
            if window_closed and not output_captured and not os.path.exists(log_path):
                 append_output(f"Output from '{original_user_input_display}': (Tmux window closed, no log found)")
        else: # "interactive_tui"
            tmux_cmd_list = ["tmux", "new-window", "-n", window_name, command_to_execute]
            logger.info(f"Executing interactive_tui tmux: {tmux_cmd_list}")
            append_output(f"⚡ Launching interactive in tmux (window: {window_name}). micro_X will pause.")
            try:
                subprocess.run(tmux_cmd_list, check=True) 
                append_output(f"✅ Interactive tmux for '{original_user_input_display}' ended.")
            except subprocess.CalledProcessError as e: append_output(f"❌ Error in tmux session '{window_name}': {e}"); logger.error(f"Error for tmux cmd '{command_to_execute}': {e}")
            except FileNotFoundError: append_output("Error: tmux not found. ❌"); logger.error("tmux not found for interactive_tui.") 
    except subprocess.CalledProcessError as e: append_output(f"❌ Error setting up tmux for '{command_to_execute}': {e}"); logger.exception(f"Error for tmux: {e}")
    except Exception as e: append_output(f"❌ Unexpected error with tmux: {e}"); logger.exception(f"Unexpected error with tmux: {e}")

def execute_shell_command(command_to_execute: str, original_user_input_display: str):
    global current_directory
    try:
        parts = shlex.split(command_to_execute)
        if not parts: append_output("⚠️ Empty command."); logger.warning(f"Empty command: {command_to_execute}"); return
        process = subprocess.Popen(parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=current_directory, text=True, errors='replace')
        stdout, stderr = process.communicate() 
        output_prefix = f"Output from '{original_user_input_display}':\n"
        if stdout: append_output(f"{output_prefix}{stdout.strip()}")
        if stderr: append_output(f"Stderr from '{original_user_input_display}':\n{stderr.strip()}")
        if not stdout and not stderr and process.returncode == 0: append_output(f"{output_prefix}(No output)")
        if process.returncode != 0:
            logger.warning(f"Command '{command_to_execute}' (from '{original_user_input_display}') exited code {process.returncode}")
            if not stderr: append_output(f"⚠️ Command '{original_user_input_display}' exited code {process.returncode}.")
    except FileNotFoundError: append_output(f"❌ Command not found: {parts[0] if parts else command_to_execute}"); logger.error(f"Cmd not found: {parts[0] if parts else command_to_execute}")
    except Exception as e: append_output(f"❌ Error executing '{command_to_execute}': {e}"); logger.exception(f"Error executing: {e}")

# --- AI Integration (Ollama) ---
_COMMAND_PATTERN_STRING = (
    r"<bash>\s*'(.*?)'\s*</bash>"      # G1
    r"|<bash>\s*(.*?)\s*</bash>"       # G2
    r"|<bash>\s*`(.*?)`\s*</bash>"     # G3
    r"|```bash\s*\n([\s\S]*?)\n```"    # G4
    r"|<code>\s*'(.*?)'\s*</code>"     # G5
    r"|<code>\s*(.*?)\s*</code>"       # G6
    r"|<pre>\s*'(.*?)'\s*</pre>"        # G7
    r"|<pre>\s*(.*?)\s*</pre>"         # G8
    r"|<command>\s*'(.*?)'\s*</command>"# G9
    r"|<command>\s*(.*?)\s*</command>"  # G10
    r"|<cmd>\s*'(.*?)'\s*</cmd>"       # G11
    r"|<cmd>\s*(.*?)\s*</cmd>"         # G12
    r"|```\s*([\s\S]*?)\s*```"         # G13
    r"|<unsafe>\s*([\s\S]*?)\s*</unsafe>" # G14
)
try:
    COMMAND_PATTERN = re.compile(_COMMAND_PATTERN_STRING, re.IGNORECASE | re.DOTALL)
    EXPECTED_GROUPS = 14 
    logger.debug(f"COMMAND_PATTERN: {COMMAND_PATTERN.groups} groups (expected {EXPECTED_GROUPS}).")
    if COMMAND_PATTERN.groups != EXPECTED_GROUPS:
        logger.error(f"CRITICAL: COMMAND_PATTERN groups mismatch: {COMMAND_PATTERN.groups} vs {EXPECTED_GROUPS}.")
except re.error as e:
    logger.critical(f"Failed to compile COMMAND_PATTERN: {e}", exc_info=True); COMMAND_PATTERN = None 
_COMMAND_EXTRACT_GROUPS = list(range(1, 14)) 
_UNSAFE_TAG_CONTENT_GROUP = 14
_INNER_TAG_EXTRACT_PATTERN = re.compile(r"^\s*<([a-zA-Z0-9_:]+)(?:\s+[^>]*)?>([\s\S]*?)<\/\1>\s*$", re.DOTALL)

async def interpret_human_input(human_input: str) -> tuple[str | None, str | None]:
    """
    Takes a human query, gets a translation from the main Ollama model,
    cleans it, and returns the (cleaned_command, raw_candidate_from_regex).
    Includes internal retries for API calls and parsing.
    """
    if COMMAND_PATTERN is None:
        logger.error("COMMAND_PATTERN not compiled."); append_output("❌ Internal error: AI parser unavailable."); return None, None
    
    raw_candidate_from_regex = None 
    cleaned_linux_command = None
    ollama_call_retries = 2 
    retry_delay_seconds = 1 
    
    last_exception_in_ollama_call = None 

    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None 
        try:
            logger.info(f"To Translation AI (model: {OLLAMA_MODEL}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'")
            response = await asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_MODEL, 
                messages=[
                    {'role': 'system', 'content': 'You are a helpful assistant that translates human language queries into a single, precise Linux command. Strictly enclose the Linux command within <bash></bash> tags. Do not add any other explanations, apologies, or text outside these tags. If the request is ambiguous, unsafe, or cannot be translated into a single command, respond with only "<unsafe>Cannot translate safely</unsafe>" or a similar message within <unsafe> tags.'},
                    {'role': 'user', 'content': f'Translate to a single Linux command: "{human_input}".'}
                ]
            )
            ai_response = response['message']['content'].strip()
            logger.debug(f"Raw Translation AI response (attempt {attempt + 1}): {ai_response}")
            match = COMMAND_PATTERN.search(ai_response)
            
            if match:
                if COMMAND_PATTERN.groups >= _UNSAFE_TAG_CONTENT_GROUP and match.group(_UNSAFE_TAG_CONTENT_GROUP) is not None:
                    unsafe_message = match.group(_UNSAFE_TAG_CONTENT_GROUP).strip()
                    logger.warning(f"Translation AI unsafe query: '{human_input}'. AI Msg: '{unsafe_message}'"); append_output(f"⚠️ AI: {unsafe_message}"); return None, None
                
                for group_index in _COMMAND_EXTRACT_GROUPS:
                    if COMMAND_PATTERN.groups >= group_index and (extracted_candidate := match.group(group_index)) is not None:
                        if raw_candidate_from_regex is None: 
                            raw_candidate_from_regex = extracted_candidate.strip()
                        
                        processed_candidate = extracted_candidate.strip()
                        # STAGE 0: Inner Tag Extraction
                        inner_match = _INNER_TAG_EXTRACT_PATTERN.match(processed_candidate)
                        if inner_match:
                            tag_name = inner_match.group(1).lower()
                            if tag_name in ["bash", "code", "cmd", "command", "pre"]:
                                extracted_content = inner_match.group(2).strip()
                                logger.debug(f"Inner tag <{tag_name}> extracted: '{processed_candidate}' -> '{extracted_content}'"); processed_candidate = extracted_content
                            else: logger.debug(f"Inner tag <{tag_name}> found but not one of the expected types. Original: '{processed_candidate}'")
                        
                        # STAGE 1: Strip quotes/backticks
                        if len(processed_candidate) >= 2:
                            if processed_candidate.startswith("'") and processed_candidate.endswith("'"):
                                processed_candidate = processed_candidate[1:-1].strip(); logger.debug(f"Stripped quotes from '{extracted_candidate.strip()}': -> '{processed_candidate}'")
                            elif processed_candidate.startswith("`") and processed_candidate.endswith("`"):
                                processed_candidate = processed_candidate[1:-1].strip(); logger.debug(f"Stripped backticks from '{extracted_candidate.strip()}': -> '{processed_candidate}'")
                        
                        # STAGE 2: Handle "bash <cmd>" or "sh <cmd>"
                        if (processed_candidate.lower().startswith("bash ") or processed_candidate.lower().startswith("sh ")) and len(processed_candidate) > 6:
                            prefix_len = 5 if processed_candidate.lower().startswith("bash ") else 3
                            potential_inner_cmd = processed_candidate[prefix_len:].strip()
                            if potential_inner_cmd.startswith("<") and potential_inner_cmd.endswith(">") and len(potential_inner_cmd) >=2:
                                inner_cmd_content = potential_inner_cmd[1:-1].strip()
                                if not any(c in inner_cmd_content for c in '<>|&;'): 
                                    logger.debug(f"Stripped '{processed_candidate[:prefix_len]}<cmd>' pattern: '{processed_candidate}' -> '{inner_cmd_content}'"); processed_candidate = inner_cmd_content
                                else: logger.debug(f"Retained '{processed_candidate[:prefix_len]}<cmd>' structure: '{processed_candidate}'")
                        
                        # STAGE 3: Strip general outermost angle brackets
                        if len(processed_candidate) >= 2 and processed_candidate.startswith("<") and processed_candidate.endswith(">"):
                            inner_content = processed_candidate[1:-1].strip()
                            if not any(c in inner_content for c in '<>|&;'): 
                                logger.debug(f"Stripped general angle brackets: '{processed_candidate}' -> '{inner_content}'"); processed_candidate = inner_content
                            else: logger.debug(f"Retained general angle brackets: '{processed_candidate}'")
                        
                        cleaned_linux_command = processed_candidate.strip() 
                        
                        # STAGE 4: Handle erroneously prepended slash
                        if cleaned_linux_command.startswith('/') and '/' not in cleaned_linux_command[1:]:
                            original_for_log = cleaned_linux_command; cleaned_linux_command = cleaned_linux_command[1:]; logger.debug(f"Stripped leading slash: '{original_for_log}' -> '{cleaned_linux_command}'")
                        
                        # STAGE 5: Truncate to first command
                        original_for_multicmd_log = cleaned_linux_command
                        try:
                            first_command_match = re.match(r"^([^;&|]+)", cleaned_linux_command)
                            if first_command_match:
                                first_command_part = first_command_match.group(1).strip()
                                if first_command_part != cleaned_linux_command: logger.info(f"AI multi-cmd: '{original_for_multicmd_log}' truncated to: '{first_command_part}'"); cleaned_linux_command = first_command_part
                            elif any(sep in cleaned_linux_command for sep in (';', '&&', '||')): logger.warning(f"AI cmd '{original_for_multicmd_log}' has separators but no clean first part. Discarding."); cleaned_linux_command = "" 
                        except Exception as e_shlex: logger.error(f"Multi-cmd heuristic error for '{original_for_multicmd_log}': {e_shlex}. Using as is."); cleaned_linux_command = original_for_multicmd_log 
                        
                        if cleaned_linux_command and not cleaned_linux_command.lower().startswith(("sorry", "i cannot", "unable to", "cannot translate")):
                            logger.info(f"Translation AI interpreted '{human_input}' as: '{cleaned_linux_command}' (group {group_index}, after all stripping)")
                            return cleaned_linux_command, raw_candidate_from_regex 
                logger.warning(f"Translation AI response matched but no valid cmd extracted. Response: {ai_response}") 
            else: 
                logger.error(f"Translation AI response no match: {ai_response}") 
            
            if attempt < ollama_call_retries:
                logger.info(f"Retrying Translation AI call due to parsing/match failure (internal attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'."); 
                await asyncio.sleep(retry_delay_seconds) 
                continue 
            else: 
                logger.error(f"Translation AI parsing/match failed for '{human_input}' after {ollama_call_retries+1} internal attempts. Last AI: {ai_response}"); 
                return None, raw_candidate_from_regex 
        
        except ollama.ResponseError as e_resp: 
            current_attempt_exception = e_resp 
            append_output(f"❌ Ollama API Error (Translation): {e_resp}"); logger.error(f"Ollama API Error (Translation): {e_resp}", exc_info=True); 
            return None, raw_candidate_from_regex 
        except ollama.RequestError as e_req: 
            current_attempt_exception = e_req
            append_output(f"❌ Ollama Connection Error (Translation): {e_req}"); logger.error(f"Ollama Connection Error (Translation): {e_req}", exc_info=True)
        except Exception as e_gen: 
            current_attempt_exception = e_gen
            append_output(f"❌ AI Processing Error (Translation): {e_gen}"); logger.exception(f"Unexpected error in interpret_human_input for '{human_input}'") 
        
        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries and not isinstance(current_attempt_exception, ollama.ResponseError): 
                logger.info(f"Retrying Translation AI call after error '{type(current_attempt_exception).__name__}' (internal attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'."); 
                await asyncio.sleep(retry_delay_seconds) 
            else: 
                logger.error(f"All Translation AI call attempts failed for '{human_input}'. Last error: {current_attempt_exception}")
                return None, raw_candidate_from_regex
            
    logger.error(f"interpret_human_input exhausted all internal retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}")
    return None, raw_candidate_from_regex


# --- Command Categorization Subsystem (Now uses full command strings) ---
def load_command_categories() -> dict:
    if os.path.exists(CATEGORY_PATH):
        try:
            with open(CATEGORY_PATH, "r") as f: categories = json.load(f)
            for cat_name_key in set(CATEGORY_MAP.values()): 
                if cat_name_key not in categories: categories[cat_name_key] = []
                elif not isinstance(categories[cat_name_key], list): 
                    logger.warning(f"Category '{cat_name_key}' in JSON is not a list. Resetting.")
                    categories[cat_name_key] = []
            return categories
        except Exception as e: logger.error(f"Error loading {CATEGORY_PATH}: {e}. Defaulting.", exc_info=True)
    else: logger.info(f"{CATEGORY_PATH} not found. Defaulting.")
    return {cat_name: [] for cat_name in set(CATEGORY_MAP.values())}

def save_command_categories(data: dict):
    try:
        os.makedirs(os.path.dirname(CATEGORY_PATH), exist_ok=True)
        with open(CATEGORY_PATH, "w") as f: json.dump(data, f, indent=2)
        logger.info(f"Categories saved to {CATEGORY_PATH}")
    except Exception as e: logger.error(f"Failed to save categories: {e}", exc_info=True); append_output(f"❌ Error saving categories: {e}")

def classify_command(cmd: str) -> str:
    if not cmd: return UNKNOWN_CATEGORY_SENTINEL 
    known_categories = load_command_categories()
    for category_name, full_commands_in_category in known_categories.items():
        if cmd in full_commands_in_category: 
            return category_name
    return UNKNOWN_CATEGORY_SENTINEL 

def add_command_to_category(full_cmd_to_add: str, category_input: str):
    known_categories = load_command_categories()
    if not full_cmd_to_add: append_output("⚠️ Cannot add empty command."); return
    target_category_name = CATEGORY_MAP.get(category_input.lower(), category_input if category_input in CATEGORY_MAP.values() else None)
    if not target_category_name: append_output(f"❌ Invalid category '{category_input}'."); return
    for cat_name, cmds_list in known_categories.items():
        if full_cmd_to_add in cmds_list and cat_name != target_category_name:
            cmds_list.remove(full_cmd_to_add)
            append_output(f"ℹ️ Command '{full_cmd_to_add}' removed from previous category '{cat_name}'."); break 
    if target_category_name not in known_categories: known_categories[target_category_name] = []
    if full_cmd_to_add in known_categories[target_category_name]:
        append_output(f"⚠️ Command '{full_cmd_to_add}' is already classified as '{target_category_name}'."); return
    known_categories[target_category_name].append(full_cmd_to_add)
    save_command_categories(known_categories)
    append_output(f"✅ Command '{full_cmd_to_add}' added to category '{target_category_name}'.")

def remove_command_from_category(full_cmd_to_remove: str):
    known_categories = load_command_categories()
    if not full_cmd_to_remove: append_output("⚠️ Cannot remove empty command."); return
    found_and_removed = False
    for category_name, commands_in_category in known_categories.items():
        if full_cmd_to_remove in commands_in_category:
            commands_in_category.remove(full_cmd_to_remove)
            save_command_categories(known_categories)
            append_output(f"🗑️ Command '{full_cmd_to_remove}' removed from category '{category_name}'."); found_and_removed = True; break 
    if not found_and_removed: append_output(f"⚠️ Command '{full_cmd_to_remove}' not found in any category.")

def list_categorized_commands():
    known_categories = load_command_categories()
    output_lines = ["📄 Current command categories:"]
    for cat_name in sorted(list(set(CATEGORY_MAP.values()))): 
        full_commands_in_cat = sorted(known_categories.get(cat_name, []))
        output_lines.append(f"\n🔹 {cat_name}:")
        output_lines.extend([f"  - {cmd}" for cmd in full_commands_in_cat] if full_commands_in_cat else ["  (No commands)"])
    append_output("\n".join(output_lines))

def move_command_category(full_cmd_to_move: str, new_category_input: str):
    known_categories = load_command_categories()
    if not full_cmd_to_move: append_output("⚠️ Cannot move empty command."); return
    new_target_category_name = CATEGORY_MAP.get(new_category_input.lower(), new_category_input if new_category_input in CATEGORY_MAP.values() else None)
    if not new_target_category_name: append_output(f"❌ Invalid new category '{new_category_input}'."); return
    current_category_of_cmd, found_in_a_category = None, False
    for cat_name, cmds_list in known_categories.items():
        if full_cmd_to_move in cmds_list:
            current_category_of_cmd, found_in_a_category = cat_name, True
            if cat_name == new_target_category_name: append_output(f"⚠️ Command '{full_cmd_to_move}' is already in category '{new_target_category_name}'."); return
            cmds_list.remove(full_cmd_to_move); break 
    if not found_in_a_category: append_output(f"⚠️ Command '{full_cmd_to_move}' not found to move."); return
    if new_target_category_name not in known_categories: known_categories[new_target_category_name] = []
    known_categories[new_target_category_name].append(full_cmd_to_move)
    save_command_categories(known_categories)
    append_output(f"🔄 Command '{full_cmd_to_move}' moved from '{current_category_of_cmd}' to '{new_target_category_name}'.")

def handle_command_subsystem_input(input_str: str):
    parts = shlex.split(input_str.strip()) 
    cmd_help = ("ℹ️ /command usage:\n"
                "  add \"<full command>\" <cat_id|name> | remove \"<full command>\" | list\n"
                "  move \"<full command>\" <new_cat_id|name> | help\n"
                "  Note: Wrap commands with spaces in quotes.\n"
                "  Categories: 1/simple, 2/semi_interactive, 3/interactive_tui")
    if len(parts) < 2 or parts[0] != "/command": append_output(f"❌ Invalid /command.\n{cmd_help}"); return
    subcmd = parts[1].lower()
    if subcmd == "add":
        if len(parts) == 4: add_command_to_category(parts[2], parts[3])
        else: append_output(f"❌ Usage: /command add \"<full_command>\" <category>\n{cmd_help}")
    elif subcmd == "remove":
        if len(parts) == 3: remove_command_from_category(parts[2])
        else: append_output(f"❌ Usage: /command remove \"<full_command>\"\n{cmd_help}")
    elif subcmd == "list":
        if len(parts) == 2: list_categorized_commands()
        else: append_output(f"❌ Usage: /command list\n{cmd_help}")
    elif subcmd == "move":
        if len(parts) == 4: move_command_category(parts[2], parts[3])
        else: append_output(f"❌ Usage: /command move \"<full_command>\" <new_category>\n{cmd_help}")
    elif subcmd == "help": append_output(cmd_help)
    else: append_output(f"❌ Unknown /command subcommand or wrong args.\n{cmd_help}")

# --- Main Application Setup and Run ---
def run_shell():
    global output_field, input_field, key_help_field, app, auto_scroll, current_directory
    history = FileHistory(HISTORY_FILE_PATH)
    home_dir, max_prompt_len = os.path.expanduser("~"), 20
    if current_directory == home_dir: initial_prompt_dir = "~"
    elif current_directory.startswith(home_dir + os.sep):
        rel_path = current_directory[len(home_dir)+1:]
        initial_prompt_dir = "~/" + rel_path if len("~/" + rel_path) <= max_prompt_len else "~/" + "..." + rel_path[-(max_prompt_len - 5):] if (max_prompt_len - 5) > 0 else "~/... "
    else:
        base_name = os.path.basename(current_directory)
        initial_prompt_dir = base_name if len(base_name) <= max_prompt_len else "..." + base_name[-(max_prompt_len - 3):] if (max_prompt_len - 3) > 0 else "..."
    
    output_field = TextArea(text="Welcome to micro_X Shell 🚀\nType '/ai query' or a command. '/command help' for options.\n", style='class:output-field', scrollbar=True, focusable=False, wrap_lines=True, read_only=True)
    if not output_buffer: output_buffer.append(output_field.text)
    
    input_field = TextArea(
        prompt=f"({initial_prompt_dir}) > ", 
        style='class:input-field', 
        multiline=True, 
        wrap_lines=False, 
        history=history, 
        accept_handler=normal_input_accept_handler, 
        height=INPUT_FIELD_HEIGHT 
    )

    key_help_field = Window(content=FormattedTextControl("Ctrl+N: Newline | Enter: Submit | Ctrl+C/D: Exit | Tab: Complete/Indent | ↑/↓: History/Lines | PgUp/PgDn: Scroll"), height=1, style='class:key-help')
    layout = HSplit([output_field, Window(height=1, char='─', style='class:line'), input_field, key_help_field])
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
        if not (output_field and output_field.window and output_field.window.render_info): return
        doc, render_info = output_field.buffer.document, output_field.window.render_info
        if doc.line_count > render_info.window_height and doc.cursor_position_row < (doc.line_count - render_info.window_height):
            if auto_scroll: auto_scroll = False
        elif not auto_scroll: auto_scroll = True
    output_field.buffer.on_cursor_position_changed += on_output_cursor_pos_changed
    input_field.buffer.accept_handler = normal_input_accept_handler
    app = Application(layout=Layout(layout, focused_element=input_field), key_bindings=kb, style=style, full_screen=True, mouse_support=True)
    logger.info("micro_X Shell application starting.")
    try: app.run()
    except (EOFError, KeyboardInterrupt): print("\nExiting micro_X Shell. 👋"); logger.info("Exiting due to EOF/KeyboardInterrupt.")
    except Exception as e: print(f"\nUnexpected critical error: {e}"); logger.critical("Critical error in app.run()", exc_info=True)
    finally: logger.info("micro_X Shell application stopped.")

if __name__ == "__main__":
    run_shell()
