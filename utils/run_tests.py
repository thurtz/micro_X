#!/usr/bin/env python

import subprocess
import os
import sys
import datetime
import re # Not strictly needed in this version if only doing string replace for sanitization
import logging

# --- Configuration ---
RESULTS_DIR_NAME = "pytest_results"
FIXED_RESULTS_FILENAME = "pytest_results.txt"
PROJECT_ROOT_PLACEHOLDER = "<PROJECT_ROOT>"
HOME_DIR_PLACEHOLDER = "<HOME>"

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

def get_project_root():
    """
    Determines the project root directory.
    Assumes this script is in a 'utils' subdirectory of the project root,
    and the project root contains a 'main.py' or a '.git' directory as fallback.
    """
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    project_root_candidate1 = os.path.dirname(utils_dir)

    # Check criteria
    if os.path.exists(os.path.join(project_root_candidate1, "main.py")) or \
       os.path.exists(os.path.join(project_root_candidate1, ".venv")) or \
       os.path.exists(os.path.join(project_root_candidate1, ".git")):
        # Don't log the absolute path here, it will be logged by the caller if needed
        return project_root_candidate1

    if os.path.exists(os.path.join(utils_dir, "main.py")) or \
       os.path.exists(os.path.join(utils_dir, ".venv")) or \
       os.path.exists(os.path.join(utils_dir, ".git")):
        return utils_dir

    # Fallback, log this warning in the main run_tests function where context is clearer
    return project_root_candidate1

def sanitize_pytest_output(output_text: str, proj_root: str, user_home: str) -> str:
    """Sanitizes project and home directory paths in pytest output."""
    sanitized_text = output_text
    sanitized_text = sanitized_text.replace(proj_root, PROJECT_ROOT_PLACEHOLDER)
    if user_home != "/" and user_home != proj_root:
        if not proj_root.startswith(user_home + os.sep):
            sanitized_text = sanitized_text.replace(user_home, HOME_DIR_PLACEHOLDER)
    if HOME_DIR_PLACEHOLDER not in PROJECT_ROOT_PLACEHOLDER and user_home != "/":
        sanitized_text = sanitized_text.replace(user_home, HOME_DIR_PLACEHOLDER)
    return sanitized_text

def display_path(abs_path: str, proj_root: str, user_home: str) -> str:
    """Returns a path string suitable for display, anonymized if necessary."""
    if abs_path.startswith(proj_root):
        relative_part = os.path.relpath(abs_path, proj_root)
        return f"{PROJECT_ROOT_PLACEHOLDER}{os.sep}{relative_part}" if relative_part != '.' else PROJECT_ROOT_PLACEHOLDER
    elif abs_path.startswith(user_home) and user_home != "/": # Added user_home != "/" to avoid replacing root if home is root
        relative_part = os.path.relpath(abs_path, user_home)
        return f"{HOME_DIR_PLACEHOLDER}{os.sep}{relative_part}" if relative_part != '.' else HOME_DIR_PLACEHOLDER
    return abs_path # Return original if not under project or home, or if logic is complex

def run_tests():
    """
    Runs pytest, captures its output, sanitizes paths, and saves the results.
    Console output from this utility itself will also use anonymized paths.
    """
    project_root = get_project_root()
    home_dir = os.path.expanduser("~")

    # Log the identified project root (once, and clearly marked)
    logger.info(f"Project root identified. Will be referred to as {PROJECT_ROOT_PLACEHOLDER} in subsequent messages and results.")
    logger.info(f"Actual project root: {project_root}") # Log it once for debug if needed, console will use placeholder
    if not (os.path.exists(os.path.join(project_root, "main.py")) or \
            os.path.exists(os.path.join(project_root, ".venv")) or \
            os.path.exists(os.path.join(project_root, ".git"))):
        logger.warning(f"Could not reliably determine project root. Using: {project_root}")
        # Use display_path for the warning printed to console
        print(f"Warning: Project root determination might be inaccurate (using {display_path(project_root, project_root, home_dir)}).")


    venv_dir_abs = os.path.join(project_root, ".venv")
    pytest_executable_name = "pytest.exe" if sys.platform == "win32" else "pytest"
    pytest_path_abs = os.path.join(venv_dir_abs, "Scripts" if sys.platform == "win32" else "bin", pytest_executable_name)

    results_abs_dir = os.path.join(project_root, RESULTS_DIR_NAME)
    os.makedirs(results_abs_dir, exist_ok=True)

    fixed_results_file_path_abs = os.path.join(results_abs_dir, FIXED_RESULTS_FILENAME)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_results_file_path_abs = os.path.join(results_abs_dir, f"pytest_results_{timestamp}.txt")

    # Use display_path for console output
    dp_project_root = PROJECT_ROOT_PLACEHOLDER # Since all project paths will be relative to this
    dp_pytest_path = display_path(pytest_path_abs, project_root, home_dir)
    dp_fixed_results_file = display_path(fixed_results_file_path_abs, project_root, home_dir)
    dp_timestamped_results_file = display_path(timestamped_results_file_path_abs, project_root, home_dir)

    if not os.path.exists(pytest_path_abs):
        logger.error(f"Pytest executable not found at actual path: '{pytest_path_abs}'.")
        print(f"Error: Pytest executable not found at '{dp_pytest_path}'.")
        print("Please ensure pytest is installed in the virtual environment '.venv'.")
        sys.exit(2)

    logger.info(f"Running tests from project root (shown as {dp_project_root})")
    logger.info(f"Pytest executable (shown as {dp_pytest_path})")
    logger.info(f"Saving fixed results to (shown as {dp_fixed_results_file})")
    logger.info(f"Saving timestamped results to (shown as {dp_timestamped_results_file})")

    print(f"\nRunning tests from: {dp_project_root}")
    print(f"Using Pytest: {dp_pytest_path}")

    pytest_command = [pytest_path_abs, project_root, "--tb=short"]
    
    try:
        process = subprocess.run(
            pytest_command,
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False
        )
    except FileNotFoundError:
        logger.error(f"Error: Could not execute pytest. Actual path '{pytest_path_abs}' not found or not executable.")
        print(f"Error: Could not execute pytest. '{dp_pytest_path}' not found or not executable.")
        sys.exit(3)
    except Exception as e:
        logger.error(f"An unexpected error occurred while trying to run pytest: {e}")
        print(f"An unexpected error occurred while trying to run pytest: {e}")
        sys.exit(4)

    raw_stdout = process.stdout
    raw_stderr = process.stderr

    sanitized_stdout = sanitize_pytest_output(raw_stdout, project_root, home_dir)
    sanitized_stderr = sanitize_pytest_output(raw_stderr, project_root, home_dir)

    output_for_file_lines = []
    output_for_file_lines.append(f"pytest execution from micro_X utility ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    # Construct the command string using placeholders for the file output
    anonymized_pytest_executable = f"{PROJECT_ROOT_PLACEHOLDER}{os.sep}.venv{os.sep}{'Scripts' if sys.platform == 'win32' else 'bin'}{os.sep}{pytest_executable_name}"
    output_for_file_lines.append(f"Command: {anonymized_pytest_executable} {PROJECT_ROOT_PLACEHOLDER} --tb=short\n")
    output_for_file_lines.append(f"Return Code: {process.returncode}\n")
    # Modified lines to not include the actual paths in the file:
    output_for_file_lines.append(f"Note: Actual project root path has been replaced with: {PROJECT_ROOT_PLACEHOLDER}\n")
    if home_dir != "/" and home_dir != project_root : # Check if home_dir is distinct and not root
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

    sys.exit(process.returncode)

if __name__ == "__main__":
    run_tests()
