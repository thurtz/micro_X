# micro_X_v2/modules/git_context_service.py

import logging
import asyncio
import subprocess
import shutil
from ..core.events import EventBus, Event, EventType
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class GitContextService:
    """
    Checks git branch and status.
    Enforces integrity checks for protected branches.
    """
    def __init__(self, bus: EventBus, config: ConfigManager):
        self.bus = bus
        self.config = config
        self.current_branch = "unknown"
        
        self.bus.subscribe_async(EventType.APP_STARTED, self._on_start)
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._on_input)

    async def _on_start(self, event: Event):
        if not shutil.which("git"):
            return

        try:
            # Get branch
            proc = await asyncio.create_subprocess_shell(
                "git rev-parse --abbrev-ref HEAD",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            self.current_branch = stdout.decode().strip()
            
            # Broadcast branch info? Or just log
            logger.info(f"GitContext: Current branch is '{self.current_branch}'")
            
            # Check integrity
            await self._check_integrity()
            
        except Exception as e:
            logger.error(f"GitContext check failed: {e}")

    async def _check_integrity(self):
        protected = self.config.get("integrity_check.protected_branches", ["main", "testing"])
        
        if self.current_branch in protected:
            # Check for modifications
            proc = await asyncio.create_subprocess_shell(
                "git status --porcelain",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if stdout:
                msg = f"⚠️ WARNING: You are on protected branch '{self.current_branch}' with uncommitted changes."
                await self.bus.publish(Event(
                    type=EventType.EXECUTION_OUTPUT,
                    payload={'output': msg, 'is_stderr': True},
                    sender="GitContext"
                ))
                # Optional: Halt if configured
                if self.config.get("integrity_check.halt_on_integrity_failure", False):
                     pass # For V2 prototype, just warn.

    async def _on_input(self, event: Event):
        text = event.payload.get('input', "").strip().lower()
        if text == "/git_branch":
            await self.bus.publish(Event(
                type=EventType.EXECUTION_OUTPUT,
                payload={'output': f"🌿 Current Branch: {self.current_branch}"},
                sender="GitContext"
            ))
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
