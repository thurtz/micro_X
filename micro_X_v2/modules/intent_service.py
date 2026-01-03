# micro_X_v2/modules/intent_service.py

import os
import json
import logging
import numpy as np
import asyncio
import ollama
from typing import Dict, Optional, Tuple

from ..core.events import EventBus, Event, EventType
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class IntentService:
    """
    V2 Intent Service.
    Uses semantic similarity to map natural language to specific commands.
    """
    
    INTENT_COMMAND_MAP = {
        "show_help": "/help",
        "show_history": "/history",
        "ollama_start": "/ollama start",
        "ollama_stop": "/ollama stop",
        "ollama_restart": "/ollama restart",
        "ollama_status": "/ollama status",
        "command_list": "/command --list",
        "alias_list": "/alias --list",
        "generate_project_tree": "/tree",
        "open_docs": "/docs",
        "update_system": "/update",
        "exit_shell": "/exit"
    }

    def __init__(self, bus: EventBus, config: ConfigManager):
        self.bus = bus
        self.config = config
        self.intent_embeddings: Dict[str, np.ndarray] = {}
        self._initialized = False
        
        # Subscribe
        self.bus.subscribe_async(EventType.APP_STARTED, self._on_app_started)

    async def _on_app_started(self, event: Event):
        """Initializes the embeddings in the background."""
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self):
        logger.info("IntentService: Starting background initialization...")
        try:
            intents_file = self.config.get("intent_classification.intents_file_path", "config/intents.json")
            base_dir = self.config.get_base_dir()
            path = os.path.join(base_dir, intents_file)
            
            logger.debug(f"IntentService: Loading intents from {path}")
            if not os.path.exists(path):
                logger.error(f"Intents file not found: {path}")
                return

            with open(path, 'r') as f:
                intents_data = json.load(f)

            model = self.config.get("intent_classification.embedding_model", "nomic-embed-text")
            logger.info(f"IntentService: Generating embeddings for {len(intents_data)} intents using {model}...")

            for intent, phrases in intents_data.items():
                logger.debug(f"IntentService: Embedding intent '{intent}'...")
                phrase_embeddings = [ollama.embeddings(model=model, prompt=phrase)['embedding'] for phrase in phrases]
                self.intent_embeddings[intent] = np.mean(phrase_embeddings, axis=0)
            
            self._initialized = True
            logger.info("IntentService initialization COMPLETE.")
        except Exception as e:
            logger.error(f"IntentService failed to initialize: {e}", exc_info=True)

    async def classify(self, text: str) -> Tuple[Optional[str], float]:
        """
        Classifies the input text against known intents.
        Returns (intent_name, score).
        """
        if not self._initialized or not text:
            logger.debug(f"IntentService: Not initialized or empty text. Initialized: {self._initialized}")
            return None, 0.0

        try:
            model = self.config.get("intent_classification.embedding_model", "nomic-embed-text")
            # Use asyncio.to_thread for the sync ollama call
            response = await asyncio.to_thread(ollama.embeddings, model=model, prompt=text)
            input_embedding = np.array(response['embedding'])

            best_intent = None
            highest_score = -1.0

            for intent, intent_vec in self.intent_embeddings.items():
                # Cosine Similarity
                score = np.dot(input_embedding, intent_vec) / (np.linalg.norm(input_embedding) * np.linalg.norm(intent_vec))
                if score > highest_score:
                    highest_score = score
                    best_intent = intent
            
            return best_intent, highest_score
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return None, 0.0

    def get_command_for_intent(self, intent: str) -> Optional[str]:
        return self.INTENT_COMMAND_MAP.get(intent)
