# micro_X_v2/modules/builtin_service.py

import logging
import sys
from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class BuiltinService:
    """
    V2 Builtin Commands Service.
    Handles /exit, /help, etc.
    """
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._on_input)

    async def _on_input(self, event: Event):
        text = event.payload.get('input', "").strip()
        text_lower = text.lower()
        
        if text_lower.startswith("/alias"):
            await self.bus.publish(Event(
                type=EventType.ALIAS_COMMAND_RECEIVED,
                payload={'input': text},
                sender="BuiltinService"
            ))
            
        elif text_lower == "/exit" or text_lower == "exit":
            logger.info("BuiltinService: Exit requested.")
            await self.bus.publish(Event(EventType.APP_SHUTDOWN))
            # prompt_toolkit app.exit() will be handled by the UI listening for SHUTDOWN or just exiting

