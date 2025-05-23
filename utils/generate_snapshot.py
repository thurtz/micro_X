#!/usr/bin/env python

import os
import datetime

# --- Configuration ---
# Files and directories to include in the snapshot.
# Paths are relative to the project root (where this script's parent directory is).
FILES_TO_INCLUDE = [
    "main.py",
    "config/default_config.json",
    "config/default_command_categories.json",
    "config/.tmux.conf",          # Added .tmux.conf
    "requirements.txt",
    ".gitignore",
    "utils/generate_tree.py",
    "utils/generate_snapshot.py",
    "project_tree.txt",
    "README.md",
    "micro_X.sh",                 # Added micro_X.sh
    "micro_X.desktop",             # Added micro_X.desktop
    "modules/ai_handler.py",     # Added ai_handler.py
    "modules/category_manager.py", # Added category_handler.py
    "modules/output_analyzer.py", # Added output_analyzer.py
    "modules/ollama_manager.py", # Added ollama_manager.py
    "modules/shell_engine.py",   # Added shell_engine.py
    "setup_scripts/setup_micro_X_mac.sh", # Added setup_micro_x_mac.sh
    "setup_scripts/setup_micro_X_mint.sh", # Added setup_micro_x_mint.sh
    "setup_scripts/setup_micro_X_termux.sh", # Added setup_micro_x_termux.sh
    "setup_scripts/setup_micro_X_wsl.sh", # Added setup_micro_x_wsl.sh
    "tests/test_ai_handler.py", # Added test_ai_handler.py
    "tests/test_category_manager.py", # Added test_category_manager.py
    "tests/conftest.py", # Added test_conftest.py
    "tests/test_ui_manager.py", # Added test_ui_manager.py
    "tests/test_shell_engine.py", # Added test_shell_engine.py
    "tests/tests.md", # Added tests.md
    "pytest_results/pytest_results.txt", # Added pytest_results.txt
    "modules/ui_manager.py", # Added ui_manager.py
    "docs/micro_X_User_Guide.md", # Added micro_X_User_Guide.md
    "docs/setup_micro_X_mac.md", # Added setup_micro_x_mac.sh
    "docs/setup_micro_X_mint.md", # Added setup_micro_x_mint.sh
    "docs/setup_micro_X_termux.md", # Added setup_micro_x_termux.sh
    "docs/setup_micro_X_wsl.md", # Added setup_micro_x_wsl.sh
    "docs/review_of_micro_X_project.md", # Added review_of_micro_X_project.md
    "setup.sh", # Added setup.sh
    "docs/micro_X_testing_guide.md" # Added micro_X_testing_guide.md
]

# Output directory and filename for the snapshot
SNAPSHOT_DIRECTORY = "snapshots" # New directory for snapshots
SNAPSHOT_FILENAME_TEMPLATE = "micro_x_context_snapshot_{timestamp}.txt"

# --- Helper Functions ---
def get_project_root():
    """Determines the project root directory.
    Assumes this script is in a 'utils' subdirectory of the project root.
    """
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(utils_dir)
    # Basic check: does it look like a project root (e.g., contains main.py)?
    if os.path.exists(os.path.join(project_root, "main.py")):
        return project_root
    else:
        # Fallback if main.py is not found in parent, maybe script is in root
        if os.path.exists(os.path.join(utils_dir, "main.py")):
             return utils_dir
        print("Warning: Could not reliably determine project root. Using script's directory's parent.")
        return project_root


def read_file_content(filepath):
    """Reads the content of a file. Returns None if file not found or error."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: File not found - {filepath}") # This print is for direct execution
        return None
    except Exception as e:
        print(f"Warning: Error reading file {filepath} - {e}") # This print is for direct execution
        return None

# --- Main Function ---
def generate_snapshot():
    """Generates a snapshot file containing the content of specified project files."""
    project_root = get_project_root()
    
    # Define the snapshots directory path
    snapshots_dir_path = os.path.join(project_root, SNAPSHOT_DIRECTORY)

    # Create the snapshots directory if it doesn't exist
    try:
        os.makedirs(snapshots_dir_path, exist_ok=True)
        # print(f"Ensured snapshot directory exists: {snapshots_dir_path}") # For direct execution feedback
    except Exception as e:
        print(f"Error creating snapshot directory {snapshots_dir_path}: {e}")
        return None
        
    # Generate a timestamp for the filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_filename = SNAPSHOT_FILENAME_TEMPLATE.format(timestamp=timestamp)
    
    output_filepath = os.path.join(snapshots_dir_path, snapshot_filename)

    # These print statements are primarily for when the script is run directly
    print(f"Generating snapshot for project at: {project_root}")
    print(f"Output will be saved to: {output_filepath}")

    snapshot_content = []
    snapshot_content.append(f"micro_X Project Snapshot\n")
    snapshot_content.append(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    # Removed Project Root from snapshot content to avoid full paths
    snapshot_content.append("=" * 80 + "\n\n")

    for relative_path in FILES_TO_INCLUDE:
        full_path = os.path.join(project_root, relative_path)
        
        snapshot_content.append(f"--- START OF FILE: {relative_path} ---\n")
        
        content = read_file_content(full_path)
        if content is not None:
            snapshot_content.append(content)
        else:
            snapshot_content.append(f"[Content not available or file not found: {relative_path}]\n")
        
        snapshot_content.append(f"\n--- END OF FILE: {relative_path} ---\n\n")
        snapshot_content.append("=" * 80 + "\n\n")

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.writelines(snapshot_content)
        print(f"Successfully generated snapshot: {output_filepath}") # For direct execution feedback
        return output_filepath # Return the path for confirmation
    except Exception as e:
        print(f"Error writing snapshot file: {e}") # For direct execution feedback
        return None

if __name__ == "__main__":
    generated_file = generate_snapshot()
    if generated_file:
        print(f"\nSnapshot generation complete. File: {generated_file}")
    else:
        print("\nSnapshot generation failed.")
