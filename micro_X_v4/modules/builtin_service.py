# micro_X_v4/modules/builtin_service.py

import asyncio
import subprocess
import shlex
import logging
from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class BuiltinService:
    """
    V2 Builtin Commands Service.
    Handles /exit, /help, /alias, /config etc.
    """
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._on_input)

    async def _on_input(self, event: Event):
        text = event.payload.get('input', "").strip()
        text_lower = text.lower()
        
        # Only handle commands starting with /
        if not text_lower.startswith("/"):
            return

        if text_lower.startswith("/alias"):
            await self.bus.publish(Event(
                type=EventType.ALIAS_COMMAND_RECEIVED,
                payload={'input': text},
                sender="BuiltinService"
            ))
            
        elif text_lower.startswith("/config"):
            await self._handle_config(text)
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

        elif text_lower == "/exit" or text_lower == "/quit":
            logger.info("BuiltinService: Exit requested.")
            await self.bus.publish(Event(EventType.APP_SHUTDOWN))
            # prompt_toolkit app.exit() will be handled by the UI listening for SHUTDOWN or just exiting

    async def _handle_config(self, text: str):
        """Runs utils/config_manager.py"""
        # Determine subcommand
        parts = shlex.split(text)
        args = parts[1:] if len(parts) > 1 else []
        
        # Default to printing help if no args? Or just pass through.
        # utils/config_manager.py handles no args by printing help.
        
        cmd = ["python3", "utils/config_manager.py"] + args
        
        try:
            # We run this as a subprocess. The script handles tmux detaching itself.
            await self.bus.publish(Event(
                type=EventType.EXECUTION_OUTPUT,
                payload={'output': f"⚙️ Running Config Manager: {' '.join(cmd)}"},
                sender="BuiltinService"
            ))
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if stdout:
                await self.bus.publish(Event(
                    type=EventType.EXECUTION_OUTPUT,
                    payload={'output': stdout.decode().strip()},
                    sender="BuiltinService"
                ))
            if stderr:
                await self.bus.publish(Event(
                    type=EventType.EXECUTION_OUTPUT,
                    payload={'output': stderr.decode().strip(), 'is_stderr': True},
                    sender="BuiltinService"
                ))
                
        except Exception as e:
            logger.error(f"Failed to run config manager: {e}")
            await self.bus.publish(Event(
                type=EventType.EXECUTION_ERROR,
                payload={'message': str(e)},
                sender="BuiltinService"
            ))

