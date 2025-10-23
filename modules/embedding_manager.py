# modules/embedding_manager.py
import logging
import json
import os
import numpy as np
import ollama
import httpx
import aiohttp

logger = logging.getLogger(__name__)

async def _get_mcp_context() -> dict:
    """Fetches the full context from the MCP server."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8123/context")
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"MCP server returned status {response.status_code} for context fetch.")
            return {}
    except httpx.RequestError:
        logger.warning("Could not connect to MCP server to fetch context.")
        return {}

class EmbeddingManager:
    def __init__(self):
        self.client = None
        self.intents = {}
        self.intent_embeddings = {}
        self.embedding_model = None

    async def _load_intents_from_file(self):
        """Loads intents from the JSON file specified in the config."""
        context = await _get_mcp_context()
        config = context.get("config", {})
        intents_path = config.get('intent_classification', {}).get('intents_file_path')
        if not intents_path:
            logger.error("Intents file path not found in config.")
            return False
        
        # Ensure the path is absolute
        if not os.path.isabs(intents_path):
            # Assuming the path is relative to the project root. 
            # This might need adjustment if the script runs from a different CWD.
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            intents_path = os.path.join(base_dir, intents_path)

        try:
            with open(intents_path, 'r') as f:
                self.intents = json.load(f)
            logger.info(f"Successfully loaded {len(self.intents)} intents from {intents_path}")
            return True
        except FileNotFoundError:
            logger.error(f"Intents file not found at: {intents_path}")
            return False
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from intents file: {intents_path}")
            return False

    async def initialize(self):
        """
        Initializes the Ollama client and generates embeddings for all intents.
        """
        if not await self._load_intents_from_file():
            return

        context = await _get_mcp_context()
        config = context.get("config", {})
        self.embedding_model = config.get('intent_classification', {}).get('embedding_model')
        if not self.embedding_model:
            logger.error("Embedding model not specified in config.")
            return

        try:
            self.client = ollama.Client()
            logger.info("Ollama client initialized successfully.")
            self._generate_intent_embeddings()
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}", exc_info=True)
            self.client = None

    def _generate_intent_embeddings(self):
        """
        Generates and caches the average embedding for each intent.
        """
        if not self.client:
            logger.warning("Cannot generate intent embeddings: Ollama client not available.")
            return

        logger.info(f"Generating embeddings for {len(self.intents)} intents using model: {self.embedding_model}...")
        for intent, phrases in self.intents.items():
            try:
                # Get embeddings for all phrases of an intent
                phrase_embeddings = [self.client.embeddings(model=self.embedding_model, prompt=phrase)['embedding'] for phrase in phrases]
                
                # Average the embeddings to get a single representative vector for the intent
                self.intent_embeddings[intent] = np.mean(phrase_embeddings, axis=0)
                logger.debug(f"Generated embedding for intent: {intent}")

            except Exception as e:
                logger.error(f"Failed to generate embedding for intent '{intent}': {e}", exc_info=True)
        
        logger.info("Finished generating all intent embeddings.")

    def classify_intent(self, user_input: str) -> tuple[str | None, float]:
        """
        Classifies the user input against known intents.

        Args:
            user_input: The raw input from the user.

        Returns:
            A tuple of (intent_name, similarity_score).
            Returns (None, 0.0) if classification is not possible.
        """
        if not self.client or not self.intent_embeddings:
            logger.warning("Cannot classify intent: EmbeddingManager not ready.")
            return None, 0.0

        try:
            # Embed the user input
            input_embedding = np.array(self.client.embeddings(model=self.embedding_model, prompt=user_input)['embedding'])

            # Calculate cosine similarity against all intent embeddings
            best_match_intent = None
            highest_similarity = -1.0

            for intent, intent_embedding in self.intent_embeddings.items():
                # Cosine similarity calculation
                cos_sim = np.dot(input_embedding, intent_embedding) / (np.linalg.norm(input_embedding) * np.linalg.norm(intent_embedding))
                
                if cos_sim > highest_similarity:
                    highest_similarity = cos_sim
                    best_match_intent = intent
            
            logger.info(f"Classified input '{user_input}' as intent '{best_match_intent}' with similarity {highest_similarity:.4f}")
            return best_match_intent, highest_similarity

        except Exception as e:
            logger.error(f"Failed to classify intent for input '{user_input}': {e}", exc_info=True)
            return None, 0.0

