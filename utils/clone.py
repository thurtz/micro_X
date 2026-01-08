# utils/clone.py

import os
import shutil
import argparse
import sys
import fnmatch
import datetime

HELP_TEXT = """
micro_X Utility: Clone Project

Creates a functional copy (clone) of the 'micro_X-dev' environment.
Useful for creating sandboxes for testing dangerous commands or experimental features
without affecting your primary development environment.

Usage:
  /utils clone [name]

Arguments:
  name    (Optional) The name of the new clone.
          If omitted, a name like 'clone_YYYYMMDD_HHMMSS' will be generated.

Notes:
  - This utility ALWAYS clones the 'micro_X-dev' directory, regardless of which branch it is run from.
  - It respects .gitignore (excludes .git, .venv, logs, etc.).
  - You must run ./setup.sh inside the new clone to initialize its environment.
"""

def find_micro_x_root():
    """
    Finds the absolute path of the 'micro_X' (main) root directory.
    Assumes this script is in .../micro_X[/micro_X-dev]/utils/clone.py
    """
    current = os.path.abspath(__file__)
    # Go up from utils/
    current = os.path.dirname(os.path.dirname(current))
    
    # If we are in dev or testing, we need to go up one more level to reach the main root
    folder_name = os.path.basename(current)
    if folder_name in ["micro_X-dev", "micro_X-testing"]:
        current = os.path.dirname(current)
    
    return current

def parse_gitignore(root_dir):
    """Parses .gitignore patterns from the directory."""
    gitignore_path = os.path.join(root_dir, ".gitignore")
    patterns = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    
    # Always force ignore specific heavy/generated dirs
    patterns.append(".git")
    patterns.append(".venv")
    patterns.append("__pycache__")
    patterns.append("clones") # Don't copy other clones!
    return patterns

def should_ignore(path, names, root_dir, ignore_patterns):
    """Custom ignore callable for shutil.copytree."""
    ignored_names = set()
    rel_path = os.path.relpath(path, root_dir)
    if rel_path == ".":
        rel_path = ""

    for name in names:
        child_rel_path = os.path.join(rel_path, name) if rel_path else name
        
        for pattern in ignore_patterns:
            is_dir_pattern = pattern.endswith("/")
            clean_pattern = pattern.rstrip("/")
            
            if fnmatch.fnmatch(name, clean_pattern) or \
               fnmatch.fnmatch(child_rel_path, clean_pattern) or \
               fnmatch.fnmatch(child_rel_path, pattern):
                ignored_names.add(name)
                break
            
            if is_dir_pattern and (fnmatch.fnmatch(name, clean_pattern) or fnmatch.fnmatch(child_rel_path, clean_pattern)):
                 ignored_names.add(name)
                 break
    return ignored_names

def main():
    parser = argparse.ArgumentParser(description="Clone the micro_X dev environment.")
    parser.add_argument("name", nargs="?", default=None, help="Name of the clone (optional).")
    args = parser.parse_args()

    # Auto-generate name if missing
    if not args.name:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.name = f"clone_{timestamp}"
        print(f"ℹ️  No name provided. Using auto-generated name: '{args.name}'")

    main_root = find_micro_x_root()
    source_dir = os.path.join(main_root, "micro_X-dev")

    if not os.path.isdir(source_dir):
        print(f"Error: Could not locate 'micro_X-dev' directory at '{source_dir}'.")
        print("Please ensure you have activated the dev environment using '/dev --activate'.")
        sys.exit(1)

    # Determine Destination
    clones_dir = os.path.join(source_dir, "clones")
    dest_dir = os.path.join(clones_dir, args.name)

    if os.path.exists(dest_dir):
        print(f"Error: Destination '{dest_dir}' already exists.")
        sys.exit(1)

    print(f"Source:      {source_dir}")
    print(f"Destination: {dest_dir}")
    print("Cloning 'micro_X-dev'...")

    ignore_patterns = parse_gitignore(source_dir)
    
    # Ensure clones directory exists
    os.makedirs(clones_dir, exist_ok=True)
    
    try:
        shutil.copytree(
            source_dir, 
            dest_dir, 
            ignore=lambda src, names: should_ignore(src, names, source_dir, ignore_patterns)
        )
        print(f"\n✅ Clone created successfully!")
        print(f"   Location: {dest_dir}")
        print(f"\nNext Steps:")
        print(f"1. cd {dest_dir}")
        print(f"2. ./setup.sh  (To create the virtual environment)")
        print(f"3. ./micro_X.sh")
    except Exception as e:
        print(f"\n❌ Error cloning project: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()