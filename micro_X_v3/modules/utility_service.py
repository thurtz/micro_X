# micro_X_v2/modules/utility_service.py

import logging
import asyncio
import shlex
import os
import sys
from ..core.events import EventBus, Event, EventType
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class UtilityService:
    """
    V2 Utility Service.
    Executes external utility scripts (snapshot, tree, dev, etc.)
    """
    
    # Map command -> (script_path, needs_args)
    # Paths are relative to project root
    UTILITY_MAP = {
        "/snapshot": ("utils/generate_snapshot.py", True),
        "/tree": ("utils/generate_tree.py", True),
        "/update": ("utils/update.py", False),
        "/dev": ("utils/dev.py", True),
        "/list": ("utils/list_scripts.py", True),
        "/logs": ("utils/logs.py", True),
        "/setup_brew": ("utils/setup_brew.py", True),
        "/test": ("utils/run_tests.py", True),
        "/ollama_cli": ("utils/ollama_cli.py", True),
        "/command": ("utils/command.py", True),
        "/docs": ("utils/docs.py", True),
        "/knowledge": ("utils/knowledge.py", True),
        "/history_cli": ("utils/history.py", True) # Renamed to avoid conflict with internal /history
    }

    def __init__(self, bus: EventBus, config: ConfigManager):
        self.bus = bus
        self.config = config
        self.bus.subscribe_async(EventType.EXECUTION_REQUESTED, self._on_execution)

    async def direct_run(self, util_name: str, args: list):
        """Direct method for agents to run utilities."""
        cmd = f"/{util_name}" if not util_name.startswith("/") else util_name
        
        if cmd in self.UTILITY_MAP:
            script, allow_args = self.UTILITY_MAP[cmd]
            await self._run_script(script, args)
        else:
            logger.warning(f"UtilityService: Unknown utility '{util_name}'")

    async def _on_execution(self, event: Event):
        # We check if the requested command is a utility
        full_cmd = event.payload.get('command', "").strip()
        parts = full_cmd.split()
        if not parts: return
        
        cmd = parts[0].lower()
        if not cmd.startswith("/"):
            cmd = "/" + cmd # Normalize ls -> /ls for lookup if needed? No, utilities start with /
        
        # Handle generic /utils wrapper
        if cmd == "/utils" and len(parts) > 1:
            script_name = parts[1]
            lookup_cmd = f"/{script_name}"
            if lookup_cmd in self.UTILITY_MAP:
                script, allow_args = self.UTILITY_MAP[lookup_cmd]
                args = parts[2:] if allow_args else []
                await self._run_script(script, args)
                # Signal finished is implicit? No, we should probably output.
            else:
                pass # Not a known utility
            return

        if cmd in self.UTILITY_MAP:
            script, allow_args = self.UTILITY_MAP[cmd]
            args = parts[1:] if allow_args else []
            await self._run_script(script, args)
            # EXECUTION_FINISHED is published by _run_script logic or should be?
            # _run_script does not publish FINISHED. It waits.
            # But the ShellService also listens to EXECUTION_REQUESTED.
            # We need to make sure ShellService DOESN'T run it if we do.
            # Or we ensure LogicEngine sets a mode?

    async def _run_script(self, script_rel_path: str, args: list):
        base_dir = self.config.get_base_dir()
        script_path = os.path.join(base_dir, script_rel_path)
        
        logger.debug(f"UtilityService: Looking for script at {script_path}")
        if not os.path.exists(script_path):
            logger.error(f"UtilityService: Script NOT FOUND at {script_path}")
            await self._error(f"Script not found: {script_rel_path}")
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
            return

        cmd = [sys.executable, script_path] + args
        
        try:
            logger.info(f"UtilityService: Launching subprocess: {' '.join(cmd)}")
            await self._output(f"⚙️ Executing: {' '.join(cmd)}")
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=base_dir # Run from root
            )
            
            # Stream output? Or wait? 
            # For utilities like snapshot/tree, output is fast.
            # For /dev update, might be slow. Streaming is better.
            
            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if line:
                        await self.bus.publish(Event(
                            type=EventType.EXECUTION_OUTPUT,
                            payload={'output': line.decode().strip(), 'is_stderr': is_stderr},
                            sender="UtilityService"
                        ))
                    else:
                        break

            await asyncio.gather(
                read_stream(proc.stdout),
                read_stream(proc.stderr, True)
            )
            
            await proc.wait()
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
            
        except Exception as e:
            logger.error(f"Utility execution failed: {e}")
            await self._error(str(e))

    async def _output(self, text):
        await self.bus.publish(Event(
            type=EventType.EXECUTION_OUTPUT,
            payload={'output': text},
            sender="UtilityService"
        ))

    async def _error(self, text):
        await self.bus.publish(Event(
            type=EventType.EXECUTION_ERROR,
            payload={'message': text},
            sender="UtilityService"
        ))
