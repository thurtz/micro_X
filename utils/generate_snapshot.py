# utils/generate_snapshot.py

import os
import datetime
import subprocess # For running other utility scripts
import sys # For using sys.executable
import argparse # For command-line arguments
import re # For log parsing

# --- Configuration ---
# Files and directories to include in the snapshot.
# Paths are relative to the project root (where this script's parent directory is).
FILES_TO_INCLUDE = [
    # --- Project Root Files ---
    "main.py",
    ".gitignore",
    "LICENSE",
    "README.md",
    "micro_X-A_Technical_Whitepaper.md",
    "micro_X.sh",
    "micro_X.desktop",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.sh",

    # --- Generated Artifacts ---
    "project_tree.txt",
    "pytest_results/pytest_results.txt",

    # --- Config Files ---
    "config/default_config.json",
    "config/user_config.json",
    "config/default_command_categories.json",
    "config/user_command_categories.json",
    "config/default_aliases.json",
    "config/user_aliases.json",
    "config/.tmux.conf"

    # --- Documentation ---
    "docs/developer/development_principles.md",
    "docs/developer/generate_snapshot.md",
    "docs/developer/generate_tree.md",
    "docs/developer/micro_X_Code_Quality_Review.md",
    "docs/developer/micro_X_Code_Quality_Review_Accomplishments.md",
    "docs/developer/micro_X_testing_guide.md",
    "docs/developer/review_of_micro_X_project.md",

    "docs/user_guide/01_installation.md",
    "docs/user_guide/02_basic_usage.md",
    "docs/user_guide/03_ai_features.md",
    "docs/user_guide/04_command_categorization.md",
    "docs/user_guide/05_management_and_utils.md",
    "docs/user_guide/06_developer_mode.md",
    "docs/user_guide/07_advanced_topics.md",
    "docs/user_guide/08_troubleshooting.md",
    "docs/user_guide/index.md",

    # --- Core Application Modules ---
    "modules/ai_handler.py",
    "modules/category_manager.py",
    "modules/config_handler.py",
    "modules/curses_ui_manager.py",
    "modules/git_context_manager.py",
    "modules/ollama_manager.py",
    "modules/output_analyzer.py",
    "modules/shell_engine.py",
    "modules/ui_manager.py",

    # --- Setup Scripts ---
    "setup_scripts/setup_micro_X_mac.sh",
    "setup_scripts/setup_micro_X_mint.sh",
    "setup_scripts/setup_micro_X_termux.sh",
    "setup_scripts/setup_micro_X_wsl.sh",

    # --- Test Suite ---
    "tests/conftest.py",
    "tests/test_ai_handler.py",
    "tests/test_category_manager.py",
    "tests/test_config_handler.py",
    "tests/test_git_context_manager.py",
    "tests/test_main_startup.py",
    "tests/test_shell_engine.py",
    "tests/test_ui_manager.py",
    "tests/tests.md",

    # --- Tools ---
    "tools/config_manager/index.html",

    # --- Utility Scripts ---
    "utils/alias.py",
    "utils/command.py",
    "utils/config_manager.py",
    "utils/dev.py",
    "utils/generate_snapshot.py", # Include self
    "utils/generate_tree.py",
    "utils/help.py",
    "utils/install_requirements.py",
    "utils/list_scripts.py",
    "utils/ollama_cli.py",
    "utils/run_tests.py",
    "utils/setup_brew.py",
    "utils/setup_dev_env.py",
    "utils/update.py",
]

# List of module files that can be summarized to their API documentation.
# This list is used when the --summarize flag is active.
MODULE_FILES_TO_SUMMARIZE = [
    "modules/ai_handler.py",
    "modules/category_manager.py",
    "modules/output_analyzer.py",
    "modules/ollama_manager.py",
    "modules/shell_engine.py",
    "modules/ui_manager.py",
    "modules/git_context_manager.py",
]

# Output directory and filename for the snapshot
SNAPSHOT_DIRECTORY = "snapshots"
SNAPSHOT_FILENAME_TEMPLATE = "micro_x_context_snapshot_{timestamp}.txt"

# Log file details (relative to project root)
LOG_DIR_NAME = "logs"
LOG_FILE_BASENAME = "micro_x.log"

# Log message content markers (these are the exact strings logged by logger.info(), AFTER stripping)
LOG_SEPARATOR_LINE_TEXT = "=" * 80 # Adjusted to match main.py's actual log output (was 68)
LOG_SESSION_START_TEXT = "micro_X Session Started" 
LOG_SESSION_END_TEXT = "micro_X Session Ended"   
LOG_TIMESTAMP_PREFIX_TEXT = "Timestamp:" 

# Regex to extract the message part from a log line
LOG_MESSAGE_CAPTURE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\s*-\s*"
    r"(?:INFO|DEBUG|WARNING|ERROR|CRITICAL)\s*-\s*"
    r"[\w\.<>-]+:\d+\s*-\s*(.*)$"
)

# API Documentation markers
API_DOC_START_MARKER = "# --- API DOCUMENTATION for"
API_DOC_END_MARKER = "# --- END API DOCUMENTATION ---"

# --- Helper Functions ---
def get_project_root():
    """Determines the project root directory."""
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(utils_dir)
    if os.path.exists(os.path.join(project_root, "main.py")) or \
       os.path.exists(os.path.join(project_root, ".git")) or \
       os.path.isdir(os.path.join(project_root, "modules")):
        return project_root
    else:
        if os.path.exists(os.path.join(utils_dir, "main.py")) or \
           os.path.exists(os.path.join(utils_dir, ".git")) or \
           os.path.isdir(os.path.join(utils_dir, "modules")):
            print("Warning: Script might be in project root, not utils/. Assuming current dir is root.")
            return utils_dir
        print(f"Warning: Could not reliably determine project root. Using script's parent directory: {project_root}")
        return project_root

def read_file_content(filepath):
    """Reads the content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: File not found - {filepath}")
        return None
    except Exception as e:
        print(f"Warning: Error reading file {filepath} - {e}")
        return None

def extract_api_documentation(filepath: str) -> str:
    """Extracts the API documentation block from a module file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        doc_lines = []
        in_doc_block = False
        for line in lines:
            if API_DOC_START_MARKER in line:
                in_doc_block = True
            
            if in_doc_block:
                doc_lines.append(line)
            
            if API_DOC_END_MARKER in line:
                break # Stop after finding the end marker
        
        if doc_lines:
            return "".join(doc_lines)
        else:
            return f"[API Documentation block not found in {os.path.basename(filepath)}]\n"
            
    except FileNotFoundError:
        return f"[File not found: {os.path.basename(filepath)}]\n"
    except Exception as e:
        return f"[Error reading API documentation from {os.path.basename(filepath)}: {e}]\n"

def run_utility_script(script_name: str, project_root: str, utils_dir: str) -> tuple[bool, str]:
    """Runs a utility script."""
    script_path = os.path.join(utils_dir, script_name)
    if not os.path.exists(script_path):
        message = f"Utility script '{script_name}' not found at '{script_path}'. Skipping."
        print(f"Warning: {message}")
        return False, f"[NOTICE: {script_name} execution skipped - script not found.]\n"
    print(f"Attempting to run utility: {script_name}...")
    try:
        process = subprocess.run(
            [sys.executable, script_path], cwd=project_root, check=False,
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if process.stdout: print(f"--- Output from {script_name} ---\n{process.stdout.strip()}\n---------------------------")
        if process.stderr: print(f"--- Errors from {script_name} ---\n{process.stderr.strip()}\n---------------------------", file=sys.stderr)
        if process.returncode == 0:
            print(f"Success: Utility '{script_name}' executed successfully.")
            return True, ""
        elif script_name == "run_tests.py" and process.returncode == 1: # Pytest returns 1 for test failures
            print(f"Notice: Utility '{script_name}' completed. Some tests failed. Results have been updated.")
            return True, f"[NOTICE: {script_name} reported test failures. Results file updated.]\n"
        else:
            print(f"Error: Utility '{script_name}' failed with exit code {process.returncode}.\nStderr:\n{process.stderr.strip() if process.stderr else 'N/A'}")
            return False, f"[NOTICE: {script_name} execution failed (Code: {process.returncode}). Corresponding artifact may be stale or missing.]\n"
    except Exception as e:
        print(f"Error: An unexpected error occurred while trying to run '{script_name}': {e}")
        return False, f"[NOTICE: Unexpected error running {script_name}. Corresponding artifact may be stale or missing.]\n"

def _get_message_from_log_line(log_line_str: str) -> str | None:
    """Extracts the core message from a formatted log line, normalizes whitespace, and strips."""
    original_line_stripped = log_line_str.strip() 
    match = LOG_MESSAGE_CAPTURE_PATTERN.match(original_line_stripped) 
    if match:
        message_captured = match.group(1)
        message_normalized = message_captured.replace('\xa0', ' ').strip()
        return message_normalized
    return None

def _get_last_log_session(log_filepath: str) -> tuple[str, str]:
    """
    Reads the log file and attempts to extract the last session.
    Prioritizes the last *completed* session. If none, tries the current *active* session.
    Returns a tuple: (session_type: str, session_content: str)
    session_type can be "COMPLETED", "ACTIVE", or "NONE".
    If "NONE", session_content will contain debug information.
    """
    parsing_debug_log = [f"LogParser: Attempting to read log session from: {log_filepath}\n"]
    # Console print for direct script execution feedback
    print(f"LogParser: Attempting to read log session from: {log_filepath}") 
    
    if not os.path.exists(log_filepath):
        parsing_debug_log.append("[LogParser: Log file not found at specified path]\n")
        return "NONE", "".join(parsing_debug_log)
    try:
        with open(log_filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        parsing_debug_log.append(f"[LogParser: Error reading log file: {e}]\n")
        return "NONE", "".join(parsing_debug_log)
    if not lines:
        parsing_debug_log.append("[LogParser: Log file is empty]\n")
        return "NONE", "".join(parsing_debug_log)

    # Attempt 1: Find the last COMPLETED session
    session_end_block_indices = []
    parsing_debug_log.append(f"LogParser: Scanning {len(lines)} lines for session end markers...\n")
    print(f"LogParser: Scanning {len(lines)} lines for session end markers...") 
    found_end_marker_this_run = False
    for i in range(len(lines) - 3): # Need at least 4 lines for a full block
        msg0 = _get_message_from_log_line(lines[i])
        msg1 = _get_message_from_log_line(lines[i+1])
        msg2 = _get_message_from_log_line(lines[i+2])
        msg3 = _get_message_from_log_line(lines[i+3])
        
        is_potential_end_block = (msg0 == LOG_SEPARATOR_LINE_TEXT or \
                                  msg1 == LOG_SESSION_END_TEXT or \
                                  (msg2 is not None and msg2.startswith(LOG_TIMESTAMP_PREFIX_TEXT)) or \
                                  msg3 == LOG_SEPARATOR_LINE_TEXT)

        # Conditional detailed logging for snapshot
        if i < 5 or i > len(lines) - 8 or is_potential_end_block : 
            parsing_debug_log.append(f"\nLogParser END SCAN (idx {i}):\n")
            parsing_debug_log.append(f"  Raw Line 0: {repr(lines[i].strip())}\n")
            parsing_debug_log.append(f"  Msg 0: {repr(msg0)} (Expected: {repr(LOG_SEPARATOR_LINE_TEXT)}) Match: {msg0 == LOG_SEPARATOR_LINE_TEXT}\n")
            parsing_debug_log.append(f"  Raw Line 1: {repr(lines[i+1].strip())}\n")
            parsing_debug_log.append(f"  Msg 1: {repr(msg1)} (Expected: {repr(LOG_SESSION_END_TEXT)}) Match: {msg1 == LOG_SESSION_END_TEXT}\n")
            parsing_debug_log.append(f"  Raw Line 2: {repr(lines[i+2].strip())}\n")
            parsing_debug_log.append(f"  Msg 2: {repr(msg2)} (Expected prefix: {repr(LOG_TIMESTAMP_PREFIX_TEXT)}) Match: {msg2.startswith(LOG_TIMESTAMP_PREFIX_TEXT) if msg2 else False}\n")
            parsing_debug_log.append(f"  Raw Line 3: {repr(lines[i+3].strip())}\n")
            parsing_debug_log.append(f"  Msg 3: {repr(msg3)} (Expected: {repr(LOG_SEPARATOR_LINE_TEXT)}) Match: {msg3 == LOG_SEPARATOR_LINE_TEXT}\n")

        if msg0 == LOG_SEPARATOR_LINE_TEXT and \
           msg1 == LOG_SESSION_END_TEXT and \
           (msg2 is not None and msg2.startswith(LOG_TIMESTAMP_PREFIX_TEXT)) and \
           msg3 == LOG_SEPARATOR_LINE_TEXT:
            session_end_block_indices.append(i)
            parsing_debug_log.append(f"LogParser: Found potential session end block starting at line index {i}.\n")
            print(f"LogParser: Found potential session end block starting at line index {i}.") 
            found_end_marker_this_run = True


    if session_end_block_indices:
        parsing_debug_log.append(f"LogParser: Found {len(session_end_block_indices)} session end marker blocks.\n")
        print(f"LogParser: Found {len(session_end_block_indices)} session end marker blocks.") 
        last_session_end_block_start_index = session_end_block_indices[-1]
        parsing_debug_log.append(f"LogParser: Last session end block starts at index {last_session_end_block_start_index}.\n")
        print(f"LogParser: Last session end block starts at index {last_session_end_block_start_index}.") 
        last_session_start_block_start_index = -1
        parsing_debug_log.append(f"LogParser: Searching backwards for corresponding start marker before index {last_session_end_block_start_index}...\n")
        print(f"LogParser: Searching backwards for corresponding start marker before index {last_session_end_block_start_index}...") 
        for i in range(last_session_end_block_start_index - 4, -1, -1): # Search backwards from before the found end block
            if i + 3 >= len(lines): continue # Ensure we don't go out of bounds
            
            msg0_s = _get_message_from_log_line(lines[i])
            msg1_s = _get_message_from_log_line(lines[i+1])
            msg2_s = _get_message_from_log_line(lines[i+2])
            msg3_s = _get_message_from_log_line(lines[i+3])
            
            is_potential_start_block = (msg0_s == LOG_SEPARATOR_LINE_TEXT or \
                                        msg1_s == LOG_SESSION_START_TEXT or \
                                        (msg2_s is not None and msg2_s.startswith(LOG_TIMESTAMP_PREFIX_TEXT)) or \
                                        msg3_s == LOG_SEPARATOR_LINE_TEXT)

            if i > last_session_end_block_start_index - 4 - 10 or is_potential_start_block: # Log details for nearby or potential matches
                parsing_debug_log.append(f"\nLogParser START SCAN (idx {i}):\n")
                parsing_debug_log.append(f"  Msg0_s: {repr(msg0_s)} (Expected: {repr(LOG_SEPARATOR_LINE_TEXT)}) Match: {msg0_s == LOG_SEPARATOR_LINE_TEXT}\n")
                parsing_debug_log.append(f"  Msg1_s: {repr(msg1_s)} (Expected: {repr(LOG_SESSION_START_TEXT)}) Match: {msg1_s == LOG_SESSION_START_TEXT}\n")
                parsing_debug_log.append(f"  Msg2_s: {repr(msg2_s)} (Expected prefix: {repr(LOG_TIMESTAMP_PREFIX_TEXT)}) Match: {msg2_s.startswith(LOG_TIMESTAMP_PREFIX_TEXT) if msg2_s else False}\n")
                parsing_debug_log.append(f"  Msg3_s: {repr(msg3_s)} (Expected: {repr(LOG_SEPARATOR_LINE_TEXT)}) Match: {msg3_s == LOG_SEPARATOR_LINE_TEXT}\n")

            if msg0_s == LOG_SEPARATOR_LINE_TEXT and \
               msg1_s == LOG_SESSION_START_TEXT and \
               (msg2_s is not None and msg2_s.startswith(LOG_TIMESTAMP_PREFIX_TEXT)) and \
               msg3_s == LOG_SEPARATOR_LINE_TEXT:
                if i < last_session_end_block_start_index: # Ensure start is before end
                    last_session_start_block_start_index = i
                    parsing_debug_log.append(f"LogParser: Found corresponding session start block for completed session at index {i}.\n")
                    print(f"LogParser: Found corresponding session start block for completed session at index {i}.") 
                    break
        if last_session_start_block_start_index != -1:
            start_idx = last_session_start_block_start_index
            end_idx = last_session_end_block_start_index + 4 # Include the 4 lines of the end block
            parsing_debug_log.append(f"LogParser: Extracting COMPLETED session from line {start_idx} to {end_idx-1}.\n")
            print(f"LogParser: Extracting COMPLETED session from line {start_idx} to {end_idx-1}.") 
            return "COMPLETED", "".join(lines[start_idx:end_idx])
        else:
            parsing_debug_log.append("[LogParser: Found session end(s), but no corresponding start marker for the last completed one.]\n")
            print("[LogParser: Found session end(s), but no corresponding start marker for the last completed one.]") 
    elif not found_end_marker_this_run: 
        parsing_debug_log.append("[LogParser: No complete session end marker blocks found in log during scan.]\n")
        print("[LogParser: No complete session end marker blocks found in log during scan.]") 


    # Attempt 2: Find the last ACTIVE session (if no completed session was found)
    parsing_debug_log.append("LogParser: No completed session found. Looking for last active session...\n")
    print("LogParser: No completed session found. Looking for last active session...") 
    session_start_block_indices = []
    found_start_marker_this_run = False
    for i in range(len(lines) - 3): # Need at least 4 lines for a full block
        msg0 = _get_message_from_log_line(lines[i])
        msg1 = _get_message_from_log_line(lines[i+1])
        msg2 = _get_message_from_log_line(lines[i+2])
        msg3 = _get_message_from_log_line(lines[i+3])
        
        is_potential_active_start_block = (msg0 == LOG_SEPARATOR_LINE_TEXT or \
                                           msg1 == LOG_SESSION_START_TEXT or \
                                           (msg2 is not None and msg2.startswith(LOG_TIMESTAMP_PREFIX_TEXT)) or \
                                           msg3 == LOG_SEPARATOR_LINE_TEXT)
        
        if i < 5 or i > len(lines) - 8 or is_potential_active_start_block:
            parsing_debug_log.append(f"\nLogParser ACTIVE SCAN (idx {i}):\n")
            parsing_debug_log.append(f"  Msg0: {repr(msg0)} (Expected: {repr(LOG_SEPARATOR_LINE_TEXT)}) Match: {msg0 == LOG_SEPARATOR_LINE_TEXT}\n")
            parsing_debug_log.append(f"  Msg1: {repr(msg1)} (Expected: {repr(LOG_SESSION_START_TEXT)}) Match: {msg1 == LOG_SESSION_START_TEXT}\n")
            parsing_debug_log.append(f"  Msg2: {repr(msg2)} (Expected prefix: {repr(LOG_TIMESTAMP_PREFIX_TEXT)}) Match: {msg2.startswith(LOG_TIMESTAMP_PREFIX_TEXT) if msg2 else False}\n")
            parsing_debug_log.append(f"  Msg3: {repr(msg3)} (Expected: {repr(LOG_SEPARATOR_LINE_TEXT)}) Match: {msg3 == LOG_SEPARATOR_LINE_TEXT}\n")

        if msg0 == LOG_SEPARATOR_LINE_TEXT and \
           msg1 == LOG_SESSION_START_TEXT and \
           (msg2 is not None and msg2.startswith(LOG_TIMESTAMP_PREFIX_TEXT)) and \
           msg3 == LOG_SEPARATOR_LINE_TEXT:
            session_start_block_indices.append(i)
            parsing_debug_log.append(f"LogParser: Found potential session start block at line index {i}.\n")
            print(f"LogParser: Found potential session start block at line index {i}.") 
            found_start_marker_this_run = True
    
    if session_start_block_indices:
        last_session_start_block_start_index = session_start_block_indices[-1]
        parsing_debug_log.append(f"LogParser: Last session start block (for active session) is at index {last_session_start_block_start_index}.\n")
        parsing_debug_log.append(f"LogParser: Extracting ACTIVE session from line {last_session_start_block_start_index} to end of file.\n")
        print(f"LogParser: Last session start block (for active session) is at index {last_session_start_block_start_index}.") 
        print(f"LogParser: Extracting ACTIVE session from line {last_session_start_block_start_index} to end of file.") 
        return "ACTIVE", "".join(lines[last_session_start_block_start_index:])
    elif not found_start_marker_this_run:
        parsing_debug_log.append("[LogParser: No session start marker blocks found either during active scan.]\n")
        print("[LogParser: No session start marker blocks found either during active scan.]") 

    final_error_message = "[LogParser: No session start or end markers found in log after all attempts]\n"
    parsing_debug_log.append(final_error_message)
    return "NONE", "".join(parsing_debug_log)

# --- Main Function ---
def generate_snapshot(summary_message=None, include_logs=False, summarize_modules=False, full_code_exceptions=None):
    """Generates a snapshot file."""
    project_root = get_project_root()
    utils_dir = os.path.join(project_root, "utils")
    snapshots_dir_path = os.path.join(project_root, SNAPSHOT_DIRECTORY)
    try:
        os.makedirs(snapshots_dir_path, exist_ok=True)
    except Exception as e:
        print(f"Error creating snapshot directory {snapshots_dir_path}: {e}"); return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_filename = SNAPSHOT_FILENAME_TEMPLATE.format(timestamp=timestamp)
    output_filepath = os.path.join(snapshots_dir_path, snapshot_filename)

    print(f"\nGenerating snapshot for project at: {project_root}")
    if summary_message: print(f"With summary: {summary_message}")
    if include_logs: print("Log inclusion requested.")
    if summarize_modules: print("Module summarization requested.")
    print(f"Output will be saved to: {output_filepath}\n")

    snapshot_content = [
        f"micro_X Project Snapshot\n",
        f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"Summary: {summary_message if summary_message else '[No summary provided for this snapshot]'}\n"
    ]
    log_inclusion_message = "[Log Inclusion: Not requested or no log data found]\n"
    log_session_content_for_snapshot = "" 
    log_section_header_for_snapshot = ""
    log_section_footer_for_snapshot = ""


    prerequisite_notices = []
    tree_success, tree_notice = run_utility_script("generate_tree.py", project_root, utils_dir)
    if not tree_success: prerequisite_notices.append(tree_notice) # Only append notice if script itself failed, not for tree generation logic failure
    
    tests_ran_successfully, tests_notice = run_utility_script("run_tests.py", project_root, utils_dir)
    # tests_notice will contain info about failures if run_tests.py returns 1 (test failures)
    # or if the script itself had an issue.
    if tests_notice: prerequisite_notices.append(tests_notice)

    if prerequisite_notices:
        snapshot_content.append("\n--- Prerequisite Utility Status ---\n")
        snapshot_content.extend(prerequisite_notices)
        snapshot_content.append("-----------------------------------\n\n")
    else:
        snapshot_content.append("\n[All prerequisite utilities executed successfully (tests may have passed or failed as reported by the test utility).]\n\n")
    
    log_session_type = "NONE" 
    if include_logs: 
        log_file_full_path = os.path.join(project_root, LOG_DIR_NAME, LOG_FILE_BASENAME)
        log_session_type, log_session_content_for_snapshot = _get_last_log_session(log_file_full_path)
        
        if log_session_type == "COMPLETED":
            log_inclusion_message = "Log Inclusion: Last completed session log included.\n"
            log_section_header_for_snapshot = f"--- START OF LAST COMPLETED LOG SESSION ({LOG_FILE_BASENAME}) ---\n"
            log_section_footer_for_snapshot = f"\n--- END OF LAST COMPLETED LOG SESSION ({LOG_FILE_BASENAME}) ---\n\n"
        elif log_session_type == "ACTIVE":
            log_inclusion_message = "Log Inclusion: Current active session log (up to snapshot time) included.\n"
            log_section_header_for_snapshot = f"--- START OF CURRENT ACTIVE LOG SESSION ({LOG_FILE_BASENAME}) ---\n"
            log_section_footer_for_snapshot = f"\n--- END OF CURRENT ACTIVE LOG SESSION ({LOG_FILE_BASENAME}) ---\n\n"
        else: # "NONE"
            log_inclusion_message = f"Log Inclusion: Attempted, but no suitable log session found. See debug trace below.\n"
            log_section_header_for_snapshot = f"--- LOG PARSING DEBUG TRACE ({LOG_FILE_BASENAME}) ---\n" 
            log_section_footer_for_snapshot = f"\n--- END OF LOG PARSING DEBUG TRACE ({LOG_FILE_BASENAME}) ---\n\n"
    
    snapshot_content.append(log_inclusion_message) 
    snapshot_content.append("=" * 80 + "\n\n")

    for relative_path in FILES_TO_INCLUDE:
        full_path = os.path.join(project_root, relative_path)
        
        # Default behavior
        is_summarizable_module = summarize_modules and relative_path in MODULE_FILES_TO_SUMMARIZE
        
        # New logic: Check for exceptions to the summarization rule
        if is_summarizable_module and full_code_exceptions:
            module_basename = os.path.basename(relative_path)
            # Allow matching with or without the .py extension
            if module_basename in full_code_exceptions or module_basename.replace('.py', '') in full_code_exceptions:
                print(f"Info: Overriding summarization for '{relative_path}' due to --include-full-module flag.")
                is_summarizable_module = False # Force full code inclusion for this module
        
        if is_summarizable_module:
            snapshot_content.append(f"# ==============================================================================\n")
            snapshot_content.append(f"# --- START OF API DOCS: {relative_path} ---\n")
            snapshot_content.append(f"# ==============================================================================\n")
            content = extract_api_documentation(full_path)
        else:
            snapshot_content.append(f"# ==============================================================================\n")
            snapshot_content.append(f"# --- START OF FILE: {relative_path} ---\n")
            snapshot_content.append(f"# ==============================================================================\n")
            content = read_file_content(full_path)

        snapshot_content.append(content if content is not None else f"[Content not available or file not found: {relative_path}]\n")
        
        if is_summarizable_module:
            snapshot_content.append(f"\n# ==============================================================================\n")
            snapshot_content.append(f"# --- END OF API DOCS: {relative_path} ---\n")
            snapshot_content.append(f"# ==============================================================================\n\n")
        else:
            snapshot_content.append(f"\n# ==============================================================================\n")
            snapshot_content.append(f"# --- END OF FILE: {relative_path} ---\n")
            snapshot_content.append(f"# ==============================================================================\n\n")


    if include_logs: 
        snapshot_content.append(log_section_header_for_snapshot)
        snapshot_content.append(log_session_content_for_snapshot) 
        snapshot_content.append(log_section_footer_for_snapshot)
        snapshot_content.append("=" * 80 + "\n\n")

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.writelines(snapshot_content)
        print(f"Successfully generated snapshot: {output_filepath}")
        return output_filepath
    except Exception as e:
        print(f"Error writing snapshot file: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a snapshot of the micro_X project context. "
                    "This includes specified source files, configuration, "
                    "and optionally the latest log session. "
                    "Prerequisite utilities (generate_tree.py, run_tests.py) are run by default "
                    "to ensure included artifacts like project_tree.txt and pytest_results.txt are up-to-date.",
        epilog="Typically run via '/utils generate_snapshot [options]' from within micro_X, "
               "or directly for development/debugging.",
        formatter_class=argparse.RawTextHelpFormatter # Allows for newlines in help
    )
    parser.add_argument(
        "-s", "--summary", type=str,
        help="A short summary or reason for generating this snapshot.\nThis will be included in the snapshot file.",
        default=None
    )
    parser.add_argument(
        "--include-logs", action="store_true",
        help="Include the last session (completed or active) from the log file\n(logs/micro_x.log) in the snapshot.",
        default=False
    )
    parser.add_argument(
        "--summarize", action="store_true",
        help="Summarize module files using their API documentation blocks\ninstead of including the full code to save tokens.",
        default=False
    )
    parser.add_argument(
        "--include-full-module",
        nargs='+',  # This allows accepting one or more values
        metavar='MODULE_NAME',
        help="Specify module(s) to include in full, even when --summarize is active. "
             "Provide just the filename, e.g., 'shell_engine.py' or 'shell_engine'.",
        default=[]
    )
    
    args = parser.parse_args()
    generated_file = generate_snapshot(
        summary_message=args.summary, 
        include_logs=args.include_logs,
        summarize_modules=args.summarize,
        full_code_exceptions=args.include_full_module
    )
    if generated_file: print(f"\nSnapshot generation complete. File: {generated_file}")
    else: print("\nSnapshot generation failed.")
