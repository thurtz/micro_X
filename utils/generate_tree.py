#!/usr/bin/env python

import os
import fnmatch # Added for robust pattern matching
import argparse # Added for help argument handling
import sys # Added to exit if path is not a directory

def _generate_recursive(current_path, prefix, ignore_dirs, ignore_files, 
                        pipe_segment, space_segment, entry_connector_dir, entry_connector_file,
                        output_lines):
    """
    Recursively generates the file tree for the current_path and appends to output_lines.

    Args:
        current_path (str): The directory path to list.
        prefix (str): The prefix string for indentation and tree lines.
        ignore_dirs (list): List of directory names to ignore.
        ignore_files (list): List of file names/extensions/patterns to ignore (supports fnmatch).
        pipe_segment (str): String for a pipe segment in the prefix (e.g., "|   ").
        space_segment (str): String for a space segment in the prefix (e.g., "    ").
        entry_connector_dir (str): Prefix for directory entries (e.g., "├── ").
        entry_connector_file (str): Prefix for the last entry in a list (e.g., "└── ").
        output_lines (list): A list to accumulate the lines of the tree.
    """
    try:
        entries = os.listdir(current_path)
    except OSError as e:
        # Handle cases where a directory might not be accessible
        output_lines.append(f"{prefix}{entry_connector_file}[Error accessing: {os.path.basename(current_path)} - {e.strerror}]")
        return

    # Separate directories and files, then filter and sort
    dirs_to_process = []
    files_to_print = []

    for entry_name in entries:
        entry_full_path = os.path.join(current_path, entry_name)
        if os.path.isdir(entry_full_path):
            if entry_name not in ignore_dirs: # Simple name check for directories
                dirs_to_process.append(entry_name)
        else: # It's a file
            is_ignored = False
            for pattern in ignore_files: # Use fnmatch for file patterns
                if fnmatch.fnmatch(entry_name, pattern):
                    is_ignored = True
                    break
            if not is_ignored:
                files_to_print.append(entry_name)
    
    dirs_to_process.sort()
    files_to_print.sort()

    # Combine sorted directories and files for ordered printing
    all_items_to_render = [(d, True) for d in dirs_to_process] + \
                          [(f, False) for f in files_to_print]

    for i, (item_name, is_dir_item) in enumerate(all_items_to_render):
        is_last_entry = (i == len(all_items_to_render) - 1)
        connector = entry_connector_file if is_last_entry else entry_connector_dir
        
        display_name = item_name + os.sep if is_dir_item else item_name
        output_lines.append(f"{prefix}{connector}{display_name}")

        if is_dir_item:
            child_prefix = prefix + (space_segment if is_last_entry else pipe_segment)
            _generate_recursive(os.path.join(current_path, item_name), 
                                child_prefix, 
                                ignore_dirs, ignore_files,
                                pipe_segment, space_segment, 
                                entry_connector_dir, entry_connector_file,
                                output_lines)


def generate_file_tree(startpath, output_filepath, display_root_name="micro_X", ignore_dirs=None, ignore_files=None):
    """
    Generates a file tree structure and saves it to a file.

    Args:
        startpath (str): The root directory from which to generate the tree.
        output_filepath (str): The full path to the file where the tree will be saved.
        display_root_name (str, optional): The name to display for the root of the tree.
        ignore_dirs (list, optional): A list of directory names to ignore.
        ignore_files (list, optional): A list of file names/extensions/patterns to ignore (supports fnmatch).
    """
    # Define tree drawing elements
    pipe_segment = "|   " # Consistent spacing
    space_segment = "    " # Consistent spacing
    entry_connector_dir = "├── "
    entry_connector_file = "└── "

    if ignore_dirs is None:
        ignore_dirs = ['.git', '__pycache__', '.venv', 'venv', 'env', 'ENV', 
                       '.pytest_cache', '.mypy_cache', '.ruff_cache', 'logs', 
                       'build', 'dist', 'site', '*.egg-info', 
                       'snapshots'] # Added snapshots to default ignore_dirs
    if ignore_files is None:
        # Default ignore_files, including the pattern for timestamped pytest results
        ignore_files = ['.DS_Store', '*.pyc', '*.pyo', '.coverage', 'pytest_results_*.txt'] 

    if not os.path.isdir(startpath):
        print(f"Error: Provided path '{startpath}' is not a directory or does not exist.")
        return False # Indicate failure

    output_lines = []
    # Add the desired display root name as the first line
    output_lines.append(f"Generating file tree for: {display_root_name}\n")
    output_lines.append(display_root_name) # The actual root name for the tree structure

    # Start the recursive generation for the contents of the root directory
    _generate_recursive(startpath, "", 
                        ignore_dirs, ignore_files,
                        pipe_segment, space_segment,
                        entry_connector_dir, entry_connector_file,
                        output_lines)
    
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            for line in output_lines:
                f.write(line + "\n")
        print(f"File tree successfully saved to: {output_filepath}")
        return True # Indicate success
    except Exception as e:
        print(f"Error writing file tree to {output_filepath}: {e}")
        return False # Indicate failure


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a directory tree structure for the micro_X project.",
        epilog="This script is typically run from the '/utils list' or '/utils generate_tree' command within the micro_X shell."
    )

    
    args = parser.parse_args() # This will handle -h/--help

    script_location_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine project root (assuming script is in 'utils' or project root)
    project_root_candidate = os.path.dirname(script_location_dir) \
                             if os.path.basename(script_location_dir).lower() in ['utils', 'scripts'] \
                             else script_location_dir
    
    if os.path.exists(os.path.join(project_root_candidate, "main.py")): 
        project_root = project_root_candidate
    else:
        # Fallback if main.py not found, or if script is run from an unexpected location
        print("Warning: Could not reliably determine project root based on 'main.py'.")
        print(f"Assuming project root is: {project_root_candidate}")
        project_root = project_root_candidate

    # Define the output file path
    output_filename = "project_tree.txt" # Keep this fixed for now, or use args.output if defined
    output_file_full_path = os.path.join(project_root, output_filename)

    desired_root_display_name = "micro_X" # This is the name displayed at the top of the tree

    # Sensible defaults for viewing the micro_X project structure
    custom_ignore_dirs = [
        '.git', '__pycache__', '.venv', 'venv', 'env', 'ENV', 
        '.pytest_cache', '.mypy_cache', '.ruff_cache', 'logs', 
        'build', 'dist', 'site', '*.egg-info', 'main_versions',
        'snapshots' # Also ignore the snapshots directory itself from the tree
    ]
    custom_ignore_files = [
        '.DS_Store', '*.pyc', '*.pyo', '.coverage', 
        'pytest_results_*.txt', # Corrected pattern for timestamped pytest results
        output_filename, # Ignore the tree file itself if it exists
        '*.old.*' # Exclude user's local backup files (e.g., file.old.py)
    ]

    print(f"Attempting to generate file tree and save to: {output_file_full_path}")
    
    success = generate_file_tree(project_root,
                                 output_filepath=output_file_full_path,
                                 display_root_name=desired_root_display_name,
                                 ignore_dirs=custom_ignore_dirs, 
                                 ignore_files=custom_ignore_files)

    if success:
        print(f"\nGeneration complete. Tree saved in: {output_file_full_path}")
    else:
        print("\nTree generation failed or could not be saved.")
        sys.exit(1)
