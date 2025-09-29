# utils/git_branch.py

import subprocess
import sys

def get_current_branch():
    """Prints the current git branch name."""
    try:
        # Using subprocess.run to capture output
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True  # Raises CalledProcessError if git command fails
        )
        current_branch = result.stdout.strip()
        print(f"Current Git Branch: {current_branch}")
    except FileNotFoundError:
        print("❌ Error: 'git' command not found. Is Git installed and in your PATH?", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # This can happen if not in a git repository
        error_message = e.stderr.strip()
        print(f"❌ Error: Not a git repository or another git error occurred.\n   Details: {error_message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    get_current_branch()

