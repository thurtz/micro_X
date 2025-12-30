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
        text = event.payload.get('input', "").strip().lower()
        
        if text.startswith("/alias"):
             # For now, just a placeholder message
            await self.bus.publish(Event(
                type=EventType.EXECUTION_OUTPUT,
                payload={'output': "ℹ️ Alias management not yet implemented in V2 UI (but loading works)."},
                sender="BuiltinService"
            ))
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
            
        elif text == "/exit" or text == "exit":
            logger.info("BuiltinService: Exit requested.")
            await self.bus.publish(Event(EventType.APP_SHUTDOWN))
            # prompt_toolkit app.exit() will be handled by the UI listening for SHUTDOWN or just exiting
            
        elif text == "/help" or text == "help":
            help_text = (
                "\n📚 micro_X V2 Help:\n"
                "  /ls, /pwd...    - Run shell commands directly.\n"
                "  <any text>      - AI will translate to a command.\n"
                "  /help           - Show this message.\n"
                "  /exit           - Quit micro_X.\n"
            )
            await self.bus.publish(Event(
                type=EventType.EXECUTION_OUTPUT,
                payload={'output': help_text},
                sender="BuiltinService"
            ))
            # Signal that we are done with this input
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

