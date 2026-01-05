# micro_X_v2/main.py

import asyncio
import logging
import sys
import os
import re

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
# from .modules.rag_service import RagService # Imported but we'll use specific trigger
from .modules.rag_service import RagService
from .modules.help_service import HelpService
from .modules.intent_service import IntentService
from .modules.history_service import HistoryService
from .modules.git_context_service import GitContextService
from .modules.utility_service import UtilityService
from .modules.router_service import RouterService

# Configure Logging
logging.basicConfig(filename='v2.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LogicEngine:
    """
    The Master Router for micro_X V2.
    Orchestrates Alias expansion, Intent classification, Security, and Dispatching.
    """
    def __init__(self, bus: EventBus, state_manager: StateManager, ollama_service: OllamaService, 
                 config: ConfigManager, category_manager: CategoryManager, 
                 alias_manager: AliasManager, intent_service: IntentService, 
                 utility_service: UtilityService, router_service: RouterService):
        self.bus = bus
        self.state = state_manager
        self.ollama = ollama_service
        self.config = config
        self.category_manager = category_manager
        self.alias_manager = alias_manager
        self.intent_service = intent_service
        self.utility_service = utility_service
        self.router_service = router_service
        
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._handle_input)
        self.bus.subscribe_async(EventType.USER_CONFIRMED, self._execute_command)

    async def _check_security(self, command: str) -> bool:
        """Checks command against Deny and Warn lists. Returns False if blocked."""
        dangerous_patterns = self.config.get("security.dangerous_patterns", [])
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                logger.warning(f"SECURITY: Command '{command}' blocked by pattern '{pattern}'")
                await self.bus.publish(Event(
                    type=EventType.EXECUTION_ERROR,
                    payload={'message': f"❌ SECURITY BLOCKED: Dangerous command pattern detected."},
                    sender="LogicSecurity"
                ))
                return False

        warn_commands = self.config.get("security.warn_on_commands", [])
        first_token = command.strip().split()[0]
        if first_token in warn_commands:
            logger.info(f"SECURITY: Command '{command}' triggered warning.")
            cat = self.category_manager.classify_command(command) or "semi_interactive"
            await self.bus.publish(Event(
                type=EventType.SECURITY_WARN_TRIGGERED,
                payload={'command': command, 'category': cat},
                sender="LogicSecurity"
            ))
            return False 

        return True

    async def _handle_input(self, event: Event):
        raw_input = event.payload.get('input', "").strip()
        if not raw_input: return
        
        logger.debug(f"LogicEngine processing: '{raw_input}' (sender: {event.sender})")

        # 1. Immediate Dispatch for Forced Execution (!)
        if raw_input.startswith("!"):
            cmd = raw_input[1:].strip()
            if cmd:
                if not await self._check_security(cmd): return
                cat = self.category_manager.classify_command(cmd) or self.config.get("behavior.default_category_for_unclassified", "semi_interactive")
                await self._dispatch(cmd, cat)
            return

        # 2. Alias Expansion
        expanded_input = self.alias_manager.resolve_alias(raw_input)
        is_alias = expanded_input != raw_input
        if is_alias:
            logger.debug(f"Alias expanded: '{raw_input}' -> '{expanded_input}'")

        # 3. Intent Classification (Semantic Routing)
        # Rule: Only run for natural language. 
        # If it started with / or ! or was an alias, we treat it as an explicit command and SKIP intents.
        intent, score = None, 0.0
        if not raw_input.startswith("/") and not raw_input.startswith("!") and not is_alias and event.sender != "LogicRedirect":
            intent, score = await self.intent_service.classify(expanded_input)
            threshold = self.config.get("intent_classification.classification_threshold", 0.60)
            
            if intent and score > threshold:
                mapped_cmd = self.intent_service.get_command_for_intent(intent)
                if mapped_cmd and mapped_cmd != expanded_input:
                    logger.info(f"Intent Match: '{expanded_input}' -> '{intent}' -> '{mapped_cmd}'")
                    await self.bus.publish(Event(
                        type=EventType.USER_INPUT_RECEIVED,
                        payload={'input': mapped_cmd},
                        sender="LogicRedirect"
                    ))
                    return

        # 4. Builtin & Utility Routing
        # Use expanded input from here on
        first_token = expanded_input.split()[0].lower()
        
        # Builtins handled natively by services listening to USER_INPUT_RECEIVED
        # We just need to stop processing here.
        if first_token in ["/exit", "exit", "/help", "help", "/alias", "/history", "/git_branch", "/config"]:
            logger.debug(f"LogicEngine skipping builtin: {first_token}")
            return

        # Utilities handled by UtilityService
        if first_token in self.utility_service.UTILITY_MAP or first_token == "/utils":
            logger.info(f"LogicEngine routing to UtilityService: {expanded_input}")
            await self._dispatch(expanded_input, mode='utility')
            return

        # RAG / Documentation
        if expanded_input.lower().startswith("/docs"):
            query = expanded_input[5:].strip()
            if query:
                await self.bus.publish(Event(
                    EventType.RAG_QUERY_REQUESTED,
                    payload={'query': query},
                    sender="Logic"
                ))
            else:
                # Just /docs -> trigger the utility
                await self._dispatch("/docs", mode='utility')
            return

        # 5. Auto-Run for Categorized Shell Commands
        known_cat = self.category_manager.classify_command(expanded_input)
        if known_cat:
            if not await self._check_security(expanded_input): return
            logger.info(f"Auto-running known command: {expanded_input} ({known_cat})")
            await self._dispatch(expanded_input, known_cat)
            return

        # 6. Ambiguity Routing (Router Agent)
        # Only if not a direct command path
        if not expanded_input.startswith("/"):
            route = await self.router_service.route_input(expanded_input)
            if route == "DOCS":
                logger.info("Router directed to RAG.")
                await self.bus.publish(Event(EventType.RAG_QUERY_REQUESTED, payload={'query': expanded_input}, sender="Logic"))
                return

        # 7. AI Translation (Ollama)
        await self.bus.publish(Event(EventType.AI_PROCESSING_STARTED, sender="Logic"))
        proposed_cmd = await self.ollama.generate_command(expanded_input)
        
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
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

    async def _dispatch(self, command: str, mode: str):
        """Helper to fire execution event."""
        await self.bus.publish(Event(
            type=EventType.EXECUTION_REQUESTED,
            payload={'command': command, 'mode': mode},
            sender="Logic"
        ))

    async def _execute_command(self, event: Event):
        """Called when user confirms an AI suggestion."""
        cmd = self.state.context.proposed_command
        category = event.payload.get('category') or self.state.context.proposed_category
        should_save = event.payload.get('save', False)
        
        if not cmd: return

        if should_save and category:
            self.category_manager.add_command(cmd, category)

        # Final check if we need categorization (if user hit [1] Yes on unknown)
        if not event.payload.get('category') and not self.category_manager.is_known(cmd):
             await self.bus.publish(Event(
                type=EventType.CATEGORIZATION_REQUESTED,
                payload={'command': cmd},
                sender="Logic"
            ))
             return

        await self._dispatch(cmd, category or 'simple')

async def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bus = EventBus()
    config = ConfigManager(base_dir)
    
    state_manager = StateManager(bus)
    ollama_service = OllamaService(bus, config)
    shell_service = ShellService(bus)
    tmux_service = TmuxService(bus)
    builtin_service = BuiltinService(bus)
    category_manager = CategoryManager(config)
    alias_manager = AliasManager(bus, config)
    rag_service = RagService(bus, config, ollama_service)
    help_service = HelpService(bus)
    intent_service = IntentService(bus, config)
    history_service = HistoryService(bus, config)
    git_service = GitContextService(bus, config)
    utility_service = UtilityService(bus, config)
    router_service = RouterService(config)
    
    builtins = ["/exit", "/help", "/alias", "/history", "/git_branch", "/config", "/docs"]
    utils = list(utility_service.UTILITY_MAP.keys())
    aliases = list(alias_manager.get_all_aliases().keys())
    completion_words = sorted(list(set(builtins + utils + aliases)))

    ui = V2UIManager(bus, state_manager, history_service.get_pt_history(), completion_words)
    logic = LogicEngine(bus, state_manager, ollama_service, config, category_manager, alias_manager, intent_service, utility_service, router_service)

    await bus.publish(Event(EventType.APP_STARTED))
    app = ui.build_app()
    await app.run_async()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
