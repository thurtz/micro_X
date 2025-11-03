# modules/native_shell_processor.py

import asyncio
import logging
import os
import pty
import sys
import shutil
import tty
import termios
import fcntl
import signal

logger = logging.getLogger(__name__)

class NativeShellProcessor:
    """
    The main class for handling the 'native' shell integration mode.
    This mode wraps a real shell (like bash) in a PTY and injects AI
    features, rather than simulating a shell in a TUI.
    """
    def __init__(self, config, ai_handler_module, ollama_manager_module, embedding_manager_instance):
        self.config = config
        self.ai_handler = ai_handler_module
        self.ollama_manager = ollama_manager_module
        self.embedding_manager = embedding_manager_instance
        self.shell = shutil.which("bash") or "/bin/sh"
        self.processing_lock = asyncio.Lock()
        logger.info(f"NativeShellProcessor initialized, using shell: {self.shell}")

    async def _handle_ai_confirmation(self, suggested_command: str, original_command: str, stdin_reader: asyncio.StreamReader, master_fd: int) -> str | None:
        """Get user confirmation for an AI-suggested command."""
        
        explained = False
        while True:
            options = "[Y]es / [N]o / [M]odify"
            if not explained:
                options += " / [E]xplain"

            prompt = f"\r\n[AI]: {suggested_command}\r\nExecute? {options} "
            sys.stdout.buffer.write(prompt.encode())
            sys.stdout.flush()

            user_char = await stdin_reader.read(1)
            user_char_lower = user_char.lower()

            if user_char_lower == b'y':
                sys.stdout.buffer.write(b'Yes\r\n')
                sys.stdout.flush()
                return suggested_command
            elif user_char_lower == b'n':
                sys.stdout.buffer.write(b'No\r\n')
                sys.stdout.flush()
                return original_command
            elif user_char_lower == b'm':
                sys.stdout.buffer.write(b'Modify\r\n')
                # Safest approach: Just print the command and let the user re-type or copy it.
                modify_prompt = f"\r\nTo modify, re-type or copy the command below:\r\n{suggested_command}\r\n"
                sys.stdout.buffer.write(modify_prompt.encode())
                sys.stdout.flush()
                return None # Signal that no further execution should happen
            elif user_char_lower == b'e' and not explained:
                sys.stdout.buffer.write(b'Explain\r\n')
                sys.stdout.flush()
                
                explanation = await self.ai_handler.explain_linux_command_with_ai(
                    suggested_command, self.config, lambda x, **kwargs: None
                )
                if explanation:
                    explanation_text = f"\r\n--- AI Explanation ---\r\n{explanation}\r\n----------------------\r\n"
                    sys.stdout.buffer.write(explanation_text.encode())
                    sys.stdout.flush()
                else:
                    sys.stdout.buffer.write(b"\r\nSorry, could not get an explanation.\r\n")
                    sys.stdout.flush()
                
                explained = True

    async def _process_intercepted_command(self, command_text: str, master_fd: int, stdin_reader: asyncio.StreamReader):
        """Processes the intercepted command text, applying AI logic."""
        async with self.processing_lock:
            logger.info(f"[INTERCEPTED]: {command_text}")

            if command_text.strip().lower() in ["exit", "quit"]:
                os.write(master_fd, command_text.encode() + b'\n')
                return

            # Default to executing the user's original command
            final_command_to_run = command_text
            linux_command = None

            if await self.ollama_manager.is_ollama_server_running():
                linux_command, _ = await self.ai_handler.get_validated_ai_command(
                    command_text, self.config, lambda x, **kwargs: None, lambda: None
                )

            if linux_command and linux_command != command_text:
                # AI has a suggestion, enter confirmation flow
                decision = await self._handle_ai_confirmation(linux_command, command_text, stdin_reader, master_fd)
                
                if decision is None: # This is the 'Modify' case
                    # We have already printed the suggestion to the user.
                    # Now, send a newline to the PTY to get a fresh prompt.
                    os.write(master_fd, b'\n')
                    return # End processing for this command
                else:
                    # User chose Yes or No, so we'll execute their choice.
                    final_command_to_run = decision
            
            # Execute the determined command (either original, or AI-approved)
            os.write(master_fd, final_command_to_run.encode() + b'\n')


    async def run(self):
        """ Main entry point and run loop for the native shell mode. """
        logger.info("Starting native shell mode...")
        
        pid, master_fd = pty.fork()

        if pid == pty.CHILD:
            argv = [self.shell]
            env = os.environ.copy()
            os.execve(self.shell, argv, env)
        else:
            logger.info(f"Parent process managing child PID: {pid} with PTY master fd: {master_fd}")
            
            original_termios = termios.tcgetattr(sys.stdin.fileno())
            
            try:
                tty.setraw(sys.stdin.fileno())

                def handle_resize(signum, frame):
                    rows, cols = shutil.get_terminal_size()
                    winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b'\0'*8)
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                    logger.debug(f"Terminal resized to {rows}x{cols}. Propagated to PTY.")

                loop = asyncio.get_running_loop()
                loop.add_signal_handler(signal.SIGWINCH, handle_resize, None, None)
                handle_resize(None, None)

                stdin_reader = asyncio.StreamReader()
                protocol = asyncio.StreamReaderProtocol(stdin_reader)
                await loop.connect_read_pipe(lambda: protocol, sys.stdin)

                async def user_to_pty(reader: asyncio.StreamReader):
                    line_buffer = bytearray()
                    while not reader.at_eof():
                        data = await reader.read(1)
                        if not data:
                            continue

                        if data in (b'\r', b'\n'):
                            sys.stdout.buffer.write(b'\r\n')
                            sys.stdout.flush()

                            command_text = line_buffer.decode(errors='ignore').strip()
                            line_buffer.clear()
                            
                            if command_text:
                                await self._process_intercepted_command(command_text, master_fd, reader)
                            else:
                                os.write(master_fd, b'\n')

                        elif data in (b'\x7f', b'\b'):
                            if line_buffer:
                                line_buffer.pop()
                                sys.stdout.buffer.write(b'\b \b')
                                sys.stdout.flush()
                        
                        elif data >= b' ' and data <= b'~':
                            line_buffer.extend(data)
                            sys.stdout.buffer.write(data)
                            sys.stdout.flush()

                async def pty_to_user():
                    pty_reader = asyncio.StreamReader()
                    protocol = asyncio.StreamReaderProtocol(pty_reader)
                    await loop.connect_read_pipe(lambda: protocol, os.fdopen(master_fd, 'rb', 0))

                    while not pty_reader.at_eof():
                        data = await pty_reader.read(1024)
                        if not data: break
                        sys.stdout.buffer.write(data)
                        sys.stdout.flush()

                user_input_task = loop.create_task(user_to_pty(stdin_reader))
                pty_output_task = loop.create_task(pty_to_user())

                await loop.run_in_executor(None, os.waitpid, pid, 0)

            finally:
                loop.remove_signal_handler(signal.SIGWINCH)
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, original_termios)
                logger.info("Restored original terminal settings.")

            logger.info("Native shell mode session ended.")
