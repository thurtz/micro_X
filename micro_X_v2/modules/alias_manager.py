# micro_X_v2/modules/alias_manager.py

import os
import json
import logging
from typing import Dict, Optional
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class AliasManager:
    """
    Manages command aliases (e.g., /l -> ls -la).
    """
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.aliases: Dict[str, str] = {}
        self.load_aliases()

    def load_aliases(self):
        """Loads default and user aliases."""
        base_dir = self.config_manager.base_dir
        config_dir = os.path.join(base_dir, "config")
        
        default_path = os.path.join(config_dir, "default_aliases.json")
        # In V1, user aliases might be in a separate file or merged. 
        # For V2 simplicity, let's assume we might have a user_aliases.json later.
        
        if os.path.exists(default_path):
            try:
                with open(default_path, 'r') as f:
                    self.aliases = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load aliases: {e}")

    def resolve_alias(self, command: str) -> str:
        """
        Checks if the command (or its first token) is an alias.
        Returns the expanded command if found, otherwise the original.
        """
        # We only alias the first word (command) usually
        parts = command.split(" ", 1)
        first_word = parts[0]
        
        if first_word in self.aliases:
            expanded = self.aliases[first_word]
            if len(parts) > 1:
                return f"{expanded} {parts[1]}"
            return expanded
            
        return command

    def get_all_aliases(self) -> Dict[str, str]:
        return self.aliases
