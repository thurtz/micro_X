# micro_X_v2/modules/router_service.py

import logging
import asyncio
import ollama
from typing import Optional
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class RouterService:
    """
    V2 Router Service.
    Uses an LLM to decide if a query is for the Shell, Documentation, or other.
    """
    def __init__(self, config: ConfigManager):
        self.config = config

    async def route_input(self, user_input: str) -> str:
        """
        Classifies input into: 'SHELL', 'DOCS', or 'CHAT'.
        """
        text = user_input.lower()
        
        # 1. Strong Heuristics (Faster & More Reliable for small models)
        if "micro_x" in text or "microx" in text:
            return "DOCS"
            
        # Common shell verbs usually imply action
        shell_verbs = ["list", "show", "get", "set", "run", "delete", "remove", "create", "make", "check", "find", "search"]
        if any(text.startswith(v) for v in shell_verbs):
            return "SHELL"
            
        # "What is..." questions about current directory/files are usually shell
        if text.startswith("what is") and ("directory" in text or "file" in text or "ip" in text):
            return "SHELL"

        model_name = self.config.get("ai_models.router.model", "qwen3:0.6b")
        
        # Improved few-shot prompt
        prompt = (
            "You are a routing assistant for the micro_X AI Shell. "
            "Classify the user input into exactly one category.\n\n"
            "Categories:\n"
            "- SHELL: A request to perform a system action, file operation, or run a command. Also includes general Linux 'how-to' questions.\n"
            "- DOCS: A question specifically about the micro_X tool, its features, internal configuration, or setup.\n"
            "- CHAT: General conversation, greetings, or off-topic talk.\n\n"
            "Examples:\n"
            "Input: 'show me my files' -> SHELL\n"
            "Input: 'how do I use the tree command' -> DOCS\n"
            "Input: 'how do I copy a file in linux' -> SHELL\n"
            "Input: 'what directory am I in' -> SHELL\n"
            "Input: 'tell me about the snapshot tool' -> DOCS\n"
            "Input: 'check disk usage' -> SHELL\n"
            "Input: 'how do I change the micro_X model' -> DOCS\n\n"
            f"Input: \"{user_input}\"\n\n"
            "Output ONLY the word SHELL, DOCS, or CHAT."
        )

        try:
            logger.info(f"RouterService: Routing '{user_input}' using {model_name}...")
            response = await asyncio.to_thread(
                ollama.generate,
                model=model_name,
                prompt=prompt
            )
            result = response['response'].strip().upper()
            
            # Basic cleanup/validation
            if "DOCS" in result: return "DOCS"
            if "CHAT" in result: return "CHAT"
            # Default to SHELL for safety/utility
            return "SHELL"
            
        except Exception as e:
            logger.error(f"RouterService failed: {e}")
            return "SHELL" # Fallback
