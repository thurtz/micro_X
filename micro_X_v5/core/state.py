# micro_X_v4/core/state.py

import asyncio
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import logging

from .events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class AppState(Enum):
    """The high-level mode the application is in."""
    BOOTING = auto()
    IDLE = auto()               # Waiting for user input at the prompt
    PROCESSING = auto()         # AI or Logic is thinking
    CONFIRMATION = auto()       # Showing the "Yes/No/Explain" dialog
    CATEGORIZATION = auto()     # Asking user to categorize unknown command
    CAUTION = auto()            # Security warning for sensitive manual commands
    EXECUTING = auto()          # Running a shell command
    ERROR_RECOVERY = auto()     # Command failed, offering fix
    ERROR = auto()              # Error state

@dataclass
class StateContext:
    """Holds data relevant to the current state (payloads, history, etc)."""
    current_input: str = ""
    proposed_command: Optional[str] = None
    proposed_category: Optional[str] = None
    last_error: Optional[str] = None
    
    # For Error Recovery
    failed_command: Optional[str] = None
    failed_output: Optional[str] = None

class StateManager:
    """
    The Single Source of Truth for Application State.
    """
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self._state: AppState = AppState.BOOTING
        self._context: StateContext = StateContext()

        # Wire up internal listeners
        self.bus.subscribe(EventType.APP_STARTED, self._on_app_started)
        self.bus.subscribe(EventType.USER_INPUT_RECEIVED, self._on_user_input)
        self.bus.subscribe(EventType.AI_PROCESSING_STARTED, self._on_ai_processing)
        self.bus.subscribe(EventType.AI_SUGGESTION_READY, self._on_suggestion_ready)
        self.bus.subscribe(EventType.USER_CONFIRMED, self._on_user_confirmed)
        self.bus.subscribe(EventType.USER_CANCELLED, self._on_user_cancelled)
        self.bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)
        self.bus.subscribe(EventType.EXECUTION_FINISHED, self._on_execution_finished)
        self.bus.subscribe(EventType.SECURITY_WARN_TRIGGERED, self._on_security_warn)
        self.bus.subscribe(EventType.CATEGORIZATION_REQUESTED, self._on_categorization_req)

    @property
    def current_state(self) -> AppState:
        return self._state

    @property
    def context(self) -> StateContext:
        return self._context

    def _set_state(self, new_state: AppState):
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.info(f"State Transition: {old_state.name} -> {new_state.name}")
            asyncio.create_task(self.bus.publish(Event(
                type=EventType.STATE_CHANGED,
                payload={'old': old_state, 'new': new_state},
                sender="StateManager"
            )))

    def _on_app_started(self, event: Event):
        self._set_state(AppState.IDLE)

    def _on_user_input(self, event: Event):
        self._context.current_input = event.payload.get('input', "")

    def _on_ai_processing(self, event: Event):
        self._set_state(AppState.PROCESSING)

    def _on_suggestion_ready(self, event: Event):
        self._context.proposed_command = event.payload.get('command')
        self._context.proposed_category = event.payload.get('category') # Can be None
        self._set_state(AppState.CONFIRMATION)

    def _on_user_confirmed(self, event: Event):
        self._set_state(AppState.EXECUTING)

    def _on_user_cancelled(self, event: Event):
        self._context.proposed_command = None
        self._set_state(AppState.IDLE)

    def _on_error(self, event: Event):
        self._context.last_error = event.payload.get('message')

    def _on_security_warn(self, event: Event):
        self._context.proposed_command = event.payload.get('command')
        self._context.proposed_category = event.payload.get('category', 'semi_interactive')
        self._set_state(AppState.CAUTION)

    def _on_categorization_req(self, event: Event):
        self._context.proposed_command = event.payload.get('command')
        # We don't have a category yet
        self._set_state(AppState.CATEGORIZATION)

    def _on_execution_finished(self, event: Event):
        returncode = event.payload.get('returncode', 0)
        
        # Note: ShellService passes full output? No, it streamed it.
        # But we need the output for analysis. 
        # StateManager doesn't buffer output. ShellService doesn't store it.
        # We need to capture the buffer?
        # V2 UIManager has the output buffer. 
        # Or ShellService should include the captured stderr in the finished payload?
        
        # For now, let's assume we trigger recovery only if we have context.
        # But wait, ShellService logic sends EXECUTION_OUTPUT events.
        # If we want to analyze, we need the last N lines of output?
        
        # Let's assume ShellService adds 'last_stderr' to payload if possible?
        # I'll update ShellService first.
        
        # Placeholder logic:
        if returncode != 0:
            self._context.failed_command = self._context.proposed_command or "Unknown"
            self._context.failed_output = event.payload.get('last_stderr', "No output captured.")
            self._set_state(AppState.ERROR_RECOVERY)
        else:
            self._set_state(AppState.IDLE)

    async def command_execution_finished(self):
        self._set_state(AppState.IDLE)