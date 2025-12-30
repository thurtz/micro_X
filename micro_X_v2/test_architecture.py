# micro_X-v2/test_architecture.py

import asyncio
import sys
import os

# Ensure we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.events import EventBus, Event, EventType
from core.state import StateManager, AppState

async def test_flow():
    print("--- Starting Architecture Test ---")
    
    # 1. Setup
    bus = EventBus()
    state_manager = StateManager(bus)
    
    # 2. Add a simple observer to print state changes
    def print_state_change(event):
        old = event.payload['old'].name
        new = event.payload['new'].name
        print(f"State Changed: {old} -> {new}")
        
    bus.subscribe(EventType.STATE_CHANGED, print_state_change)

    # 3. Simulate App Start
    print("\n[Step 1] App Start")
    await bus.publish(Event(EventType.APP_STARTED))
    assert state_manager.current_state == AppState.IDLE
    print("✓ State is IDLE")

    # 4. Simulate User Input
    print("\n[Step 2] User Input: 'Hello AI'")
    await bus.publish(Event(EventType.USER_INPUT_RECEIVED, payload={'input': 'Hello AI'}))
    
    # 5. Simulate AI Processing Start (Logic would trigger this)
    print("\n[Step 3] AI Processing Starts")
    await bus.publish(Event(EventType.AI_PROCESSING_STARTED))
    assert state_manager.current_state == AppState.PROCESSING
    print("✓ State is PROCESSING")

    # 6. Simulate AI Suggestion Ready
    print("\n[Step 4] AI Suggestion: 'echo Hello'")
    await bus.publish(Event(EventType.AI_SUGGESTION_READY, payload={'command': 'echo Hello'}))
    assert state_manager.current_state == AppState.CONFIRMATION
    assert state_manager.context.proposed_command == 'echo Hello'
    print("✓ State is CONFIRMATION")
    print("✓ Context has proposed command")

    # 7. Simulate User Confirmation
    print("\n[Step 5] User Confirms")
    await bus.publish(Event(EventType.USER_CONFIRMED))
    assert state_manager.current_state == AppState.EXECUTING
    print("✓ State is EXECUTING")

    print("\n--- Test Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(test_flow())