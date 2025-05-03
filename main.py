# main.py

import os
import pty
import select
import tty
import termios
import sys
import signal

def spawn_shell(shell_path="/bin/bash"):
    """Spawn a shell in a PTY and connect it to the current terminal."""
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    # Save original terminal settings
    old_settings = termios.tcgetattr(stdin_fd)

    def sigwinch_handler(signum, frame):
        """Handle window resize events."""
        if child_pid > 0:
            rows, cols = os.popen('stty size', 'r').read().split()
            import fcntl, struct
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
            os.execvp(shell_path, [shell_path])

        else:
            # Parent process: forward input and output
            sigwinch_handler(None, None)  # set initial window size
            while True:
                rlist, _, _ = select.select([stdin_fd, master_fd], [], [])
                if stdin_fd in rlist:
                    input_data = os.read(stdin_fd, 1024)
                    if not input_data:
                        break
                    os.write(master_fd, input_data)
                if master_fd in rlist:
                    output_data = os.read(master_fd, 1024)
                    if not output_data:
                        break
                    os.write(stdout_fd, output_data)

    except Exception as e:
        os.write(stderr_fd, f"\n❌ Error in PTY shell: {e}\n".encode())

    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    spawn_shell()