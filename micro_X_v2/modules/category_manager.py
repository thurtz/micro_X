# micro_X_v2/modules/category_manager.py

import os
import json
import logging
from typing import Dict, List, Optional
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class CategoryManager:
    """
    Classifies commands into execution categories:
    - simple: Run in background, stream output to TUI.
    - semi_interactive: Run in tmux, wait for keypress to close.
    - interactive_tui: Run in tmux, interactive (e.g., vim, htop).
    """
    
    CATEGORY_MAP = {
        "simple": "simple",
        "semi_interactive": "semi_interactive", 
        "interactive_tui": "interactive_tui"
    }

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.categories: Dict[str, List[str]] = {}
        self.load_categories()

    def load_categories(self):
        """Loads and merges default and user categories."""
        # We reuse the logic from V1 roughly, but cleaner
        base_dir = self.config_manager.base_dir
        config_dir = os.path.join(base_dir, "config")
        
        default_path = os.path.join(config_dir, "default_command_categories.json")
        user_path = os.path.join(config_dir, "user_command_categories.json")

        # Load Default
        self.categories = self._load_file(default_path)
        
        # Merge User
        user_cats = self._load_file(user_path)
        for cat, cmds in user_cats.items():
            if cat not in self.categories:
                self.categories[cat] = []
            
            # Add user commands, removing them from other categories if they exist
            for cmd in cmds:
                self._remove_from_all(cmd)
                if cmd not in self.categories[cat]:
                    self.categories[cat].append(cmd)

    def _load_file(self, path: str) -> Dict[str, List[str]]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r') as f:
                # Simple load, assuming valid JSON for now (or add comment stripping if needed)
                # The ConfigManager helper handles comments, maybe we should expose that utility?
                # For now, standard json load.
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load categories from {path}: {e}")
            return {}

    def _remove_from_all(self, cmd: str):
        for cmds in self.categories.values():
            if cmd in cmds:
                cmds.remove(cmd)

    def classify_command(self, cmd: str) -> Optional[str]:
        """Returns the category for a command string, or None if not explicitly defined."""
        
        # Check exact matches first
        for cat, cmds in self.categories.items():
            if cmd in cmds:
                return cat
        
        # Check if the binary (first word) is in the lists
        binary = cmd.split()[0] if cmd else ""
        for cat, cmds in self.categories.items():
            if binary in cmds:
                return cat

        return None
