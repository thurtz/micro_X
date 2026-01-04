# micro_X_v2/modules/history_service.py

import os
import logging
from typing import List
from prompt_toolkit.history import FileHistory
from ..core.events import EventBus, Event, EventType
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class HistoryService:
    """
    Manages command history persistence and viewing.
    Uses prompt_toolkit's FileHistory for compatibility.
    """
    def __init__(self, bus: EventBus, config: ConfigManager):
        self.bus = bus
        self.config = config
        
        base_dir = self.config.get_base_dir()
        self.history_file = os.path.join(base_dir, "config", ".history")
        
        # We use prompt_toolkit's helper to manage the file easily
        self.pt_history = FileHistory(self.history_file)
        
        # Subscribe
        self.bus.subscribe_async(EventType.EXECUTION_REQUESTED, self._on_execution)
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._on_input)

    async def _on_execution(self, event: Event):
        """Append executed commands to history."""
        cmd = event.payload.get('command', "")
        if cmd:
            self.pt_history.append_string(cmd)

    async def _on_input(self, event: Event):
        """Handle /history command."""
        text = event.payload.get('input', "").strip().lower()
        if text == "/history":
            await self._show_history()
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

    async def _show_history(self):
        # prompt_toolkit FileHistory returns strings NEWEST first.
        all_strings = list(self.pt_history.load_history_strings())
        total_count = len(all_strings)
        
        # Take the 20 most recent entries
        num_to_show = min(total_count, 20)
        recent = all_strings[:num_to_show]
        
        # Reverse them to get chronological order (oldest to newest)
        recent.reverse()
        
        output = f"\n📜 Command History (Showing last {num_to_show} of {total_count}):\n"
        start_index = total_count - num_to_show
        
        for i, item in enumerate(recent):
            global_index = start_index + i + 1
            output += f"  {global_index:>4}. {item}\n"
            
        await self.bus.publish(Event(
            type=EventType.EXECUTION_OUTPUT,
            payload={'output': output},
            sender="HistoryService"
        ))
    
    def get_pt_history(self):
        return self.pt_history
