# micro_X-v2/core/events.py

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Defines all possible event types in the system."""
    # System Events
    APP_STARTED = auto()
    APP_SHUTDOWN = auto()
    ERROR_OCCURRED = auto()

    # User Input Events
    USER_INPUT_RECEIVED = auto()  # Raw input from the prompt
    
    # Logic/Processing Events
    COMMAND_DETECTED = auto()     # Input identified as a shell command
    NATURAL_LANGUAGE_DETECTED = auto() # Input identified as NL
    AI_PROCESSING_STARTED = auto()
    AI_SUGGESTION_READY = auto()  # AI has a proposed command
    AI_EXPLAIN_REQUESTED = auto() # Request for explanation
    AI_EXPLANATION_READY = auto() # Explanation received
    AI_ANALYZE_ERROR = auto()     # Request error analysis
    
    # RAG Events
    RAG_QUERY_REQUESTED = auto()
    RAG_RESPONSE_READY = auto()
    
    # Alias Events
    ALIAS_COMMAND_RECEIVED = auto() # /alias --add etc.
    ALIAS_LIST_REQUESTED = auto()
    
    # Intent Events
    INTENT_STATUS_CHANGED = auto()
    
    # Security Events
    SECURITY_BLOCKED = auto()
    SECURITY_WARN_TRIGGERED = auto()
    
    # UI/State Events
    STATE_CHANGED = auto()        # The global app state has transitioned
    REQUEST_CONFIRMATION = auto() # Logic requests UI to show confirmation
    USER_CONFIRMED = auto()       # User said YES
    USER_CANCELLED = auto()       # User said NO

    # Ollama Service Events
    OLLAMA_START_REQUESTED = auto()
    OLLAMA_STOP_REQUESTED = auto()
    OLLAMA_STATUS_CHANGED = auto()
    OLLAMA_ERROR = auto()

    # Shell/Execution Events
    EXECUTION_REQUESTED = auto()  # Request to run a command
    EXECUTION_OUTPUT = auto()     # New line of output from a command
    EXECUTION_FINISHED = auto()   # Command completed
    EXECUTION_ERROR = auto()      # Subprocess failed to start

@dataclass
class Event:
    """A single event flowing through the bus."""
    type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    sender: str = "system"

class EventBus:
    """
    Central Event Bus.
    Components publish Events here.
    Components subscribe to EventTypes here.
    """
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._async_subscribers: Dict[EventType, List[Callable[[Event], Any]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """Register a synchronous handler for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def subscribe_async(self, event_type: EventType, handler: Callable[[Event], Any]):
        """Register an asynchronous handler for an event type."""
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        self._async_subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        """
        Publish an event to all subscribers.
        Sync handlers are called immediately.
        Async handlers are awaited.
        """
        logger.debug(f"EventBus: Publishing {event.type.name} from {event.sender}")

        # 1. Call synchronous handlers
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in sync handler for {event.type.name}: {e}", exc_info=True)

        # 2. Call asynchronous handlers
        if event.type in self._async_subscribers:
            tasks = []
            for handler in self._async_subscribers[event.type]:
                tasks.append(handler(event))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):
                        logger.error(f"Error in async handler for {event.type.name}: {res}", exc_info=True)
