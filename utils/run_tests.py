#!/usr/bin/env python

import subprocess
import os
import sys
import datetime
import re # Not strictly needed in this version if only doing string replace for sanitization
import logging
import argparse # Added for help argument handling

# --- Configuration ---
RESULTS_DIR_NAME = "pytest_results"
FIXED_RESULTS_FILENAME = "pytest_results.txt"
PROJECT_ROOT_PLACEHOLDER = "<PROJECT_ROOT>"
HOME_DIR_PLACEHOLDER = "<HOME>"

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# BasicConfig will be set in if __name__ == "__main__" or by the calling application (micro_X)

def get_project_root():
    """
    Determines the project root directory.
    Assumes this script is in a 'utils' subdirectory of the project root,
    or the project root itself.
    """
    script_path = os.path.abspath(__file__)
    current_dir_name = os.path.basename(os.path.dirname(script_path))
    
    # Candidate 1: Parent of the script's directory (if script is in utils/)
    project_root_candidate1 = os.path.dirname(os.path.dirname(script_path))
    # Candidate 2: The script's own directory (if script is in root, e.g. for direct run)
    project_root_candidate2 = os.path.dirname(script_path)

    def is_valid_root(path):
        return os.path.exists(os.path.join(path, "main.py")) or \
               os.path.exists(os.path.join(path, ".venv")) or \
               os.path.exists(os.path.join(path, ".git")) or \
               os.path.isdir(os.path.join(path, "modules")) # Added modules check

    if current_dir_name == "utils" and is_valid_root(project_root_candidate1):
        return project_root_candidate1
    elif is_valid_root(project_root_candidate2): # If not in utils, check if script_dir is root
        return project_root_candidate2
    elif is_valid_root(project_root_candidate1): # Fallback to parent even if not in "utils"
         return project_root_candidate1
    else: # Final fallback if no clear indicators
        logger.warning(f"Could not reliably determine project root from '{script_path}'. Using script's parent directory: {project_root_candidate2}")
        return project_root_candidate2


def sanitize_pytest_output(output_text: str, proj_root: str, user_home: str) -> str:
    """Sanitizes project and home directory paths in pytest output."""
    sanitized_text = output_text
    # Replace project_root first, as it might be inside home_dir
    sanitized_text = sanitized_text.replace(proj_root, PROJECT_ROOT_PLACEHOLDER)
    
    # Only replace home_dir if it's different from project_root and not just "/"
    # and ensure project_root (now placeholder) isn't part of home_dir string being replaced
    if user_home != "/" and user_home != proj_root:
        # Check if proj_root was a subdirectory of home_dir
        if proj_root.startswith(user_home + os.sep):
            # If so, home_dir part would have been replaced if we naively replace user_home
            # Example: home_dir = /home/user, proj_root = /home/user/project
            # proj_root becomes <PROJECT_ROOT>
            # We should not replace "/home/user" with "<HOME>" if it's part of "<PROJECT_ROOT>" original path
            # This is tricky. The current replacement order (proj_root then home_dir) is generally safer.
            # We just need to be careful not to re-replace parts of the already replaced proj_root.
            # A simple string replace of user_home should be okay if PROJECT_ROOT_PLACEHOLDER is unique.
            pass # Handled by the next replacement if user_home is still in the string

        # Replace user_home if it's still present and distinct
        # This check ensures we don't replace / if home is /
        # and also avoids replacing if home_dir was the same as proj_root (already handled)
        sanitized_text = sanitized_text.replace(user_home, HOME_DIR_PLACEHOLDER)
        
    return sanitized_text

def display_path(abs_path: str, proj_root: str, user_home: str) -> str:
    """Returns a path string suitable for display, anonymized if necessary."""
    if abs_path.startswith(proj_root):
        relative_part = os.path.relpath(abs_path, proj_root)
        return f"{PROJECT_ROOT_PLACEHOLDER}{os.sep}{relative_part}" if relative_part != '.' else PROJECT_ROOT_PLACEHOLDER
    elif user_home != "/" and abs_path.startswith(user_home) : # Added user_home != "/"
        relative_part = os.path.relpath(abs_path, user_home)
        return f"{HOME_DIR_PLACEHOLDER}{os.sep}{relative_part}" if relative_part != '.' else HOME_DIR_PLACEHOLDER
    return abs_path # Return original if not under project or home, or if logic is complex

def run_tests_main_logic():
    """
    Core logic for running tests and saving results.
    Returns the pytest exit code.
    """
    project_root = get_project_root()
    home_dir = os.path.expanduser("~")

    logger.info(f"Project root identified as: {project_root}. Will be referred to as {PROJECT_ROOT_PLACEHOLDER} in subsequent messages and results.")
    # Log the actual path once for debugging if needed, console will use placeholder
    logger.debug(f"Actual project root: {project_root}") 
    
    # Check for .venv more robustly
    venv_dir_abs = os.path.join(project_root, ".venv")
    pytest_executable_name = "pytest.exe" if sys.platform == "win32" else "pytest"
    
    # Determine pip executable path within venv
    if sys.platform == "win32":
        pytest_path_abs = os.path.join(venv_dir_abs, "Scripts", pytest_executable_name)
        if not os.path.exists(pytest_path_abs): # Fallback for some Windows venv structures
             pytest_path_abs = os.path.join(venv_dir_abs, "bin", pytest_executable_name)
    else: # Linux, macOS
        pytest_path_abs = os.path.join(venv_dir_abs, "bin", pytest_executable_name)


    results_abs_dir = os.path.join(project_root, RESULTS_DIR_NAME)
    os.makedirs(results_abs_dir, exist_ok=True)

    # --- CHANGE START: Make the test path explicit ---
    # This ensures pytest only looks in the correct 'tests' directory
    # at the root of the current project context (main, dev, or testing).
    tests_dir_abs = os.path.join(project_root, "tests")
    # --- CHANGE END ---

    fixed_results_file_path_abs = os.path.join(results_abs_dir, FIXED_RESULTS_FILENAME)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_results_file_path_abs = os.path.join(results_abs_dir, f"pytest_results_{timestamp}.txt")

    dp_project_root = PROJECT_ROOT_PLACEHOLDER 
    dp_pytest_path = display_path(pytest_path_abs, project_root, home_dir)
    dp_fixed_results_file = display_path(fixed_results_file_path_abs, project_root, home_dir)
    dp_timestamped_results_file = display_path(timestamped_results_file_path_abs, project_root, home_dir)

    if not os.path.exists(pytest_path_abs):
        logger.error(f"Pytest executable not found at actual path: '{pytest_path_abs}'.")
        print(f"Error: Pytest executable not found at '{dp_pytest_path}'.")
        print("Please ensure pytest is installed in the virtual environment '.venv' (e.g., via setup.sh or by running 'pip install pytest pytest-mock pytest-asyncio' in the activated venv).")
        return 2 # Pytest's exit code for internal error / setup issue

    # --- CHANGE START: Check for tests directory ---
    if not os.path.isdir(tests_dir_abs):
        logger.error(f"Tests directory not found at actual path: '{tests_dir_abs}'.")
        dp_tests_dir = display_path(tests_dir_abs, project_root, home_dir)
        print(f"Error: Tests directory not found at '{dp_tests_dir}'.")
        print("Please ensure a 'tests' directory exists in the project root.")
        return 2 # Pytest's exit code for setup issue
    # --- CHANGE END ---

    logger.info(f"Running tests from project root (shown as {dp_project_root})")
    logger.info(f"Pytest executable (shown as {dp_pytest_path})")
    logger.info(f"Saving fixed results to (shown as {dp_fixed_results_file})")
    logger.info(f"Saving timestamped results to (shown as {dp_timestamped_results_file})")

    print(f"\nRunning tests from: {dp_project_root}")
    print(f"Using Pytest: {dp_pytest_path}")

    # --- CHANGE START: Use explicit tests directory ---
    # Pytest command: run pytest on the specific tests_dir_abs, use short traceback
    pytest_command = [pytest_path_abs, tests_dir_abs, "--tb=short"]
    # --- CHANGE END ---
    
    try:
        process = subprocess.run(
            pytest_command,
            capture_output=True,
            text=True,
            cwd=project_root, # Run pytest from the project root
            check=False, # We'll check the returncode manually
            errors='replace' # Replace non-UTF8 chars if any
        )
    except FileNotFoundError:
        logger.error(f"Error: Could not execute pytest. Actual path '{pytest_path_abs}' not found or not executable.")
        print(f"Error: Could not execute pytest. '{dp_pytest_path}' not found or not executable.")
        return 3 # Pytest's exit code for interruption
    except Exception as e:
        logger.error(f"An unexpected error occurred while trying to run pytest: {e}", exc_info=True)
        print(f"An unexpected error occurred while trying to run pytest: {e}")
        return 4 # Pytest's exit code for internal error

    raw_stdout = process.stdout
    raw_stderr = process.stderr

    sanitized_stdout = sanitize_pytest_output(raw_stdout, project_root, home_dir)
    sanitized_stderr = sanitize_pytest_output(raw_stderr, project_root, home_dir)

    output_for_file_lines = []
    output_for_file_lines.append(f"pytest execution from micro_X utility ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    
    anonymized_pytest_executable_for_display = display_path(pytest_path_abs, project_root, home_dir)
    
    # --- CHANGE START: Update command in log file ---
    anonymized_tests_dir_for_display = display_path(tests_dir_abs, project_root, home_dir)
    output_for_file_lines.append(f"Command: {anonymized_pytest_executable_for_display} {anonymized_tests_dir_for_display} --tb=short\n")
    # --- CHANGE END ---

    output_for_file_lines.append(f"Return Code: {process.returncode}\n")
    output_for_file_lines.append(f"Note: Actual project root path has been replaced with: {PROJECT_ROOT_PLACEHOLDER}\n")
    if home_dir != "/" and home_dir != project_root : 
        output_for_file_lines.append(f"Note: Actual home directory path has been replaced with: {HOME_DIR_PLACEHOLDER}\n")
    
    output_for_file_lines.append("\n--- STDOUT ---\n")
    output_for_file_lines.append(sanitized_stdout)
    output_for_file_lines.append("\n--- STDERR ---\n")
    output_for_file_lines.append(sanitized_stderr)
    final_output_content = "".join(output_for_file_lines)

    try:
        with open(fixed_results_file_path_abs, "w", encoding="utf-8") as f:
            f.write(final_output_content)
        logger.info(f"Latest test results saved to actual path: {fixed_results_file_path_abs}")
    except IOError as e:
        logger.error(f"Error writing to fixed results file {fixed_results_file_path_abs}: {e}")

    try:
        with open(timestamped_results_file_path_abs, "w", encoding="utf-8") as f:
            f.write(final_output_content)
        logger.info(f"Timestamped test results saved to actual path: {timestamped_results_file_path_abs}")
    except IOError as e:
        logger.error(f"Error writing to timestamped results file {timestamped_results_file_path_abs}: {e}")

    print("\n--- Pytest Execution Summary ---")
    print(f"Return Code: {process.returncode}")
    if process.returncode == 0:
        print("Status: All tests passed!")
    elif process.returncode == 1: # Pytest specific code for test failures
        print("Status: Some tests failed.")
    elif process.returncode == 5: # Pytest specific code for no tests collected
        print("Status: No tests were collected.")
    else:
        print(f"Status: Pytest exited with code {process.returncode} (see logs or full results file).")
    
    print(f"Full results (sanitized) saved to:")
    print(f"  - Latest: {dp_fixed_results_file}")
    print(f"  - Archive: {dp_timestamped_results_file}")
    print("---------------------------------")

    return process.returncode


if __name__ == "__main__":
    # Setup basic logging for direct script execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    parser = argparse.ArgumentParser(
        description="Run pytest for the micro_X project and save sanitized results.",
        epilog="This script is typically run via '/utils run_tests' from within the micro_X shell, "
               "or directly for development purposes. It expects pytest to be installed in the '.venv' "
               "of the project root."
    )

    
    args = parser.parse_args() # Handles -h/--help

    exit_code = run_tests_main_logic()
    sys.exit(exit_code)
