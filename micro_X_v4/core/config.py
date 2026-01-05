# micro_X_v2/core/config.py

import os
import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    V2 Configuration Manager.
    Loads default and user configurations, merging them into a single structure.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config_dir = os.path.join(base_dir, "config")
        self._config: Dict[str, Any] = {}
        
        self.load_all()

    def _strip_comments(self, content: str) -> str:
        """Strips // and /* */ comments from a string."""
        comment_pattern = re.compile(r'//.*?$|/\*.*?\*/', re.DOTALL | re.MULTILINE)
        return re.sub(comment_pattern, '', content)

    def _load_jsonc(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Config file not found: {path}")
            return {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            clean_content = self._strip_comments(content)
            return json.loads(clean_content)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return {}

    def _merge_dicts(self, base: Dict, overlay: Dict):
        """Recursively merges overlay into base."""
        for key, value in overlay.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def load_all(self):
        """Loads default_config.json and overlays user_config.json."""
        # 1. Load defaults
        self._config = self._load_jsonc("default_config.json")
        
        # 2. Overlay user config if it exists
        user_config = self._load_jsonc("user_config.json")
        if user_config:
            self._merge_dicts(self._config, user_config)
            logger.info("User configuration merged.")
        
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation (e.g., 'ai_translation.model').
        """
        parts = key_path.split(".")
        val = self._config
        try:
            for part in parts:
                val = val[part]
            return val
        except (KeyError, TypeError):
            return default
            
    def get_base_dir(self) -> str:
        return self.base_dir

    @property
    def data(self) -> Dict[str, Any]:
        return self._config
