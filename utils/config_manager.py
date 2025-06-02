#!/usr/bin/env python3

import argparse
import subprocess
import webbrowser
import os
import time
import socket

TMUX_SESSION_NAME = "microx_config_server_session"
DEFAULT_PORT = 8000
# This path is relative to the project root, where the http.server will be serving from.
CONFIG_MANAGER_HTML_PATH = "tools/config_manager/index.html" 

def get_project_root():
    """
    Utility scripts are typically run with their CWD set to the project root
    by micro_X's ShellEngine.
    """
    return os.getcwd()

def is_tmux_session_running(session_name: str) -> bool:
    """Checks if a tmux session with the given name is currently running."""
    try:
        # The command 'tmux has-session -t session_name' exits with 0 if session exists, 1 otherwise.
        # We capture output to prevent it from printing to micro_X's UI directly from here.
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            check=False, # Don't raise exception on non-zero exit
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        # This means tmux itself is not installed or not in PATH.
        # The calling functions should handle this by printing an error.
        return False
    except Exception as e:
        # Other potential errors during subprocess execution.
        print(f"Error checking tmux session '{session_name}': {e}")
        return False

def find_free_port(start_port: int, max_tries: int = 100) -> int:
    """Attempts to find a free port, starting from start_port."""
    for i in range(max_tries):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            return port
        except OSError:
            # Port is likely in use
            continue
    raise OSError(f"Could not find a free port after {max_tries} attempts starting from {start_port}.")


def start_server(port_preference: int, project_root: str):
    """Starts the HTTP server in a tmux session and opens the browser."""
    if not os.path.exists(os.path.join(project_root, CONFIG_MANAGER_HTML_PATH)):
        print(f"Error: Config Manager HTML file not found at expected path: {os.path.join(project_root, CONFIG_MANAGER_HTML_PATH)}")
        print(f"Please ensure the web app is built and located at tools/config_manager/index.html within the project.")
        return

    if is_tmux_session_running(TMUX_SESSION_NAME):
        print(f"Server may already be running in tmux session '{TMUX_SESSION_NAME}'.")
        # We don't know for sure which port it's on if it was started with a different --port last time.
        # For simplicity, we'll try to open the browser to the preferred port.
        # A more robust solution might store the active port if micro_X needs to manage it more closely.
        print(f"Attempting to open browser for preferred port {port_preference}...")
        url_to_open = f"http://localhost:{port_preference}/{CONFIG_MANAGER_HTML_PATH}"
        try:
            webbrowser.open_new_tab(url_to_open)
            print(f"If server is running on port {port_preference}, Config Manager should now be open at: {url_to_open}")
        except Exception as e:
            print(f"Error trying to open browser: {e}")
        return

    try:
        actual_port = find_free_port(port_preference)
    except OSError as e:
        print(f"Error: {e}")
        return

    # The http.server serves files from its Current Working Directory.
    # Since ShellEngine runs this script with CWD as project_root, this is correct.
    # If running this script manually, ensure you are in the project root.
    server_command = ["python3", "-m", "http.server", str(actual_port)]
    
    # Command to execute within tmux: cd to project root, then start server.
    # This ensures http.server serves from the correct base directory.
    # Note: Using `shlex.quote` is safer for paths if they could contain spaces,
    # but project_root here should be okay.
    full_tmux_internal_command = f"cd {project_root} && {' '.join(server_command)}"

    tmux_command_list = [
        "tmux", "new-session", "-d", "-s", TMUX_SESSION_NAME,
        full_tmux_internal_command
    ]

    try:
        subprocess.run(tmux_command_list, check=True, cwd=project_root) # cwd might be redundant here but good practice
        print(f"Config Manager server started in tmux session '{TMUX_SESSION_NAME}' on port {actual_port}.")
        print(f"Serving files from: {project_root}")
        
        # Give the server a moment to initialize
        time.sleep(1.5) 
        
        url_to_open = f"http://localhost:{actual_port}/{CONFIG_MANAGER_HTML_PATH}"
        try:
            webbrowser.open_new_tab(url_to_open)
            print(f"Opened Config Manager at: {url_to_open}")
        except Exception as e:
            print(f"Error opening web browser: {e}")
            print(f"You can manually navigate to: {url_to_open}")

        print(f"\nTo view server logs (if any): tmux attach-session -t {TMUX_SESSION_NAME}")
        print(f"To stop the server, run in micro_X: /utils config_manager --stop")

    except FileNotFoundError:
        print("Error: 'tmux' command not found. Please ensure tmux is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error starting tmux session for server: {e}")
        print("This might happen if a session with the same name already exists but is in an odd state, or if the server command failed.")
    except Exception as e:
        print(f"An unexpected error occurred during server start: {e}")

def stop_server():
    """Stops the HTTP server by killing its tmux session."""
    if not is_tmux_session_running(TMUX_SESSION_NAME):
        print(f"Server session '{TMUX_SESSION_NAME}' not found or not running.")
        return

    tmux_command_list = ["tmux", "kill-session", "-t", TMUX_SESSION_NAME]
    try:
        subprocess.run(tmux_command_list, check=True)
        print(f"Config Manager server session '{TMUX_SESSION_NAME}' stopped successfully.")
    except FileNotFoundError:
        print("Error: 'tmux' command not found. Please ensure tmux is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error stopping tmux session '{TMUX_SESSION_NAME}': {e}")
        print("It's possible the session was already closed or an issue occurred with tmux.")
    except Exception as e:
        print(f"An unexpected error occurred during server stop: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Manage the micro_X Config Manager web server.",
        epilog="This script is typically called by the '/utils config_manager' command within micro_X."
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the web server in a new tmux session and open the Config Manager in a browser."
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the web server's tmux session."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to use for the web server (default: {DEFAULT_PORT}). If port is in use, it will try the next available one."
    )
    
    # This script relies on being run from the project root.
    # If sys.argv has other args from micro_X that are not for this script,
    # argparse might complain. For now, assuming only args meant for this script are passed.
    args = parser.parse_args()

    project_root = get_project_root()

    if not os.path.exists(os.path.join(project_root, "tools", "config_manager", "index.html")):
        print("Warning: The Config Manager HTML file (tools/config_manager/index.html) does not seem to exist.")
        print("The server might start, but the page won't be found.")
        # Optionally, you could prevent starting if the file is missing.

    if args.start:
        start_server(args.port, project_root)
    elif args.stop:
        stop_server()
    else:
        # If no specific action is given, print help.
        # This is useful if a user tries to run '/utils config_manager' without args.
        parser.print_help()
        print(f"\nExample usage from within micro_X:")
        print(f"  /utils config_manager --start")
        print(f"  /utils config_manager --start --port 8080")
        print(f"  /utils config_manager --stop")

if __name__ == "__main__":
    main()