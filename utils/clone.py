# utils/clone.py

import os
import subprocess
import argparse
import sys
import datetime
import json

HELP_TEXT = """
micro_X Utility: Clone Project (Git Worktree Version)

Creates an isolated development environment using 'git worktree'.
This creates a new Git branch and checks it out into a separate directory
within 'clones/', allowing for independent development, testing, and 
seamless merging back to the 'dev' branch.

Usage:
  /utils clone [name] [--bump]

Arguments:
  name    (Optional) The name of the new clone/branch.
          If omitted, a name like 'clone_YYYYMMDD_HHMMSS' will be generated.
  --bump  Auto-name the clone by incrementing the version found in config/default_config.json.
          e.g., if version is 0.0.1034, clone name becomes 'clone_v0.0.1035'.

Notes:
  - This utility always branches off the current HEAD of the 'dev' branch.
  - You must run ./setup.sh inside the new clone to initialize its environment.
  - To remove a clone: 'git worktree remove clones/[name]' and 'git branch -d [name]'.
"""

def find_micro_x_root():
    """Finds the absolute path of the 'micro_X' (main) root directory by looking for .git."""
    current = os.path.abspath(__file__)
    while current != os.path.dirname(current):
        current = os.path.dirname(current)
        if os.path.isdir(os.path.join(current, ".git")):
            # If we are in the root that contains .git, but that root is micro_X-dev, 
            # the 'main' root is one level up.
            if os.path.basename(current) == "micro_X-dev":
                return os.path.dirname(current)
            return current
    
    # Fallback to the old logic if .git isn't found (though it should be)
    current = os.path.abspath(__file__)
    current = os.path.dirname(os.path.dirname(current))
    folder_name = os.path.basename(current)
    if folder_name in ["micro_X-dev", "micro_X-testing"]:
        current = os.path.dirname(current)
    return current

def get_next_version_name(source_dir):
    """Reads config/default_config.json and calculates the next patch version."""
    config_path = os.path.join(source_dir, "config", "default_config.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            current_ver = config.get("application", {}).get("version", "0.0.0")
            
            parts = current_ver.split('.')
            if len(parts) >= 3:
                # Increment the patch version (last part)
                parts[-1] = str(int(parts[-1]) + 1)
                new_ver = ".".join(parts)
                return f"clone_v{new_ver}"
            else:
                return f"clone_v{current_ver}_next"
    except Exception as e:
        print(f"Warning: Could not determine version from config at {config_path}: {e}")
        return None

def run_command(cmd, cwd=None):
    """Helper to run shell commands and return output."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing {' '.join(cmd)}: {e.stderr}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Clone the micro_X dev environment using Git worktrees.")
    parser.add_argument("name", nargs="?", default=None, help="Name of the clone/branch (optional).")
    parser.add_argument("--bump", action="store_true", help="Auto-name clone by incrementing the current version.")
    args = parser.parse_args()

    main_root = find_micro_x_root()
    source_dir = os.path.join(main_root, "micro_X-dev")

    if not os.path.isdir(source_dir):
        print(f"Error: Could not locate 'micro_X-dev' directory at '{source_dir}'.")
        sys.exit(1)

    # Handle --bump logic
    if args.bump:
        generated_name = get_next_version_name(source_dir)
        if generated_name:
            args.name = generated_name
            print(f"ℹ️  --bump specified. Using version-based name: '{args.name}'")
        else:
            print("❌ Failed to generate version-based name from config.")
            sys.exit(1)

    # Auto-generate timestamp name if still missing
    if not args.name:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.name = f"clone_{timestamp}"
        print(f"ℹ️  No name provided. Using auto-generated name: '{args.name}'")

    # Determine Destination
    clones_dir = os.path.join(source_dir, "clones")
    dest_dir = os.path.join(clones_dir, args.name)

    if os.path.exists(dest_dir):
        print(f"Error: Destination '{dest_dir}' already exists.")
        sys.exit(1)

    print(f"Branch Name: {args.name}")
    print(f"Destination: {dest_dir}")
    print("Creating Git worktree...")

    # Ensure clones directory exists
    os.makedirs(clones_dir, exist_ok=True)
    
    # Create the worktree and branch in one go from the current 'dev' branch
    run_command(["git", "worktree", "add", "-b", args.name, dest_dir, "dev"], cwd=source_dir)

    print(f"\n✅ Clone created successfully using Git worktree!")
    print(f"   Location: {dest_dir}")
    print(f"   Branch:   {args.name}")
    print(f"\nNext Steps:")
    print(f"1. cd {dest_dir}")
    print(f"2. ./setup.sh  (To create the virtual environment)")
    print(f"3. ./micro_X.sh")

if __name__ == "__main__":
    main()
