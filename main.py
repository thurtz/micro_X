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
from modules import ai_interpreter

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

        global child_pid, master_fd
        child_pid, master_fd = pty.fork()

        if child_pid == 0:
            # In child process: replace with shell
            os.execvp("/bin/bash", ["/bin/bash"])
        else:
            # Parent process: forward input and output, and handle /ai
            try:
                while True:
                    rlist, _, _ = select.select([stdin_fd, master_fd], [], [])
                    if stdin_fd in rlist:
                                            char_bytes = os.read(stdin_fd, 1)
                                            if not char_bytes:
                                                break
                                            char = char_bytes.decode()

                                            global command_buffer
                                            if not 'command_buffer' in globals():
                                                command_buffer = ""

                                            if command_buffer == "" and char == '/':
                                                command_buffer += char
                                                sys.stdout.write(char)  # Explicitly echo '/'
                                                sys.stdout.flush()
                                            elif command_buffer.startswith('/'):
                                                command_buffer += char
                                                sys.stdout.write(char)  # Explicitly echo typed characters
                                                sys.stdout.flush()
                                                if char == '\r': # Enter key
                                                    # Process the buffer
                                                    if command_buffer.startswith('/ai '):
                                                        human_query = command_buffer[4:].strip()
                                                        ai_interpreter.interpret_human_input(human_query, master_fd, stdout_fd)
                                                        print(f"DEBUG: Sent command for: {human_query}") # Keep this for now
                                                    command_buffer = "" # Clear buffer
                                            else:
                                                os.write(master_fd, char_bytes) # Echo normal commands via PTY
                                                if char == '\r':
                                                    command_buffer = "" # Clear buffer on Enter for normal commands

                    if master_fd in rlist:
                        output_data = os.read(master_fd, 1024)
                        if not output_data:
                            break
                        # Filter out extra newline characters (might be too aggressive)
                        #cleaned_output = output_data.replace(b'\n\n', b'\n')
                        #os.write(stdout_fd, cleaned_output)
                        os.write(stdout_fd, output_data)
            except OSError as e:
                if e.errno != 5:
                    os.write(stderr_fd, f"\n❌ OSError: {e}\n".encode())
            finally:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
                os.waitpid(child_pid, 0)

    except Exception as e:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
        os.write(stderr_fd, f"\n❌ Error in PTY shell: {e}\n".encode())

    else:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    pass # The PTY logic is now inline