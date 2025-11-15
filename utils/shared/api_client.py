# utils/shared/api_client.py

import os
import socket
import json
import sys

def get_input(prompt: str) -> str:
    """
    Prompts the user for input from within a micro_X script.

    This function communicates with the main micro_X shell to temporarily
    take control of the input field, display the given prompt, and wait
    for the user to submit their input.

    Args:
        prompt: The message to display to the user.

    Returns:
        The string entered by the user.
    """
    socket_path = os.environ.get("MICROX_API_SOCKET")
    if not socket_path:
        # Fallback for running scripts outside of micro_X, or if the API is not available
        print(f"API CLIENT (fallback): {prompt}", file=sys.stderr)
        return sys.stdin.readline().strip()

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client_socket:
            client_socket.connect(socket_path)

            # Send the request to the shell engine
            request = {
                "type": "get_input",
                "prompt": prompt
            }
            client_socket.sendall(json.dumps(request).encode('utf-8'))

            # Wait for the response from the shell engine
            response_data = client_socket.recv(4096).decode('utf-8')
            response = json.loads(response_data)

            if response.get("status") == "ok":
                return response.get("value", "")
            else:
                # Handle potential errors reported by the shell engine
                error_message = response.get("error", "Unknown error from API.")
                print(f"API CLIENT ERROR: {error_message}", file=sys.stderr)
                return ""

    except (ConnectionRefusedError, FileNotFoundError):
        print("API CLIENT ERROR: Could not connect to the micro_X shell API socket.", file=sys.stderr)
        print("Please ensure you are running this script from within micro_X.", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"API CLIENT EXCEPTION: An unexpected error occurred: {e}", file=sys.stderr)
        return ""
