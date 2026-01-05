# micro_X_v4/main.py

import asyncio
import logging
import sys
import os
import re

from .core.events import EventBus, Event, EventType
from .core.state import StateManager, AppState
from .core.config import ConfigManager
from .ui.app import V4UIManager
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
from .core.agent_graph import MicroXAgent
from langchain_core.messages import HumanMessage

# Configure Logging
logging.basicConfig(filename='v4.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LogicEngine:
    """
    The Master Router for micro_X V4.
    Orchestrates Alias expansion, Intent classification, Security, and Agent Dispatching.
    """
    def __init__(self, bus: EventBus, state_manager: StateManager, ollama_service: OllamaService, 
                 config: ConfigManager, category_manager: CategoryManager, 
                 alias_manager: AliasManager, intent_service: IntentService, 
                 utility_service: UtilityService, rag_service: RagService):
        self.bus = bus
        self.state = state_manager
        self.ollama = ollama_service
        self.config = config
        self.category_manager = category_manager
        self.alias_manager = alias_manager
        self.intent_service = intent_service
        self.utility_service = utility_service
        
        # Initialize LangGraph Agent
        self.agent = MicroXAgent(config._config, bus, rag_service, utility_service, ollama_service)
        self.agent_graph = self.agent.build_graph()
        
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
        # Skip if it looks like a command (starts with /) to avoid redirection loops
        if not expanded_input.startswith("/") and not expanded_input.startswith("!") and not is_alias and event.sender != "LogicRedirect":
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
        first_token = expanded_input.split()[0].lower()
        if first_token in ["/exit", "exit", "/help", "help", "/alias", "/history", "/git_branch", "/config"]:
            return

        if first_token in self.utility_service.UTILITY_MAP or first_token == "/utils":
            await self._dispatch(expanded_input, mode='utility')
            return

        # RAG shortcut (V3 handles this inside Agent, but we keep explicit /docs for speed)
        if expanded_input.lower().startswith("/docs"):
            query = expanded_input[5:].strip()
            if query:
                await self.bus.publish(Event(EventType.RAG_QUERY_REQUESTED, payload={'query': query}, sender="Logic"))
            else:
                await self._dispatch("/docs", mode='utility')
            return

        # 5. Auto-Run for Categorized Shell Commands
        known_cat = self.category_manager.classify_command(expanded_input)
        if known_cat:
            if not await self._check_security(expanded_input): return
            await self._dispatch(expanded_input, known_cat)
            return

        # 6. Agent Graph Execution (The "Brain")
        # Handles complex routing and translation
        await self.bus.publish(Event(EventType.AI_PROCESSING_STARTED, sender="Logic"))
        
        initial_state = {
            "messages": [HumanMessage(content=expanded_input)],
            "user_input": expanded_input,
            "final_action": None
        }
        
        try:
            result = await self.agent_graph.ainvoke(initial_state)
            logger.debug(f"Agent Graph result: {result}")
        except Exception as e:
            logger.error(f"Agent Graph execution failed: {e}")
            await self.bus.publish(Event(
                type=EventType.EXECUTION_ERROR,
                payload={'message': f"❌ AI Brain Error: {str(e)}"},
                sender="Logic"
            ))
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
            return
        
        last_message = result['messages'][-1]
        
        if last_message.type == "tool":
            output = last_message.content
            if output.startswith("COMMAND_PENDING:"):
                cmd = output.replace("COMMAND_PENDING:", "").strip()
                cat = self.category_manager.classify_command(cmd)
                await self.bus.publish(Event(
                    EventType.AI_SUGGESTION_READY, 
                    payload={'command': cmd, 'category': cat},
                    sender="Logic"
                ))
            else:
                # Direct output from tool (e.g. RAG answer)
                # We prefix this to distinguish it from the agent's chat
                await self.bus.publish(Event(
                    type=EventType.EXECUTION_OUTPUT,
                    payload={'output': f"📘 {output}"},
                    sender="Logic"
                ))
                await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
        
        elif last_message.type == "ai":
            # Direct chat response
            content = last_message.content
            # Clean <think> tags if present
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            await self.bus.publish(Event(
                type=EventType.EXECUTION_OUTPUT,
                payload={'output': f"🤖 {content}"},
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
    
    builtins = ["/exit", "/help", "/alias", "/history", "/git_branch", "/config", "/docs"]
    utils = list(utility_service.UTILITY_MAP.keys())
    aliases = list(alias_manager.get_all_aliases().keys())
    completion_words = sorted(list(set(builtins + utils + aliases)))

    ui = V4UIManager(bus, state_manager, history_service.get_pt_history(), completion_words)
    logic = LogicEngine(bus, state_manager, ollama_service, config, category_manager, alias_manager, intent_service, utility_service, rag_service)

    # Signal app start
    await bus.publish(Event(EventType.APP_STARTED))

    app = ui.build_app()
    await app.run_async()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")