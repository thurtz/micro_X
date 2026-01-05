import logging
from .events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class UIManagerAdapter:
    """
    Adapts the V1 ShellEngine's expectations of a UIManager to the V5 Event Bus.
    When ShellEngine calls methods on this, we translate them into Events.
    """
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.output_buffer = [] # Mock buffer if accessed directly
        
        # Mock UI State Flags expected by ShellEngine
        self.categorization_flow_active = False
        self.confirmation_flow_active = False
        self.hung_task_flow_active = False
        self.api_input_flow_active = False
        self.is_in_edit_mode = False

    def append_output(self, text: str, style_class: str = ''):
        """Mock implementation of append_output that publishes an event."""
        # Detect if it's an error style
        event_type = EventType.EXECUTION_OUTPUT
        if style_class == 'error':
            event_type = EventType.EXECUTION_ERROR
            # EXECUTION_ERROR payload uses 'message'
            payload = {'message': text}
        else:
            # EXECUTION_OUTPUT payload uses 'output'
            payload = {'output': text}

        # We publish synchronously? No, bus is async.
        # But append_output in V1 is sync. 
        # We need to bridge this. Ideally we schedule a task.
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.bus.publish(Event(
                type=event_type,
                payload=payload,
                sender="ShellEngine"
            )))
        except RuntimeError:
            logger.error("UIManagerAdapter: No running loop to publish event.")

    def update_input_prompt(self, current_dir: str):
        """Mock update_input_prompt."""
        # V5 UI doesn't support dynamic prompt updates via this method yet,
        # but we could send an event if we wanted.
        pass

    def update_status_bar(self, text: str):
        pass

    def get_app_instance(self):
        """Mock get_app_instance returning a dummy app with invalidate method."""
        class DummyApp:
            def invalidate(self):
                pass
            def exit(self):
                pass
        return DummyApp()
        
    def display_help(self):
        """Mock display help."""
        self.append_output("Help is not fully implemented in Hybrid V5 yet. Try 'man' or standard shell help.", style_class='info')

    # Add other methods ShellEngine uses if necessary
    async def prompt_for_api_input(self, prompt: str):
        # This is harder to bridge. V1 awaited user input.
        # We might need to implement a request/response event flow.
        return ""
