#!/usr/bin/env python

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style # Removed merge_styles as it wasn't used
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.application import get_app # Explicitly import get_app
from prompt_toolkit.history import FileHistory
# Removed D as it wasn't used: from prompt_toolkit.layout.dimension import D
from prompt_toolkit.formatted_text import FormattedText

import asyncio
import subprocess
import uuid
import shlex
import os
import re # Keep re for non-AI parts if any, or remove if fully encapsulated
# Removed ollama import as it's handled by ai_handler
import logging
import json
import time
import shutil
import hashlib # For checking file changes
import sys # Added for /utils command to use the current Python interpreter

# --- Import functions from the new ai_handler module ---
from modules.ai_handler import get_validated_ai_command, is_valid_linux_command_according_to_ai

# --- Import from the new category_manager module ---
from modules.category_manager import (
    init_category_manager,
    classify_command,
    add_command_to_category as cm_add_command_to_category, # Renamed to avoid conflict if used directly
    handle_command_subsystem_input,
    UNKNOWN_CATEGORY_SENTINEL,
    CATEGORY_MAP as CM_CATEGORY_MAP, # Aliased to avoid conflict
    CATEGORY_DESCRIPTIONS as CM_CATEGORY_DESCRIPTIONS # Aliased
)

from modules.output_analyzer import is_tui_like_output

# --- Configuration Constants (File Names & Static Values) ---
LOG_DIR = "logs"
CONFIG_DIR = "config"
# DEFAULT_CATEGORY_FILENAME and USER_CATEGORY_FILENAME are now managed by category_manager
HISTORY_FILENAME = ".micro_x_history"
REQUIREMENTS_FILENAME = "requirements.txt"
# UNKNOWN_CATEGORY_SENTINEL is now imported from category_manager
UTILS_DIR_NAME = "utils"

# --- Path Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(SCRIPT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(os.path.join(SCRIPT_DIR, CONFIG_DIR), exist_ok=True) # Ensures config dir exists
LOG_FILE = os.path.join(SCRIPT_DIR, LOG_DIR, "micro_x.log")
# DEFAULT_CATEGORY_PATH and USER_CATEGORY_PATH are now managed by category_manager
HISTORY_FILE_PATH = os.path.join(SCRIPT_DIR, HISTORY_FILENAME)
REQUIREMENTS_FILE_PATH = os.path.join(SCRIPT_DIR, REQUIREMENTS_FILENAME)
UTILS_DIR_PATH = os.path.join(SCRIPT_DIR, UTILS_DIR_NAME)
os.makedirs(UTILS_DIR_PATH, exist_ok=True)

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
DEFAULT_CONFIG_FILENAME = "default_config.json" # For general config
USER_CONFIG_FILENAME = "user_config.json"       # For general config

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
    config = fallback_config.copy()
    logger.info("Initialized with hardcoded fallback general configurations.")

    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f:
                default_settings = json.load(f)
            config = merge_configs(config, default_settings)
            logger.info(f"Loaded general configurations from {default_config_path}")
        except Exception as e:
            logger.error(f"Error loading {default_config_path}: {e}. Using current config (fallbacks or previously loaded).", exc_info=True)
    else:
        logger.warning(f"{default_config_path} not found. Using fallback defaults. Creating it now.")
        try:
            os.makedirs(os.path.dirname(default_config_path), exist_ok=True)
            with open(default_config_path, 'w') as f:
                json.dump(fallback_config, f, indent=2)
            logger.info(f"Created default general configuration file at {default_config_path} with fallback values.")
        except Exception as e:
            logger.error(f"Could not create default general configuration file at {default_config_path}: {e}", exc_info=True)

    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r') as f:
                user_settings = json.load(f)
            config = merge_configs(config, user_settings)
            logger.info(f"Loaded and merged general configurations from {user_config_path}")
        except Exception as e:
            logger.error(f"Error loading {user_config_path}: {e}. Previous configurations remain.", exc_info=True)
    else:
        logger.info(f"{user_config_path} not found. No user general overrides applied.")

load_configuration()

# --- Command Category Mapping (Constants are now imported from category_manager) ---
# CATEGORY_MAP and CATEGORY_DESCRIPTIONS are now CM_CATEGORY_MAP and CM_CATEGORY_DESCRIPTIONS from category_manager

# --- Global Variables ---
output_buffer = []
output_field = None
input_field = None
key_help_field = None
app_instance = None # Renamed 'app' to 'app_instance' to avoid conflict if 'app' is imported
auto_scroll = True
current_directory = os.getcwd()
categorization_flow_active = False
categorization_flow_state = {}
# _CURRENTLY_LOADED_CATEGORIES is now managed by category_manager

# --- Keybindings ---
kb = KeyBindings()
@kb.add('c-c')
@kb.add('c-d')
def _handle_exit_or_cancel(event):
    global categorization_flow_active, categorization_flow_state
    if categorization_flow_active:
        append_output("\n⚠️ Categorization cancelled by user.", style_class='warning')
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
    if not categorization_flow_active:
        event.current_buffer.insert_text('\n')

@kb.add('enter')
def _handle_enter(event):
    buff = event.current_buffer
    buff.validate_and_handle()

@kb.add('tab')
def _handle_tab(event):
    buff = event.current_buffer
    if buff.complete_state:
        event.app.current_buffer.complete_next() # Use event.app consistently
    else:
        event.current_buffer.insert_text('    ')

@kb.add('pageup')
def _handle_pageup(event):
    if output_field and output_field.window.render_info:
        output_field.window._scroll_up()
        event.app.invalidate()

@kb.add('pagedown')
def _handle_pagedown(event):
    if output_field and output_field.window.render_info:
        output_field.window._scroll_down()
        event.app.invalidate()

@kb.add('c-up')
def _handle_ctrl_up(event):
    if not categorization_flow_active:
        event.current_buffer.cursor_up(count=1)

@kb.add('c-down')
def _handle_ctrl_down(event):
    if not categorization_flow_active:
        event.current_buffer.cursor_down(count=1)

@kb.add('up')
def _handle_up_arrow(event):
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
def append_output(text: str, style_class: str = 'default'):
    global output_buffer, output_field, auto_scroll
    if not text.endswith('\n'):
        text += '\n'
    
    output_buffer.append((style_class, text)) # Keep storing styled tuples if needed elsewhere
    
    if output_field:
        plain_text_output = "".join([content for _, content in output_buffer]) # Reconstruct for TextArea
        
        buffer = output_field.buffer
        current_cursor_pos = buffer.cursor_position
        
        buffer.set_document(Document(plain_text_output, cursor_position=len(plain_text_output)), bypass_readonly=True)

        if auto_scroll or categorization_flow_active:
            buffer.cursor_position = len(plain_text_output)
        else:
            buffer.cursor_position = min(current_cursor_pos, len(plain_text_output))
            
        current_app = get_app() # Use the imported get_app
        if current_app.is_running:
            current_app.invalidate()
        else:
            logger.debug(f"Output appended while app not running: {text.strip()}")

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

# --- AI Command Validation and Translation are now in ai_handler.py ---

# --- Update Command Helper ---
def get_file_hash(filepath):
    if not os.path.exists(filepath): return None
    hasher = hashlib.sha256();
    with open(filepath, 'rb') as f: hasher.update(f.read())
    return hasher.hexdigest()

async def handle_update_command():
    append_output("🔄 Checking for updates...", style_class='info')
    logger.info("Update command received.")
    current_app = get_app()
    if current_app.is_running: current_app.invalidate()
    if not shutil.which("git"): append_output("❌ Update failed: 'git' not found.", style_class='error'); logger.error("Update failed: git not found."); return
    original_req_hash = get_file_hash(REQUIREMENTS_FILE_PATH); requirements_changed = False
    try:
        branch_process = await asyncio.to_thread(subprocess.run, ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=SCRIPT_DIR, capture_output=True, text=True, check=True)
        current_branch = branch_process.stdout.strip()
        append_output(f"ℹ️ On branch: '{current_branch}'. Fetching updates...", style_class='info'); logger.info(f"Current git branch: {current_branch}")
        if current_app.is_running: current_app.invalidate()
        pull_process = await asyncio.to_thread(subprocess.run, ['git', 'pull', 'origin', current_branch], cwd=SCRIPT_DIR, capture_output=True, text=True)
        if pull_process.returncode == 0:
            append_output(f"✅ Git pull successful.\nOutput:\n{pull_process.stdout.strip()}", style_class='success'); logger.info(f"Git pull output: {pull_process.stdout.strip()}")
            if "Already up to date." in pull_process.stdout: append_output("✅ micro_X is up to date.", style_class='success')
            else:
                append_output("✅ Updates downloaded.", style_class='success')
                if original_req_hash != get_file_hash(REQUIREMENTS_FILE_PATH): requirements_changed = True; append_output("⚠️ requirements.txt changed.", style_class='warning'); logger.info("requirements.txt changed.")
                append_output("💡 Restart micro_X for changes.", style_class='info')
                if requirements_changed: append_output(f"💡 After restart, update dependencies:\n    cd \"{SCRIPT_DIR}\"\n    source .venv/bin/activate\n    pip install -r {REQUIREMENTS_FILENAME}", style_class='info')
        else: append_output(f"❌ Git pull failed.\nError:\n{pull_process.stderr.strip()}", style_class='error'); logger.error(f"Git pull failed. Stderr: {pull_process.stderr.strip()}")
    except subprocess.CalledProcessError as e: append_output(f"❌ Update failed: git error.\n{e.stderr}", style_class='error'); logger.error(f"Update git error: {e}", exc_info=True)
    except FileNotFoundError: append_output("❌ Update failed: 'git' not found.", style_class='error'); logger.error("Update failed: git not found.")
    except Exception as e: append_output(f"❌ Unexpected error during update: {e}", style_class='error'); logger.error(f"Unexpected update error: {e}", exc_info=True)
    finally:
        if current_app.is_running: current_app.invalidate()

# --- Utils Command Helper ---
async def handle_utils_command_async(full_command_str: str):
    logger.info(f"Handling /utils command: {full_command_str}")
    append_output(f"🛠️ Processing /utils command...", style_class='info')
    current_app = get_app()
    if current_app.is_running: current_app.invalidate()

    try:
        parts = shlex.split(full_command_str)
    except ValueError as e:
        append_output(f"❌ Error parsing /utils command: {e}", style_class='error')
        logger.warning(f"shlex error for /utils '{full_command_str}': {e}")
        if current_app.is_running: current_app.invalidate()
        return

    utils_help_message = "ℹ️ Usage: /utils <script_name_no_ext> [args...] | list | help"

    if len(parts) < 2:
        append_output(utils_help_message, style_class='info')
        logger.debug("Insufficient arguments for /utils command.")
        if current_app.is_running: current_app.invalidate()
        return

    subcommand_or_script_name = parts[1]
    args = parts[2:]
    
    if subcommand_or_script_name.lower() in ["list", "help"]:
        try:
            if not os.path.exists(UTILS_DIR_PATH) or not os.path.isdir(UTILS_DIR_PATH):
                append_output(f"❌ Utility directory '{UTILS_DIR_NAME}' not found at '{UTILS_DIR_PATH}'.", style_class='error')
                logger.error(f"Utility directory not found: {UTILS_DIR_PATH}")
                if current_app.is_running: current_app.invalidate()
                return

            available_scripts = [
                f[:-3] for f in os.listdir(UTILS_DIR_PATH) 
                if os.path.isfile(os.path.join(UTILS_DIR_PATH, f)) and f.endswith(".py") and f != "__init__.py"
            ]
            if available_scripts:
                append_output("Available utility scripts (run with /utils <script_name>):", style_class='info')
                for script_name in sorted(available_scripts):
                    append_output(f"  - {script_name}", style_class='info')
            else:
                append_output(f"No executable Python utility scripts found in '{UTILS_DIR_NAME}'.", style_class='info')
            logger.info(f"Listed utils scripts: {available_scripts}")
        except Exception as e:
            append_output(f"❌ Error listing utility scripts: {e}", style_class='error')
            logger.error(f"Error listing utility scripts: {e}", exc_info=True)
        finally:
            if current_app.is_running: current_app.invalidate()
        return

    script_filename = f"{subcommand_or_script_name}.py"
    script_path = os.path.join(UTILS_DIR_PATH, script_filename) 

    if not os.path.isfile(script_path):
        append_output(f"❌ Utility script not found: {script_filename} in '{UTILS_DIR_NAME}' directory.", style_class='error')
        logger.warning(f"Utility script not found: {script_path}")
        append_output(utils_help_message, style_class='info') 
        if current_app.is_running: current_app.invalidate()
        return

    command_to_execute_list = [sys.executable, script_path] + args
    command_str_for_display = f"{sys.executable} {script_path} {' '.join(args)}"

    append_output(f"🚀 Executing utility: {command_str_for_display}\n    (Working directory: {SCRIPT_DIR})", style_class='info')
    logger.info(f"Executing utility script: {command_to_execute_list} with cwd={SCRIPT_DIR}")
    if current_app.is_running: current_app.invalidate()

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
            append_output(f"{output_prefix}{process.stdout.strip()}")
            has_output = True
        if process.stderr:
            append_output(f"Stderr from '{script_filename}':\n{process.stderr.strip()}", style_class='warning')
            has_output = True
        
        if not has_output and process.returncode == 0:
            append_output(f"{output_prefix}(No output)", style_class='info')

        if process.returncode != 0:
            append_output(f"⚠️ Utility '{script_filename}' exited with code {process.returncode}.", style_class='warning')
            logger.warning(f"Utility script '{script_path}' exited with code {process.returncode}. Args: {args}")
        else:
            if not process.stderr: 
                append_output(f"✅ Utility '{script_filename}' completed.", style_class='success')
            logger.info(f"Utility script '{script_path}' completed with code {process.returncode}. Args: {args}")

    except FileNotFoundError:  
        append_output(f"❌ Error: Python interpreter ('{sys.executable}') or script ('{script_filename}') not found.", style_class='error')
        logger.error(f"FileNotFoundError executing utility: {command_to_execute_list}", exc_info=True)
    except Exception as e:
        append_output(f"❌ Unexpected error executing utility '{script_filename}': {e}", style_class='error')
        logger.error(f"Error executing utility script '{script_path}': {e}", exc_info=True)
    finally:
        if current_app.is_running: current_app.invalidate()

# --- General Help Function ---
def display_general_help():
    help_text_styled = [
        ('class:help-title', "micro_X AI-Enhanced Shell - Help\n\n"),
        ('class:help-text', "Welcome to micro_X! An intelligent shell that blends traditional command execution with AI capabilities.\n"),
        ('class:help-header', "\nAvailable Commands:\n"),
        ('class:help-command', "  /ai <query>             "), ('class:help-description', "- Translate natural language <query> into a Linux command.\n"),
        ('class:help-example', "                          Example: /ai list all text files in current folder\n"),
        ('class:help-command', "  /command <subcommand>   "), ('class:help-description', "- Manage command categorizations (simple, semi_interactive, interactive_tui).\n"),
        ('class:help-example', "                          Type '/command help' for detailed options.\n"),
        ('class:help-command', "  /utils <script> [args]  "), ('class:help-description', "- Run a utility script from the 'utils' directory.\n"),
        ('class:help-example', "                          Type '/utils list' or '/utils help' for available scripts.\n"),
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
    global current_directory, categorization_flow_active
    if categorization_flow_active: logger.warning("Input ignored: categorization active."); return
    user_input_stripped = user_input.strip(); logger.info(f"Received input: '{user_input_stripped}'")
    if not user_input_stripped: return

    current_app = get_app() # Get app instance for UI updates

    if user_input_stripped.lower() in {"/help", "help"}:
        display_general_help()
        return

    if user_input_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:
        append_output("Exiting micro_X Shell 🚪", style_class='info'); logger.info("Exit command received.") 
        if current_app.is_running: current_app.exit(); return
    
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
        if current_app.is_running: current_app.invalidate()
        # Use the new ai_handler functions, passing necessary parameters
        linux_command, ai_raw_candidate = await get_validated_ai_command(human_query, config, append_output, get_app)
        if linux_command:
            append_output(f"🤖 AI Suggests (validated): {linux_command}", style_class='ai-response') 
            await process_command(linux_command, f"/ai {human_query} -> {linux_command}", ai_raw_candidate, None)
        else: append_output("🤔 AI could not produce a validated command.", style_class='warning') 
        return
    
    if user_input_stripped.startswith("/command"):  
        # handle_command_subsystem_input now returns a dict if it's a 'run' command
        command_action = handle_command_subsystem_input(user_input_stripped) 
        if isinstance(command_action, dict) and command_action.get('action') == 'force_run':
            cmd_to_run = command_action['command']
            forced_cat = command_action['category']
            display_input = f"/command run {forced_cat} \"{cmd_to_run}\""
            append_output(f"⚡ Forcing execution of '{cmd_to_run}' as '{forced_cat}'...", style_class='info')
            await process_command(cmd_to_run, display_input, None, None, forced_category=forced_cat)
        # If not a 'force_run' dict, it means it was handled internally by category_manager (e.g., list, help)
        # or an error was printed by it, so no further action here.
        return
    
    # Use classify_command from category_manager
    category = classify_command(user_input_stripped) 
    if category != UNKNOWN_CATEGORY_SENTINEL: # UNKNOWN_CATEGORY_SENTINEL from category_manager
        logger.debug(f"Direct input '{user_input_stripped}' is known: '{category}'.")
        await process_command(user_input_stripped, user_input_stripped, None, None)
    else: # Unknown command, try AI validation then translation
        logger.debug(f"Direct input '{user_input_stripped}' unknown. Validating with AI.")
        append_output(f"🔎 Validating '{user_input_stripped}' with AI...", style_class='info'); 
        if current_app.is_running: current_app.invalidate()
        
        # Use the new ai_handler function
        is_cmd_ai_says = await is_valid_linux_command_according_to_ai(user_input_stripped, config)
        
        # Heuristics (same as before)
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
        else: # AI says not a command, or heuristic overrides, or AI inconclusive -> try translation
            log_msg = ""; ui_msg = ""; ui_style = 'ai-thinking' 
            if is_cmd_ai_says is False: log_msg = f"Validator AI suggests '{user_input_stripped}' not command."; ui_msg = f"💬 AI suggests '{user_input_stripped}' not direct command. Trying as NL query..."
            elif is_cmd_ai_says is True and user_input_looks_like_phrase: log_msg = f"Validator AI confirmed '{user_input_stripped}' as command, but heuristic overrides."; ui_msg = f"💬 AI validated '{user_input_stripped}' as command, but looks like phrase. Trying as NL query..."
            else: log_msg = f"Validator AI for '{user_input_stripped}' inconclusive."; ui_msg = f"⚠️ AI validation for '{user_input_stripped}' inconclusive. Trying as NL query..."; ui_style = 'warning' 
            logger.info(f"{log_msg} Treating as natural language."); append_output(ui_msg, style_class=ui_style)
            if current_app.is_running: current_app.invalidate()
            
            # Use the new ai_handler function
            linux_command, ai_raw_candidate = await get_validated_ai_command(user_input_stripped, config, append_output, get_app)
            if linux_command:
                append_output(f"🤖 AI Translated & Validated to: {linux_command}", style_class='ai-response') 
                original_direct_for_prompt = user_input_stripped if linux_command != user_input_stripped else None
                await process_command(linux_command, f"'{user_input_stripped}' -> {linux_command}", ai_raw_candidate, original_direct_for_prompt)
            else: # Translation failed
                append_output(f"🤔 AI could not produce validated command for '{user_input_stripped}'. Trying original as direct command.", style_class='warning') 
                logger.info(f"Validated AI translation failed for '{user_input_stripped}'. Categorizing original input.")
                await process_command(user_input_stripped, user_input_stripped, ai_raw_candidate, None) # Pass original and raw candidate

# --- process_command and categorization flow ---
async def process_command(command_str_original: str, original_user_input_for_display: str,
                          ai_raw_candidate: str | None = None,
                          original_direct_input_if_different: str | None = None,
                          forced_category: str | None = None): # New parameter
    global current_directory
    current_app = get_app() # Get app instance

    if not forced_category and command_str_original.strip().startswith("cd "): # cd is not force-runnable this way
        handle_cd_command(command_str_original)
        return
    
    category = forced_category # Use forced_category if provided
    command_for_classification = command_str_original
    command_to_be_added_if_new = command_for_classification 
    
    if not category: # If not forced, proceed with normal classification/categorization
        # Use classify_command from category_manager
        category = classify_command(command_for_classification) 
        
        if category == UNKNOWN_CATEGORY_SENTINEL: # UNKNOWN_CATEGORY_SENTINEL from category_manager
            logger.info(f"Command '{command_for_classification}' uncategorized. Starting interactive flow.")
            categorization_result = await prompt_for_categorization(command_for_classification, ai_raw_candidate, original_direct_input_if_different)
            
            if categorization_result.get('action') == 'cancel_execution':
                append_output(f"Execution of '{command_for_classification}' cancelled.", style_class='info'); logger.info(f"Execution of '{command_for_classification}' cancelled."); return 
            elif categorization_result.get('action') == 'categorize_and_execute':
                command_to_be_added_if_new = categorization_result['command'] 
                chosen_cat_for_json = categorization_result['category']
                # Use add_command_to_category from category_manager (aliased as cm_add_command_to_category)
                cm_add_command_to_category(command_to_be_added_if_new, chosen_cat_for_json) 
                category = chosen_cat_for_json 
                logger.info(f"Command '{command_to_be_added_if_new}' categorized as '{category}'.")
                if command_to_be_added_if_new != command_str_original: 
                    logger.info(f"Using '{command_to_be_added_if_new}' for execution, overriding '{command_str_original}'.")
                    command_str_original = command_to_be_added_if_new 
            else: # Default action if flow doesn't return specific action (e.g. 'execute_as_default')
                category = config['behavior']['default_category_for_unclassified']
                append_output(f"Executing '{command_for_classification}' as default '{category}'.", style_class='info'); logger.info(f"Command '{command_for_classification}' executed with default category '{category}'.") 
    
    command_to_execute_expanded = expand_shell_variables(command_str_original, current_directory)
    if command_str_original != command_to_execute_expanded:
        logger.info(f"Expanded command: '{command_to_execute_expanded}' (original: '{command_str_original}')")
        # Only show expansion if it's different from what was classified or added
        if command_to_execute_expanded != command_for_classification and command_to_execute_expanded != command_to_be_added_if_new:
               append_output(f"Expanded for execution: {command_to_execute_expanded}", style_class='info') 
    
    command_to_execute_sanitized = sanitize_and_validate(command_to_execute_expanded, original_user_input_for_display)
    if not command_to_execute_sanitized:
        append_output(f"Command '{command_to_execute_expanded}' blocked by sanitization.", style_class='security-warning'); logger.warning(f"Command '{command_to_execute_expanded}' blocked."); return 
    
    # Use CM_CATEGORY_DESCRIPTIONS from category_manager
    logger.info(f"Final command: '{command_to_execute_sanitized}', Category: '{category}'"); 
    
    exec_message_prefix = "Forced execution" if forced_category else "Executing"
    append_output(f"▶️ {exec_message_prefix} ({category} - {CM_CATEGORY_DESCRIPTIONS.get(category, 'Unknown')}): {command_to_execute_sanitized}", style_class='executing') 
    
    if category == "simple": execute_shell_command(command_to_execute_sanitized, original_user_input_for_display)
    else: execute_command_in_tmux(command_to_execute_sanitized, original_user_input_for_display, category)

async def prompt_for_categorization(command_initially_proposed: str, ai_raw_candidate_for_suggestions: str | None, original_direct_input_if_different: str | None) -> dict:
    global categorization_flow_active, categorization_flow_state, input_field
    categorization_flow_active = True; categorization_flow_state = {'command_initially_proposed': command_initially_proposed, 'ai_raw_candidate': ai_raw_candidate_for_suggestions,'original_direct_input': original_direct_input_if_different, 'command_to_add_final': command_initially_proposed, 'step': 0.5}
    flow_completion_future = asyncio.Future(); categorization_flow_state['future'] = flow_completion_future
    if input_field: input_field.multiline = False 
    _ask_step_0_5_confirm_command_base() # Initial call to start the flow
    try: return await flow_completion_future
    finally: restore_normal_input_handler(); logger.debug("Categorization flow ended.")

def _ask_step_0_5_confirm_command_base():
    global categorization_flow_state; proposed = categorization_flow_state['command_initially_proposed']; original = categorization_flow_state['original_direct_input']
    current_app = get_app()
    if original and original.strip() != proposed.strip():
        append_output(f"\nSystem processed to: '{proposed}'\nOriginal input was: '{original}'", style_class='categorize-info') 
        append_output(f"Which version to categorize?\n  1: Processed ('{proposed}')\n  2: Original ('{original}')\n  3: Modify/Enter new command\n  4: Cancel categorization", style_class='categorize-prompt') 
        if input_field: input_field.prompt = "[Categorize] Choice (1-4): "; input_field.buffer.accept_handler = _handle_step_0_5_response; current_app.invalidate()
    else: # No difference or no original, proceed to categorize the proposed command
        categorization_flow_state['command_to_add_final'] = proposed; categorization_flow_state['step'] = 1; _ask_step_1_main_action()

def _handle_step_0_5_response(buff):
    global categorization_flow_state; response = buff.text.strip(); proposed = categorization_flow_state['command_initially_proposed']; original = categorization_flow_state['original_direct_input']
    current_app = get_app()
    if response == '1': categorization_flow_state['command_to_add_final'] = proposed; append_output(f"Using processed: '{proposed}'", style_class='categorize-info'); categorization_flow_state['step'] = 1; _ask_step_1_main_action() 
    elif response == '2' and original: categorization_flow_state['command_to_add_final'] = original; append_output(f"Using original: '{original}'", style_class='categorize-info'); categorization_flow_state['step'] = 1; _ask_step_1_main_action() 
    elif response == '3': categorization_flow_state['step'] = 3.5; _ask_step_3_5_enter_custom_command_for_categorization()
    elif response == '4': categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else: append_output("Invalid choice (1-4). Please try again.", style_class='error'); _ask_step_0_5_confirm_command_base(); return 
    if response in ['1', '2', '3', '4'] and input_field: input_field.buffer.reset()

def _ask_step_1_main_action():
    global categorization_flow_state, input_field; cmd_display = categorization_flow_state['command_to_add_final']; default_cat_name = config['behavior']['default_category_for_unclassified']
    current_app = get_app()
    append_output(f"\nCommand to categorize: '{cmd_display}'", style_class='categorize-info') 
    # Use CM_CATEGORY_DESCRIPTIONS
    append_output(f"How to categorize this command?\n"
                  f"  1: simple            ({CM_CATEGORY_DESCRIPTIONS['simple']})\n" 
                  f"  2: semi_interactive    ({CM_CATEGORY_DESCRIPTIONS['semi_interactive']})\n" 
                  f"  3: interactive_tui     ({CM_CATEGORY_DESCRIPTIONS['interactive_tui']})\n" 
                  f"  M: Modify command before categorizing\n"
                  f"  D: Execute as default '{default_cat_name}' (once, no save)\n"
                  f"  C: Cancel categorization & execution", style_class='categorize-prompt') 
    if input_field: input_field.prompt = "[Categorize] Action (1-3/M/D/C): "; input_field.buffer.accept_handler = _handle_step_1_main_action_response; current_app.invalidate()

def _handle_step_1_main_action_response(buff):
    global categorization_flow_state; response = buff.text.strip().lower(); cmd_to_add = categorization_flow_state['command_to_add_final']
    # Use CM_CATEGORY_MAP
    if response in ['1', '2', '3']: chosen_category = CM_CATEGORY_MAP.get(response); categorization_flow_state.get('future').set_result({'action': 'categorize_and_execute', 'command': cmd_to_add, 'category': chosen_category})
    elif response == 'm': categorization_flow_state['step'] = 4; _ask_step_4_enter_modified_command(base_command=cmd_to_add)
    elif response == 'd': categorization_flow_state.get('future').set_result({'action': 'execute_as_default'})
    elif response == 'c': categorization_flow_state.get('future').set_result({'action': 'cancel_execution'})
    else: append_output("Invalid choice. Please enter 1-3, M, D, or C.", style_class='error'); _ask_step_1_main_action(); return 
    if response in ['1', '2', '3', 'm', 'd', 'c'] and input_field: input_field.buffer.reset()

def _ask_step_3_5_enter_custom_command_for_categorization():
    global categorization_flow_state, input_field; append_output("\nEnter the new command string you want to categorize:", style_class='categorize-prompt') 
    current_app = get_app()
    if input_field: input_field.prompt = "[Categorize] New command: "; input_field.buffer.text = ""; input_field.buffer.accept_handler = _handle_step_3_5_response; current_app.invalidate()

def _handle_step_3_5_response(buff):
    global categorization_flow_state; custom_command = buff.text.strip()
    if not custom_command: append_output("⚠️ Command cannot be empty. Please enter a command or Ctrl+C to cancel.", style_class='warning'); _ask_step_3_5_enter_custom_command_for_categorization(); return 
    categorization_flow_state['command_to_add_final'] = custom_command; append_output(f"New command for categorization: '{custom_command}'", style_class='categorize-info'); categorization_flow_state['step'] = 1; _ask_step_1_main_action() 
    if input_field: input_field.buffer.reset()

def _ask_step_4_enter_modified_command(base_command: str):
    global categorization_flow_state, input_field; append_output(f"\nCurrent command: '{base_command}'\nEnter your modified command below:", style_class='categorize-prompt') 
    current_app = get_app()
    if input_field: input_field.prompt = f"[Categorize] Modified Cmd: "; input_field.buffer.text = base_command; input_field.buffer.cursor_position = len(base_command); input_field.buffer.accept_handler = _handle_step_4_modified_command_response; current_app.invalidate()

def _handle_step_4_modified_command_response(buff):
    global categorization_flow_state; modified_command = buff.text.strip()
    if not modified_command: append_output("⚠️ Modified command empty. Using previous command for categorization.", style_class='warning') 
    else: categorization_flow_state['command_to_add_final'] = modified_command
    categorization_flow_state['step'] = 4.5; _ask_step_4_5_category_for_modified()

def _ask_step_4_5_category_for_modified():
    global categorization_flow_state, input_field; cmd_to_categorize = categorization_flow_state['command_to_add_final']
    current_app = get_app()
    append_output(f"\nCategory for command: '{cmd_to_categorize}'", style_class='categorize-info') 
    # Use CM_CATEGORY_DESCRIPTIONS
    append_output(f"  1: simple            ({CM_CATEGORY_DESCRIPTIONS['simple']})\n" 
                  f"  2: semi_interactive    ({CM_CATEGORY_DESCRIPTIONS['semi_interactive']})\n" 
                  f"  3: interactive_tui     ({CM_CATEGORY_DESCRIPTIONS['interactive_tui']})", style_class='categorize-prompt') 
    if input_field: input_field.prompt = "[Categorize] Category (1-3): "; input_field.buffer.reset(); input_field.buffer.accept_handler = _handle_step_4_5_response; current_app.invalidate()

def _handle_step_4_5_response(buff):
    global categorization_flow_state; response = buff.text.strip()
    # Use CM_CATEGORY_MAP
    chosen_category = CM_CATEGORY_MAP.get(response)
    if chosen_category: categorization_flow_state.get('future').set_result({'action': 'categorize_and_execute', 'command': categorization_flow_state['command_to_add_final'], 'category': chosen_category})
    else: append_output("Invalid category. Please enter 1, 2, or 3.", style_class='error'); _ask_step_4_5_category_for_modified() 
    if input_field: input_field.buffer.reset() 

# --- Built-in Command Handlers ---
def handle_cd_command(full_cd_command: str):
    global current_directory, input_field
    current_app = get_app()
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
                if current_app.is_running: current_app.invalidate()
            append_output(f"📂 Changed directory to: {current_directory}", style_class='info'); logger.info(f"Directory changed to: {current_directory}") 
        else: append_output(f"❌ Error: Directory '{target_dir_str}' (resolved to '{new_dir_abs}') does not exist.", style_class='error'); logger.warning(f"Failed cd to '{new_dir_abs}'.") 
    except Exception as e: append_output(f"❌ Error processing 'cd' command: {e}", style_class='error'); logger.exception(f"Error in handle_cd_command for '{full_cd_command}'") 

# --- Command Execution ---
def sanitize_and_validate(command: str, original_input_for_log: str) -> str | None:
    dangerous_patterns = [r'\brm\s+(-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\S*', r'\bmkfs\b', r'\bdd\b\s+if=/dev/random', r'\bdd\b\s+if=/dev/zero', r'\b(shutdown|reboot|halt|poweroff)\b', r'>\s*/dev/sd[a-z]+', r':\(\)\{:\|:&};:', r'\b(wget|curl)\s+.*\s*\|\s*(sh|bash|python|perl)\b']
    for pattern in dangerous_patterns:
        if re.search(pattern, command): logger.warning(f"DANGEROUS command blocked ('{pattern}'): '{command}' (from '{original_input_for_log}')"); append_output(f"🛡️ Command blocked for security: {command}", style_class='security-critical'); return None 
    return command

def execute_command_in_tmux(command_to_execute: str, original_user_input_display: str, category: str):
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

            tmux_cmd_list_launch = ["tmux", "new-window", "-n", window_name, wrapped_command]
            logger.info(f"Executing semi_interactive tmux (non-detached): {tmux_cmd_list_launch} (log: {log_path})")

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
                
                # Removed the 'pass' here as it's not strictly needed for the logic flow
                # if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                #     pass

            if not window_closed_or_cmd_done: append_output(f"⚠️ Tmux window '{window_name}' poll timed out. Output might be incomplete or command still running.", style_class='warning'); logger.warning(f"Tmux poll for '{window_name}' timed out.")

            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        output_content = f.read().strip()

                    # *** MODIFIED SECTION START ***
                    # Get TUI detection thresholds from config, with defaults
                    # These keys would ideally be added to default_config.json
                    tui_line_threshold = config.get('behavior', {}).get('tui_detection_line_threshold_pct', 30.0)
                    tui_char_threshold = config.get('behavior', {}).get('tui_detection_char_threshold_pct', 3.0)

                    if output_content and is_tui_like_output(output_content, tui_line_threshold, tui_char_threshold):
                        logger.info(f"Output from '{original_user_input_display}' determined to be TUI-like. Not displaying raw content.")
                        suggestion_command = f'/command move "{command_to_execute}" interactive_tui' # Use the command that was actually executed
                        append_output(
                            f"Output from '{original_user_input_display}':\n"
                            f"[Semi-interactive session output appears TUI-specific and was not displayed directly.]\n"
                            f"💡 Tip: This command might work better if categorized as 'interactive_tui'.\n"
                            f"    You can try: {suggestion_command}",
                            style_class='info'
                        )                       
                        output_captured = True # Mark as captured, even if not displayed raw
                    elif output_content: # If not TUI-like and has content
                        append_output(f"Output from '{original_user_input_display}':\n{output_content}")
                        output_captured = True
                    elif window_closed_or_cmd_done: # No output, but window closed/command done
                        append_output(f"Output from '{original_user_input_display}': (No output captured)", style_class='info')
                        output_captured = True
                    # *** MODIFIED SECTION END ***

                except Exception as e:
                    logger.error(f"Error reading or analyzing tmux log {log_path}: {e}", exc_info=True)
                    append_output(f"❌ Error reading or analyzing tmux log: {e}", style_class='error')
                finally:
                    try:
                        os.remove(log_path)
                    except OSError as e_del:
                        logger.error(f"Error deleting tmux log {log_path}: {e_del}")
            elif window_closed_or_cmd_done: # Log file didn't exist, but window closed
                append_output(f"Output from '{original_user_input_display}': (Tmux window closed, no log found)", style_class='info')

            if not output_captured and not window_closed_or_cmd_done:
                append_output(f"Output from '{original_user_input_display}': (Tmux window may still be running or timed out without output)", style_class='warning')

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

# --- Command Categorization Subsystem (Now handled by category_manager.py) ---
# Functions like _load_single_category_file, load_and_merge_command_categories,
# classify_command (the old one), _save_user_command_categories, add_command_to_category (the old one),
# remove_command_from_category, list_categorized_commands, move_command_category,
# and handle_command_subsystem_input (the old one) have been removed.
# Their functionality is now accessed via the category_manager module.

# --- Main Application Setup and Run ---
def run_shell():
    global output_field, input_field, key_help_field, app_instance, auto_scroll, current_directory

    # Initialize the category manager (this also loads categories)
    init_category_manager(SCRIPT_DIR, CONFIG_DIR, append_output)
    # The old load_and_merge_command_categories() call is no longer needed here.
    
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
    output_buffer = [('class:welcome', initial_welcome_message)]

    output_field = TextArea(
        text="".join([content for _, content in output_buffer]),
        style='class:output-field', 
        scrollbar=True, 
        focusable=False, 
        wrap_lines=True, 
        read_only=True
    )

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
    
    app_instance = Application(layout=layout, key_bindings=kb, style=final_style, full_screen=True, mouse_support=True)
    
    logger.info("micro_X Shell application starting.")
    try: app_instance.run()
    except (EOFError, KeyboardInterrupt): print("\nExiting micro_X Shell. 👋"); logger.info("Exiting due to EOF or KeyboardInterrupt at app level.")
    except Exception as e: print(f"\nUnexpected critical error: {e}"); logger.critical("Critical error during app_instance.run()", exc_info=True)
    finally: logger.info("micro_X Shell application stopped.")

if __name__ == "__main__":
    run_shell()
