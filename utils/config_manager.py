#!/usr/bin/env python3

import argparse
import subprocess
import webbrowser
import os
import time
import socket
import json
import http.server
import socketserver
import threading
from urllib.parse import urlparse, parse_qs
import sys # Added for sys.executable

# --- Configuration ---
TMUX_SESSION_NAME_PREFIX = "microx_config_server_session" # Base prefix
DEFAULT_PORT = 8000
# Path relative to where http.server serves from (project root)
CONFIG_MANAGER_HTML_PATH = "tools/config_manager/index.html"
USER_CONFIG_FILENAME = "user_config.json"
USER_CATEGORIES_FILENAME = "user_command_categories.json"
CONFIG_DIR_NAME = "config" # Relative to project root

# --- Helper Functions ---
def get_project_root():
    """
    Determines the project root. Assumes this script is in 'utils/'
    and the project root is its parent directory.
    If run directly from project root (e.g. for dev), it's os.getcwd().
    """
    script_path = os.path.abspath(__file__)
    if os.path.basename(os.path.dirname(script_path)) == "utils":
        return os.path.dirname(os.path.dirname(script_path))
    return os.getcwd()

def sanitize_branch_name_for_tmux(branch_name: str) -> str:
    """Sanitizes a branch name to be safe for tmux session names."""
    # Tmux session names cannot contain periods, colons, or other special chars.
    # Replace problematic characters with underscores.
    sanitized = "".join(c if c.isalnum() or c == '-' else '_' for c in branch_name)
    return sanitized[:50] # Keep it reasonably short

def get_dynamic_tmux_session_name(branch_name: str) -> str:
    """Constructs a dynamic tmux session name based on the branch."""
    sanitized_branch = sanitize_branch_name_for_tmux(branch_name)
    return f"{TMUX_SESSION_NAME_PREFIX}_{sanitized_branch}"

def is_tmux_session_running(session_name: str) -> bool:
    """Checks if a tmux session with the given name is currently running."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", f"={session_name}"], # Use exact match for session name
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("Error: 'tmux' command not found. Please ensure tmux is installed.")
        return False
    except Exception as e:
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
            continue
    raise OSError(f"Could not find a free port after {max_tries} attempts starting from {start_port}.")

def get_preferred_port_for_branch(branch_name: str, base_default_port: int) -> int:
    """Determines a preferred starting port based on the branch name."""
    sanitized_branch = sanitize_branch_name_for_tmux(branch_name).lower()
    if sanitized_branch == "main":
        return base_default_port
    elif sanitized_branch == "dev":
        return base_default_port + 1
    elif sanitized_branch == "testing":
        return base_default_port + 2
    else: 
        # Simple hash-based offset for other branches to reduce immediate collisions
        hash_val = sum(ord(char) for char in sanitized_branch)
        return base_default_port + 10 + (hash_val % 10) # Offset by 10-19

# --- HTTP Request Handler with Save Functionality ---
class ConfigManagerHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    PROJECT_ROOT_PATH = get_project_root() 

    def do_POST(self):
        """Handles POST requests to save configuration files."""
        parsed_path = urlparse(self.path)
        endpoint = parsed_path.path
        content_length = int(self.headers.get('Content-Length', 0))
        post_data_bytes = self.rfile.read(content_length)
        
        try:
            data_to_save = json.loads(post_data_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Invalid JSON data received."}).encode('utf-8'))
            print("Error: Received invalid JSON data for saving.")
            return

        save_path = None
        filename_for_message = ""

        if endpoint == '/api/save/user_config':
            save_path = os.path.join(self.PROJECT_ROOT_PATH, CONFIG_DIR_NAME, USER_CONFIG_FILENAME)
            filename_for_message = USER_CONFIG_FILENAME
        elif endpoint == '/api/save/user_categories':
            save_path = os.path.join(self.PROJECT_ROOT_PATH, CONFIG_DIR_NAME, USER_CATEGORIES_FILENAME)
            filename_for_message = USER_CATEGORIES_FILENAME
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "Invalid save endpoint."}).encode('utf-8'))
            print(f"Error: Invalid save endpoint '{endpoint}' requested.")
            return

        if save_path:
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f"{filename_for_message} saved successfully to project."}).encode('utf-8'))
                print(f"Successfully saved {filename_for_message} to {save_path}")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": f"Error saving {filename_for_message}: {str(e)}"}).encode('utf-8'))
                print(f"Error writing {filename_for_message} to {save_path}: {e}")

# --- Server Management Functions ---
httpd_instance = None 
server_thread_instance = None 

def start_server_thread(port: int, project_root: str):
    """Starts the HTTP server in a separate thread."""
    global httpd_instance
    class HandlerWithFixedDirectory(ConfigManagerHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=project_root, **kwargs)
            
    httpd_instance = socketserver.TCPServer(("", port), HandlerWithFixedDirectory)
    print(f"micro_X Config Manager server starting on http://localhost:{port}/")
    print(f"Serving files from: {project_root}")
    print(f"Config Manager tool will be at: http://localhost:{port}/{CONFIG_MANAGER_HTML_PATH}")
    httpd_instance.serve_forever()


def start_server_in_tmux(port_preference: int, project_root: str, branch_name: str):
    """Starts the HTTP server in a branch-specific tmux session and opens the browser."""
    dynamic_session_name = get_dynamic_tmux_session_name(branch_name)

    if not os.path.exists(os.path.join(project_root, CONFIG_MANAGER_HTML_PATH)):
        print(f"Error: Config Manager HTML file not found at expected path: {os.path.join(project_root, CONFIG_MANAGER_HTML_PATH)}")
        print("Please ensure the web app (index.html) is located at tools/config_manager/ within the project.")
        return

    if is_tmux_session_running(dynamic_session_name):
        print(f"Server session '{dynamic_session_name}' for branch '{branch_name}' appears to be already running.")
        print("If you need to restart it, please stop it first using:")
        print(f"  /utils config_manager --stop --branch {branch_name}")
        # Attempt to open browser, assuming it's running on a previously determined port for this branch.
        # This is a best-effort guess if port isn't stored.
        url_to_open = f"http://localhost:{port_preference}/{CONFIG_MANAGER_HTML_PATH}" 
        try:
            webbrowser.open_new_tab(url_to_open)
            print(f"Attempted to open Config Manager at: {url_to_open} (assuming server is on preferred port for branch)")
        except Exception as e:
            print(f"Error trying to open browser: {e}")
        return

    try:
        actual_port = find_free_port(port_preference)
    except OSError as e:
        print(f"Error finding free port starting from {port_preference}: {e}")
        return
    
    tmux_internal_command_list = [
        sys.executable, os.path.abspath(__file__),
        "--internal-start-actual-server",
        "--port", str(actual_port),
        "--project-root", project_root,
        "--branch", branch_name # Pass branch for logging within the server script if needed
    ]

    tmux_command_list = [
        "tmux", "new-session", "-d", "-s", dynamic_session_name,
        " ".join(tmux_internal_command_list) 
    ]

    try:
        subprocess.run(tmux_command_list, check=True)
        print(f"Tmux session '{dynamic_session_name}' for branch '{branch_name}' created.")
        print(f"Server is being started on port {actual_port} within that session.")
        
        time.sleep(2) 
        
        url_to_open = f"http://localhost:{actual_port}/{CONFIG_MANAGER_HTML_PATH}"
        try:
            webbrowser.open_new_tab(url_to_open)
            print(f"Opened Config Manager at: {url_to_open}")
        except Exception as e:
            print(f"Error opening web browser: {e}")
            print(f"You can manually navigate to: {url_to_open}")

        print(f"\nTo view server logs: tmux attach-session -t {dynamic_session_name}")
        print(f"To stop this server, run in micro_X: /utils config_manager --stop --branch {branch_name}")

    except FileNotFoundError:
        print("Error: 'tmux' command not found. Please ensure tmux is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error starting tmux session for server: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during server start: {e}")


def stop_server_tmux_session(branch_name: str):
    """Stops the HTTP server by killing its branch-specific tmux session."""
    dynamic_session_name = get_dynamic_tmux_session_name(branch_name)
    if not is_tmux_session_running(dynamic_session_name):
        print(f"Server session '{dynamic_session_name}' for branch '{branch_name}' not found or not running.")
        return

    tmux_command_list = ["tmux", "kill-session", "-t", dynamic_session_name]
    try:
        subprocess.run(tmux_command_list, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Config Manager server session '{dynamic_session_name}' for branch '{branch_name}' stopped successfully.")
    except FileNotFoundError:
        print("Error: 'tmux' command not found.")
    except subprocess.CalledProcessError as e:
        print(f"Error stopping tmux session '{dynamic_session_name}': {e.stderr.decode().strip() if e.stderr else e}")
    except Exception as e:
        print(f"An unexpected error occurred during server stop: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Manage the micro_X Config Manager web server.",
        epilog="Typically called by '/utils config_manager' within micro_X."
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the web server in a new tmux session and open the Config Manager."
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the web server's tmux session."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT, # This will be the base for branch-specific ports
        help=f"Base preferred port for the web server (default: {DEFAULT_PORT}). Actual port may vary by branch."
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="default", # Fallback if micro_X doesn't pass it
        help="The current Git branch name (used for session and port naming). Passed by micro_X."
    )
    parser.add_argument(
        "--internal-start-actual-server",
        action="store_true",
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--project-root",
        type=str,
        help=argparse.SUPPRESS
    )
    
    args = parser.parse_args()

    if args.internal_start_actual_server:
        if not args.project_root:
            print("Error: --project-root is required for --internal-start-actual-server.")
            return
        # The branch name passed to the internal server is mostly for potential logging
        # or if the server itself needed to behave differently based on the branch.
        # The tmux session it runs in is already named with the branch.
        print(f"Internal server starting for branch: {args.branch} on port: {args.port} in project: {args.project_root}")
        ConfigManagerHTTPRequestHandler.PROJECT_ROOT_PATH = args.project_root
        start_server_thread(args.port, args.project_root)
        return

    project_root = get_project_root()
    
    # Determine preferred port based on branch and user's base preference
    preferred_port_for_branch = get_preferred_port_for_branch(args.branch, args.port)

    if args.start:
        start_server_in_tmux(preferred_port_for_branch, project_root, args.branch)
    elif args.stop:
        stop_server_tmux_session(args.branch)
    else:
        parser.print_help(sys.stderr) # Print help to stderr by default for CLI tools
        print(f"\nExample usage from within micro_X (branch will be auto-detected by micro_X):")
        print(f"  /utils config_manager --start")
        print(f"  /utils config_manager --start --port 8010  (8010 becomes base for branch-specific port)")
        print(f"  /utils config_manager --stop")

if __name__ == "__main__":
    main()