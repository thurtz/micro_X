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
from .modules.rag_service import RagService
from .modules.help_service import HelpService
from .modules.intent_service import IntentService
from .modules.history_service import HistoryService
from .modules.git_context_service import GitContextService
from .modules.utility_service import UtilityService

# Configure Logging
logging.basicConfig(filename='v2.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LogicEngine:
    """Handles the translation logic and execution requests."""
    def __init__(self, bus: EventBus, state_manager: StateManager, ollama_service: OllamaService, 
                 config: ConfigManager, category_manager: CategoryManager, 
                 alias_manager: AliasManager, intent_service: IntentService, utility_service: UtilityService):
        self.bus = bus
        self.state = state_manager
        self.ollama = ollama_service
        self.config = config
        self.category_manager = category_manager
        self.alias_manager = alias_manager
        self.intent_service = intent_service
        self.utility_service = utility_service
        
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._handle_input)
        self.bus.subscribe_async(EventType.USER_CONFIRMED, self._execute_command)

    async def _check_security(self, command: str) -> bool:
        """Checks command against Deny and Warn lists. Returns False if blocked."""
        # 1. Deny List (Regex)
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

        # 2. Warn List (Sensitive Commands)
        warn_commands = self.config.get("security.warn_on_commands", [])
        first_token = command.strip().split()[0]
        if first_token in warn_commands:
            logger.info(f"SECURITY: Command '{command}' triggered warning.")
            # Trigger CAUTION state
            cat = self.category_manager.classify_command(command) or "semi_interactive"
            await self.bus.publish(Event(
                type=EventType.SECURITY_WARN_TRIGGERED,
                payload={'command': command, 'category': cat},
                sender="LogicSecurity"
            ))
            return False # Block direct execution, flow continues in CAUTION state

        return True

    async def _handle_input(self, event: Event):
        user_input = event.payload.get('input', "").strip()
        if not user_input:
            return
            
        logger.debug(f"LogicEngine received input: '{user_input}'")
        
        # 0. Check for forced execution (!)
        if user_input.startswith("!"):
            forced_cmd = user_input[1:].strip()
            if forced_cmd:
                # Security Check
                if not await self._check_security(forced_cmd):
                    return

                cat = self.category_manager.classify_command(forced_cmd)
                if not cat:
                    # Fallback for forced command if not in json categories
                    cat = self.config.get("behavior.default_category_for_unclassified", "semi_interactive")
                
                logger.info(f"LogicEngine: Force executing '{forced_cmd}' with category '{cat}'")
                await self.bus.publish(Event(
                    type=EventType.EXECUTION_REQUESTED,
                    payload={'command': forced_cmd, 'mode': cat},
                    sender="Logic"
                ))
                return

        # 1. Check for builtins (BEFORE alias expansion)
        first_token = user_input.lower().split()[0]
        if first_token in ["/exit", "exit", "/help", "help", "/alias", "/history", "/git_branch", "/config"]:
            logger.debug("LogicEngine ignoring builtin/alias (pre-expansion).")
            return

        # 2. Expand Alias
        user_input = self.alias_manager.resolve_alias(user_input)
        
        # 3. Intent Classification (Semantic Routing)
        # Only run for natural language (doesn't start with / or !)
        intent, score = None, 0.0
        if not user_input.startswith("/") and not user_input.startswith("!"):
            intent, score = await self.intent_service.classify(user_input)
            threshold = self.config.get("intent_classification.classification_threshold", 0.75)
            logger.debug(f"Intent check: '{user_input}' -> {intent} (score: {score:.2f}, threshold: {threshold})")
            
            if intent and score > threshold:
                mapped_cmd = self.intent_service.get_command_for_intent(intent)
                if mapped_cmd and mapped_cmd != user_input:
                    logger.info(f"LogicEngine: Redirecting intent '{intent}' to '{mapped_cmd}'")
                    # Publish new event with the mapped command so services (Help, Builtin) can pick it up
                    await self.bus.publish(Event(
                        type=EventType.USER_INPUT_RECEIVED,
                        payload={'input': mapped_cmd},
                        sender="LogicRedirect"
                    ))
                    return

        # 4. Check if command is already known/categorized (Auto-Run)
        
        # Check for Utilities first
        first_token = user_input.split()[0]
        if first_token in self.utility_service.UTILITY_MAP or first_token == "/utils":
             logger.info(f"Auto-running utility: {user_input}")
             await self.bus.publish(Event(
                type=EventType.EXECUTION_REQUESTED,
                payload={'command': user_input, 'mode': 'utility'}, # mode='utility' handled by UtilityService?
                sender="Logic"
            ))
             return

        known_category = self.category_manager.classify_command(user_input)
        if known_category:
            # Security Check
            if not await self._check_security(user_input):
                return

            logger.info(f"Auto-running known command: {user_input} ({known_category})")
            # We need to set the context proposed command so execution has something to run
            # But wait, EXECUTION_REQUESTED payload carries the command.
            # However, StateManager context update usually happens on SUGGESTION_READY.
            # We should probably update context manually or just pass it in payload.
            
            # Update context directly? No, clean way:
            # We skip CONFIRMATION state and go straight to EXECUTING (via EXECUTION_REQUESTED).
            
            # BUT: StateManager needs to know we are EXECUTING.
            # StateManager listens to USER_CONFIRMED -> EXECUTING.
            # It doesn't listen to EXECUTION_REQUESTED?
            # Let's check StateManager. It listens to nothing relevant for transition to EXECUTING except USER_CONFIRMED.
            
            # We need a new event or just fire EXECUTION_REQUESTED and let ShellService handle it?
            # If we fire EXECUTION_REQUESTED, ShellService runs.
            # But StateManager remains in IDLE.
            # Then EXECUTION_FINISHED fires -> StateManager sets IDLE (no change).
            # This is technically fine, but UI might not show [Running Command...] status.
            
            # Better: Publish a "DIRECT_EXECUTION_STARTED" event?
            # Or just rely on ShellService/TmuxService execution.
            
            # Let's fire EXECUTION_REQUESTED.
            await self.bus.publish(Event(
                type=EventType.EXECUTION_REQUESTED,
                payload={'command': user_input, 'mode': known_category},
                sender="Logic"
            ))
            return

        if user_input.startswith("/") or user_input.startswith("ls ") or user_input == "ls":
             # Treat as direct command -> Suggestion (Confirmation)
             # V1 would run this if categorized.
             
             # Let's stick to the current "Safe Mode" (Confirmation) for everything unless we are sure.
             pass

        # Check for RAG query

        # Check for RAG query
        # Only if arguments are provided (e.g. /docs how to use)
        # If just "/docs", let it fall through to UtilityService (opens web docs)
        if user_input.lower().startswith("/docs ") and len(user_input.strip()) > 6:
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
    alias_manager = AliasManager(bus, config)
    rag_service = RagService(bus, config)
    help_service = HelpService(bus)
    intent_service = IntentService(bus, config)
    history_service = HistoryService(bus, config)
    git_service = GitContextService(bus, config)
    utility_service = UtilityService(bus, config)
    
    # Collect completion words
    builtins = ["/exit", "/help", "/alias", "/history", "/git_branch", "/config", "/docs"]
    utils = list(utility_service.UTILITY_MAP.keys())
    aliases = list(alias_manager.get_all_aliases().keys())
    completion_words = sorted(list(set(builtins + utils + aliases)))

    ui = V2UIManager(bus, state_manager, history_service.get_pt_history(), completion_words)
    logic = LogicEngine(bus, state_manager, ollama_service, config, category_manager, alias_manager, intent_service, utility_service)

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