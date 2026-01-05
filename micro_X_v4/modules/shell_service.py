# micro_X_v4/modules/shell_service.py

import asyncio
import logging
import os
from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class ShellService:
    """
    V2 Shell Service.
    Responsible for executing system commands and streaming output.
    """
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.subscribe_async(EventType.EXECUTION_REQUESTED, self.execute_command)

    async def execute_command(self, event: Event):
        mode = event.payload.get('mode', 'simple')
        # Only handle simple/local execution
        if mode != 'simple' and mode != 'local':
            return

        cmd = event.payload.get('command')
        if not cmd:
            return

        logger.info(f"ShellService: Executing '{cmd}'")
        
        try:
            # Buffer for error analysis
            stderr_buffer = []

            # We use the system shell to handle things like pipes and expansions
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Set working directory to current or specific if needed
                cwd=os.getcwd()
            )

            # Task to read stdout
            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if line:
                        decoded_line = line.decode().strip()
                        if is_stderr:
                            stderr_buffer.append(decoded_line)
                        
                        await self.bus.publish(Event(
                            type=EventType.EXECUTION_OUTPUT,
                            payload={'output': decoded_line, 'is_stderr': is_stderr},
                            sender="ShellService"
                        ))
                    else:
                        break

            # Run both stdout and stderr readers concurrently
            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, is_stderr=True)
            )

            returncode = await process.wait()
            
            await self.bus.publish(Event(
                type=EventType.EXECUTION_FINISHED,
                payload={'returncode': returncode, 'last_stderr': "\n".join(stderr_buffer[-10:])}, # Pass last 10 lines
                sender="ShellService"
            ))

        except Exception as e:
            logger.error(f"ShellService: Failed to execute '{cmd}': {e}")
            await self.bus.publish(Event(
                type=EventType.EXECUTION_ERROR,
                payload={'message': str(e)},
                sender="ShellService"
            ))
