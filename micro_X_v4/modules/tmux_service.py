# micro_X_v4/modules/tmux_service.py

import asyncio
import logging
import shutil
import subprocess
from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class TmuxService:
    """
    Handles execution of commands in tmux windows.
    """
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.subscribe_async(EventType.EXECUTION_REQUESTED, self.execute_if_tmux)

    async def execute_if_tmux(self, event: Event):
        mode = event.payload.get('mode', 'local')
        cmd = event.payload.get('command')
        
        if mode not in ['semi_interactive', 'interactive_tui']:
            return

        logger.info(f"TmuxService: executing '{cmd}' in mode {mode}")

        if not shutil.which("tmux"):
            await self.bus.publish(Event(
                EventType.EXECUTION_ERROR, 
                payload={'message': "tmux not installed."}, 
                sender="TmuxService"
            ))
            return

        # Strategy:
        # interactive_tui -> new-window with the command
        # semi_interactive -> new-window with command; read;
        
        tmux_cmd = ["tmux", "new-window", "-n", f"micro_X:{cmd[:10]}"]
        
        if mode == 'semi_interactive':
            # Keep window open after command finishes
            shell_cmd = f"{cmd}; echo '\n[micro_X] Command finished. Press Enter to close.'; read"
            tmux_cmd.append(shell_cmd)
        else:
            # interactive_tui (vim, htop) - let tmux handle lifecycle
            tmux_cmd.append(cmd)

        try:
            process = await asyncio.create_subprocess_exec(*tmux_cmd)
            await process.wait()
            
            # Since it runs in a separate window, we assume success once the new-window command returns
            # The actual command runs async in tmux.
            
            await self.bus.publish(Event(
                EventType.EXECUTION_OUTPUT,
                payload={'output': f"[Launched in tmux: {cmd}]"},
                sender="TmuxService"
            ))
            
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

        except Exception as e:
            logger.error(f"Tmux launch failed: {e}")
            await self.bus.publish(Event(
                EventType.EXECUTION_ERROR,
                payload={'message': str(e)},
                sender="TmuxService"
            ))
