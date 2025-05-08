# modules/tmux_handler.py

import subprocess
import sys
import time

def execute_in_tmux(command):
    """Executes a given command in a new tmux window (debugging attempt)."""
    try:
        tmux_command = [
            "tmux", "new-window",
            "-n", "ai_command",
            command
        ]
        process = subprocess.Popen(tmux_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.1)  # Give tmux a moment to start

        if process.poll() is not None:
            stdout, stderr = process.communicate()
            sys.stdout.write(f"Error launching command in tmux (exit code {process.returncode}):\n{stderr}\n")
            sys.stdout.flush()
            return False
        return True
    except FileNotFoundError:
        sys.stdout.write("Error: tmux not found. Please ensure tmux is installed.\n")
        sys.stdout.flush()
        return False
    except Exception as e:
        sys.stdout.write(f"Error launching command in tmux: {e}\n")
        sys.stdout.flush()
        return False
    return True