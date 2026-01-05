# micro_X_v4/modules/help_service.py

import logging
from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class HelpService:
    """
    V2 Help Service.
    Provides documentation for the shell commands and features.
    """
    
    GENERAL_HELP = """
📚 micro_X V2 Help

Common Commands:
  /translate <query>  - Translates natural language to a shell command.
  !command            - Force a command to be treated as a direct command, bypassing AI.
  /help [topic]       - Displays this help message or help for a specific topic.
  /alias              - Manage command aliases (shortcuts).
  /docs               - Query the project documentation (RAG).
  /exit               - Quit micro_X.

AI Features:
  - Type any natural language query to get a Linux command suggestion.
  - You will be asked to confirm, explain, or cancel.
  - V2 supports auto-running known commands for speed.

Topics:
  translate, alias, keybindings, security
"""

    AI_HELP = """
🧠 micro_X AI Features

1. Translation:
   Type "list files" -> AI suggests "ls -la".
   
2. Validation:
   The system double-checks if the AI output is a valid command.
   
3. Explanation:
   Press '5' in the confirmation menu to get a detailed explanation of the command.
   
4. Safety:
   Unknown commands require confirmation. Known commands (categorized) run instantly.
"""

    KEYS_HELP = """
⌨️ Keybindings

  Enter       - Submit command.
  Ctrl+C      - Cancel / Exit.
  
  Confirmation Menu:
  [1] Yes (Run)
  [2] Run as Simple (background/log)
  [3] Run as Semi-Interactive (tmux, wait)
  [4] Run as TUI (tmux, interactive)
  [5] Explain
  [7] Cancel
"""

    ALIAS_HELP = """
🏷️ Alias Management

  /alias --list              - Show all aliases.
  /alias --add <name> <cmd>  - Add a new alias.
  /alias --remove <name>     - Remove an alias.
  
  Example: /alias --add /l ls -la
"""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.subscribe_async(EventType.USER_INPUT_RECEIVED, self._on_input)

    async def _on_input(self, event: Event):
        text = event.payload.get('input', "").strip()
        parts = text.split()
        
        if not parts: return
        
        cmd = parts[0].lower()
        if cmd == "/help": # Only explicit command
            topic = parts[1].lower() if len(parts) > 1 else "general"
            await self._show_help(topic)
            await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

    async def _show_help(self, topic: str):
        content = ""
        if topic == "general":
            content = self.GENERAL_HELP
        elif topic == "translate" or topic == "ai":
            content = self.AI_HELP
        elif topic == "keys" or topic == "keybindings":
            content = self.KEYS_HELP
        elif topic == "alias":
            content = self.ALIAS_HELP
        else:
            content = f"❌ Unknown help topic: '{topic}'.\nAvailable: general, translate, keys, alias."

        await self.bus.publish(Event(
            type=EventType.EXECUTION_OUTPUT,
            payload={'output': content},
            sender="HelpService"
        ))
