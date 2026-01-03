# micro_X_v2/modules/alias_manager.py

import os
import json
import logging
import shlex
from typing import Dict, List, Optional
from ..core.config import ConfigManager
from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class AliasManager:
    """
    Manages command aliases (e.g., /l -> ls -la).
    Handles both default and user-defined aliases with persistence.
    """
    def __init__(self, bus: EventBus, config_manager: ConfigManager):
        self.bus = bus
        self.config_manager = config_manager
        self.default_aliases: Dict[str, str] = {}
        self.user_aliases: Dict[str, str] = {}
        self.merged_aliases: Dict[str, str] = {}
        
        self.load_aliases()
        
        # Subscribe to events
        self.bus.subscribe_async(EventType.ALIAS_COMMAND_RECEIVED, self._on_alias_command)

    def load_aliases(self):
        """Loads default and user aliases and merges them."""
        base_dir = self.config_manager.base_dir
        config_dir = os.path.join(base_dir, "config")
        
        default_path = os.path.join(config_dir, "default_aliases.json")
        user_path = os.path.join(config_dir, "user_command_aliases.json") 
        
        logger.debug(f"AliasManager loading from: {default_path}")
        
        self.default_aliases = self._load_file(default_path)
        self.user_aliases = self._load_file(os.path.join(config_dir, "user_aliases.json"))
        
        self._update_merged()

    def _load_file(self, path: str) -> Dict[str, str]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load aliases from {path}: {e}")
            return {}

    def _update_merged(self):
        """Merges defaults with user overrides."""
        self.merged_aliases = {**self.default_aliases, **self.user_aliases}

    def resolve_alias(self, command: str) -> str:
        """Expands alias if found."""
        parts = command.split(" ", 1)
        first_word = parts[0]
        
        if first_word in self.merged_aliases:
            expanded = self.merged_aliases[first_word]
            if len(parts) > 1:
                return f"{expanded} {parts[1]}"
            return expanded
            
        return command

    async def _on_alias_command(self, event: Event):
        """Handles /alias --add, --remove, --list etc."""
        raw_input = event.payload.get('input', "")
        try:
            parts = shlex.split(raw_input)
        except ValueError as e:
            await self._output(f"❌ Error parsing alias command: {e}")
            return

        if len(parts) < 2:
            await self._output("Usage: /alias [--list | --add <name> <cmd> | --remove <name>]")
            return

        sub = parts[1]
        if sub in ["--help", "-h"]:
            await self._output(
                "Usage: /alias <subcommand> [args]\n"
                "  --list             List all aliases\n"
                "  --add <name> <cmd> Add a new alias (e.g., /alias --add /l ls -la)\n"
                "  --remove <name>    Remove an alias"
            )
        elif sub == "--list":
            await self._list_aliases()
        elif sub == "--add":
            if len(parts) < 4:
                await self._output("❌ Error: Usage: /alias --add <name> <cmd>")
            else:
                await self._add_alias(parts[2], parts[3])
        elif sub == "--remove":
            if len(parts) < 3:
                await self._output("❌ Error: Usage: /alias --remove <name>")
            else:
                await self._remove_alias(parts[2])
        else:
            await self._output(f"❌ Unknown alias subcommand: {sub}")

        await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

    async def _list_aliases(self):
        output = "\n📜 Current Aliases:\n"
        for name, cmd in sorted(self.merged_aliases.items()):
            is_user = name in self.user_aliases
            tag = "[user]" if is_user else "[default]"
            output += f"  {name:<12} -> {cmd} {tag}\n"
        await self._output(output)

    async def _add_alias(self, name: str, cmd: str):
        if not name.startswith("/"):
            await self._output("❌ Error: Alias names must start with '/'")
            return
        
        reserved = ["/exit", "/help", "/alias", "/docs", "/config", "/history"]
        if name.lower() in reserved:
            await self._output(f"❌ Error: '{name}' is a reserved command and cannot be used as an alias.")
            return
        
        self.user_aliases[name] = cmd
        if self._save_user_aliases():
            self._update_merged()
            await self._output(f"✅ Alias {name} added.")
        else:
            await self._output("❌ Failed to save user aliases.")

    async def _remove_alias(self, name: str):
        if name in self.user_aliases:
            del self.user_aliases[name]
            if self._save_user_aliases():
                self._update_merged()
                await self._output(f"🗑️ Alias {name} removed.")
            else:
                await self._output("❌ Failed to save user aliases.")
        else:
            await self._output(f"⚠️ Alias {name} not found in user-defined aliases.")

    def _save_user_aliases(self) -> bool:
        path = os.path.join(self.config_manager.config_dir, "user_aliases.json")
        try:
            with open(path, 'w') as f:
                json.dump(self.user_aliases, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save aliases: {e}")
            return False

    async def _output(self, text: str):
        await self.bus.publish(Event(
            type=EventType.EXECUTION_OUTPUT,
            payload={'output': text},
            sender="AliasManager"
        ))
