# micro_X_v2/main.py

import asyncio
import logging
import sys
import os

from .core.events import EventBus, Event, EventType
from .core.state import StateManager, AppState
from .core.config import ConfigManager
from .ui.app import V2UIManager
from .modules.ollama_service import OllamaService
from .modules.shell_service import ShellService
from .modules.builtin_service import BuiltinService
from .modules.category_manager import CategoryManager
from .modules.alias_manager import AliasManager
from .modules.tmux_service import TmuxService
from .modules.rag_service import RagService

# Configure Logging
logging.basicConfig(filename='v2.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LogicEngine:
    """Handles the translation logic and execution requests."""
    def __init__(self, bus: EventBus, state_manager: StateManager, ollama_service: OllamaService, config: ConfigManager, category_manager: CategoryManager, alias_manager: AliasManager):
        self.bus = bus
        self.state = state_manager
        self.ollama = ollama_service
        self.config = config
        self.category_manager = category_manager
        self.alias_manager = alias_manager
        
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._handle_input)
        self.bus.subscribe_async(EventType.USER_CONFIRMED, self._execute_command)

    async def _handle_input(self, event: Event):
        user_input = event.payload.get('input', "").strip()
        if not user_input:
            return
            
        # 1. Expand Alias
        user_input = self.alias_manager.resolve_alias(user_input)

        # Ignore builtins (check after expansion, though usually aliases map to shell cmds)
        if user_input.lower().split()[0] in ["/exit", "exit", "/help", "help", "/alias"]:
            return

        # Check for RAG query
        if user_input.lower().startswith("/docs"):
            query = user_input[5:].strip() # Remove /docs
            await self.bus.publish(Event(
                EventType.RAG_QUERY_REQUESTED,
                payload={'query': query},
                sender="Logic"
            ))
            return

        # Use logic from Router/Config if possible, but for demo keep it simple
        if user_input.startswith("/") or user_input.startswith("ls") or user_input.startswith("cd"):
             await self.bus.publish(Event(
                EventType.AI_SUGGESTION_READY, 
                payload={'command': user_input.lstrip("/")},
                sender="Logic"
            ))
        else:
            # Natural Language - use Ollama
            await self.bus.publish(Event(EventType.AI_PROCESSING_STARTED, sender="Logic"))
            proposed_cmd = await self.ollama.generate_command(user_input)
            
            if proposed_cmd:
                cat = self.category_manager.classify_command(proposed_cmd)
                await self.bus.publish(Event(
                    EventType.AI_SUGGESTION_READY, 
                    payload={'command': proposed_cmd, 'category': cat},
                    sender="Logic"
                ))
            else:
                await self.bus.publish(Event(
                    EventType.ERROR_OCCURRED,
                    payload={'message': "Ollama failed to generate command."},
                    sender="Logic"
                ))
                await self.bus.publish(Event(EventType.EXECUTION_FINISHED)) # Return to IDLE

    async def _execute_command(self, event: Event):
        cmd = self.state.context.proposed_command
        # This category might have been updated by the UI (overrides)
        category = self.state.context.proposed_category 
        
        if cmd:
            await self.bus.publish(Event(
                type=EventType.EXECUTION_REQUESTED,
                payload={'command': cmd, 'mode': category},
                sender="Logic"
            ))

async def main():
    # Detect base directory (one level up from micro_X_v2/)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    bus = EventBus()
    config = ConfigManager(base_dir)
    
    state_manager = StateManager(bus)
    ollama_service = OllamaService(bus, config)
    shell_service = ShellService(bus)
    tmux_service = TmuxService(bus)
    builtin_service = BuiltinService(bus)
    category_manager = CategoryManager(config)
    alias_manager = AliasManager(config)
    rag_service = RagService(bus, config)
    
    ui = V2UIManager(bus, state_manager)
    logic = LogicEngine(bus, state_manager, ollama_service, config, category_manager, alias_manager)

    # Signal app start
    await bus.publish(Event(EventType.APP_STARTED))

    app = ui.build_app()
    
    # Run the prompt_toolkit app
    await app.run_async()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")