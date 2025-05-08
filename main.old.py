# main.py

import os
import pty
import select
import tty
import termios
import sys
import signal
import fcntl
import struct
import subprocess
import uuid
import shlex
from modules import ai_interpreter
from modules import tmux_handler  # We might not directly use the function now

def append_output(output):
    """Simple output function for demonstration."""
    sys.stdout.write(output + "\n")
    sys.stdout.flush()

if __name__ == "__main__":
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    # Save original terminal settings
    old_settings = termios.tcgetattr(stdin_fd)

    def sigwinch_handler(signum, frame):
        """Handle window resize events."""
        if child_pid > 0:
            rows, cols = os.popen('stty size', 'r').read().split()
            fcntl.ioctl(master_fd, tty.TIOCSWINSZ,
                        struct.pack('hhhh', int(rows), int(cols), 0, 0))

    try:
        tty.setraw(stdin_fd)
        tty.setcbreak(stdin_fd)
        signal.signal(signal.SIGWINCH, sigwinch_handler)

        global child_pid, master_fd, command_buffer
        child_pid, master_fd = pty.fork()
        command_buffer = ""

        if child_pid == 0:
            # In child process: run the shell
            os.execvp("/bin/bash", ["/bin/bash"])
        else:
            # Parent process: intercept input and handle /ai in tmux
            try:
                while True:
                    rlist, _, _ = select.select([stdin_fd, master_fd], [], [])
                    if stdin_fd in rlist:
                        char_bytes = os.read(stdin_fd, 1)
                        if not char_bytes:
                            break
                        char = char_bytes.decode()
                        command_buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

                        if char == '\n':
                            command = command_buffer.strip()
                            command_buffer = "" # Clear buffer

                            if command.startswith("/ai "):
                                human_query = command[4:].strip()
                                linux_command = ai_interpreter.interpret_human_input(human_query, master_fd, stdout_fd)
                                if linux_command:
                                    try:
                                        unique_id = str(uuid.uuid4())[:8]
                                        window_name = f"ai_cmd-{unique_id}"
                                        tmux_command = ["tmux", "new-window", "-n", window_name, linux_command]
                                        subprocess.run(tmux_command)
                                    except FileNotFoundError:
                                        append_output("Error: tmux not found.")
                                    except Exception as e:
                                        append_output(f"Error launching in tmux: {e}")
                            else:
                                os.write(master_fd, command.encode() + b'\n') # Send regular commands to child shell

                    if master_fd in rlist:
                        output_data = os.read(master_fd, 1024)
                        if not output_data:
                            break
                        os.write(stdout_fd, output_data)
            except Exception as e:
                append_output(f"Error in main loop: {e}")
            finally:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
                os.waitpid(child_pid, 0)

    except Exception as e:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
        append_output(f"Error in PTY setup: {e}")

    else:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    pass