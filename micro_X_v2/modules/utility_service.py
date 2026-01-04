# micro_X_v2/modules/utility_service.py

import logging
import asyncio
import shlex
import os
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
        "/ollama_cli": ("utils/ollama_cli.py", True) # Renamed to avoid conflict with /ollama intent
    }

    def __init__(self, bus: EventBus, config: ConfigManager):
        self.bus = bus
        self.config = config
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._on_input)

    async def _on_input(self, event: Event):
        text = event.payload.get('input', "").strip()
        parts = text.split()
        if not parts: return
        
        cmd = parts[0].lower()
        
        # Special handling for /ollama intent vs cli
        # If user types /ollama, IntentService might map it to /ollama status/start/stop.
        # But if they type /ollama arguments, we might want the CLI.
        # V1 alias: /ollama -> /utils ollama_cli
        # So we should look for /utils ollama_cli or /ollama_cli if we want to be strict.
        # For now, let's stick to the mapped aliases.
        
        if cmd in self.UTILITY_MAP:
            script, allow_args = self.UTILITY_MAP[cmd]
            args = parts[1:] if allow_args else []
            await self._run_script(script, args)
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

    async def _run_script(self, script_rel_path: str, args: list):
        base_dir = self.config.get_base_dir()
        script_path = os.path.join(base_dir, script_rel_path)
        
        if not os.path.exists(script_path):
            await self._error(f"Script not found: {script_path}")
            return

        cmd = ["python3", script_path] + args
        
        try:
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
