# micro_X_v5/main.py

import asyncio
import logging
import sys
import os

from .core.events import EventBus, Event, EventType
from .core.state import StateManager, AppState
from .core.adapters import UIManagerAdapter
from .ui.app import V5UIManager

# Import V1 ShellEngine (now patched)
from .modules.shell_engine import ShellEngine
# We need to mock/import other V1 dependencies if ShellEngine needs them
from .modules.config_handler import load_jsonc_file # Assuming this was copied

# Configure Logging
logging.basicConfig(filename='v5.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

class HybridController:
    """
    Connects the Event-Driven V5 UI with the Imperative V1 ShellEngine.
    """
    def __init__(self, bus: EventBus, shell_engine: ShellEngine):
        self.bus = bus
        self.shell_engine = shell_engine
        
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._handle_input)
        # self.bus.subscribe_async(EventType.USER_CONFIRMED, ...) # V1 Engine manages its own confirmation flow mostly

    async def _handle_input(self, event: Event):
        user_input = event.payload.get('input', "").strip()
        if not user_input: return
        
        logger.info(f"HybridController received input: {user_input}")
        
        # We start the "processing" state visual
        await self.bus.publish(Event(EventType.AI_PROCESSING_STARTED, sender="HybridController")) # Reuse this for "Working..."
        
        # Bridge to V1 Engine
        # V1 Engine's handle_built_in_command and submit_user_input are async
        try:
            # We assume normal input flow
            was_builtin = await self.shell_engine.handle_built_in_command(user_input)
            if not was_builtin:
                await self.shell_engine.submit_user_input(user_input, from_edit_mode=False)
            
            # V1 Engine doesn't return "done". It just does things.
            # We need to signal the UI that we are done?
            # The adapter sends EXECUTION_OUTPUT events.
            # We should signal FINISHED to return to prompt.
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
            
        except Exception as e:
            logger.error(f"V1 Engine Error: {e}")
            await self.bus.publish(Event(
                EventType.EXECUTION_ERROR,
                payload={'message': str(e)},
                sender="HybridController"
            ))
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

async def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bus = EventBus()
    state_manager = StateManager(bus)
    
    # 1. Setup V1 Configuration (Mock or Real?)
    # ShellEngine expects a config dict.
    # We can load the real one.
    config_path = os.path.join(base_dir, "config", "default_config.json")
    # We need a simple loader since we might not have the full config module setup correctly
    import json
    with open(config_path, 'r') as f:
        # Strip comments if needed, or just load simple
        # For robustness, let's just assume valid json or use the copied handler
        try:
            from modules.config_handler import load_jsonc_file
            config = load_jsonc_file(config_path) or {}
        except ImportError:
            config = json.load(f)

    # 2. Setup Adapter
    ui_adapter = UIManagerAdapter(bus)
    
    # 3. Initialize ShellEngine
    # It needs a lot of modules. In V1 they are passed or imported.
    # We patched imports so internal imports should work.
    # Constructor args: config, ui_manager, category_manager_module, ...
    
    # We need to manually import the modules to pass them if ShellEngine uses them for global state
    import modules.category_manager as cat_man
    import modules.ai_handler as ai_hand
    import modules.ollama_manager as ollama_man
    
    # Init dependencies
    cat_man.init_category_manager(base_dir, "config", ui_adapter.append_output)
    
    shell_engine = ShellEngine(
        config=config,
        ui_manager=ui_adapter,
        category_manager_module=cat_man,
        ai_handler_module=ai_hand,
        ollama_manager_module=ollama_man,
        main_exit_app_ref=lambda: sys.exit(0),
        main_restore_normal_input_ref=lambda: None, # UI doesn't need this callback logic
        main_normal_input_accept_handler_ref=lambda x: None,
        is_developer_mode=True, # Simplify
        git_context_manager_instance=None # Skip for now or init properly
    )
    
    # 4. Setup V5 UI
    # We need to give it history. 
    from prompt_toolkit.history import FileHistory
    history = FileHistory(".micro_x_v5_history")
    
    ui = V5UIManager(bus, state_manager, history, completion_words=[])
    
    # 5. Hybrid Controller
    controller = HybridController(bus, shell_engine)
    
    # Start
    await bus.publish(Event(EventType.APP_STARTED))
    
    app = ui.build_app()
    await app.run_async()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")