# micro_X_v4/modules/ollama_service.py

import asyncio
import shutil
import subprocess
import logging
import re
import ollama
import os
from typing import Optional
import ollama
import os
import shutil
import subprocess
import logging

from ..core.events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

class OllamaService:
    """
    V2 Ollama Service.
    Handles the lifecycle of the Ollama daemon and provides AI capabilities.
    """
    TMUX_SESSION_NAME = "micro_x_v2_ollama"

    def __init__(self, bus: EventBus, config_manager):
        self.bus = bus
        self.config = config_manager
        self._exe_path: Optional[str] = None
        self._is_running: bool = False

        # Subscribe to system events
        self.bus.subscribe_async(EventType.APP_STARTED, self._on_app_started)
        self.bus.subscribe_async(EventType.OLLAMA_START_REQUESTED, self.start_service)
        self.bus.subscribe_async(EventType.OLLAMA_STOP_REQUESTED, self.stop_service)
        self.bus.subscribe_async(EventType.AI_EXPLAIN_REQUESTED, self._on_explain_requested)
        self.bus.subscribe_async(EventType.AI_ANALYZE_ERROR, self._on_analyze_error)

    async def _on_analyze_error(self, event: Event):
        cmd = event.payload.get('command')
        output = event.payload.get('output')
        
        await self.bus.publish(Event(EventType.AI_PROCESSING_STARTED, sender="OllamaService"))
        
        analysis = await self.analyze_error(cmd, output)
        
        # We reuse EXPLANATION_READY or create a new one?
        # Reusing explanation ready is fine, it displays text.
        await self.bus.publish(Event(
            type=EventType.AI_EXPLANATION_READY,
            payload={'explanation': f"🔧 **Error Analysis**:\n{analysis}"},
            sender="OllamaService"
        ))
        
        # Reset state to IDLE so user can type new command
        await self.bus.publish(Event(EventType.EXECUTION_FINISHED))

    async def _on_explain_requested(self, event: Event):
        cmd = event.payload.get('command')
        if not cmd: return
        
        explanation = await self.explain_command(cmd)
        await self.bus.publish(Event(
            type=EventType.AI_EXPLANATION_READY,
            payload={'explanation': explanation},
            sender="OllamaService"
        ))

    async def _on_app_started(self, event: Event):
        logger.info("OllamaService: App started, checking status...")
        self._exe_path = await self._find_executable()
        
        # Configure host/port from config
        host = self.config.get("ollama_service.ollama_host", "localhost")
        port = self.config.get("ollama_service.ollama_port", 11434)
        os.environ['OLLAMA_HOST'] = f"{host}:{port}"

        if not self._exe_path:
             await self._broadcast_error("Ollama executable not found.")
             return

        is_up = await self.is_server_responsive()
        self._is_running = is_up
        await self._broadcast_status()

    async def _find_executable(self) -> Optional[str]:
        path = self.config.get("ollama_service.executable_path")
        if not path:
            path = shutil.which("ollama")
        return path

    async def is_server_responsive(self) -> bool:
        try:
            await asyncio.to_thread(ollama.list)
            return True
        except Exception:
            return False

    async def _broadcast_status(self):
        await self.bus.publish(Event(
            type=EventType.OLLAMA_STATUS_CHANGED,
            payload={'running': self._is_running},
            sender="OllamaService"
        ))

    async def _broadcast_error(self, msg: str):
        await self.bus.publish(Event(
            type=EventType.OLLAMA_ERROR,
            payload={'message': msg},
            sender="OllamaService"
        ))

    def _clean_response(self, text: str) -> str:
        """Strips reasoning tags like <think>...</think> from the AI output."""
        if not text:
            return ""
        # Remove anything between <think> and </think> (including the tags)
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()

    async def start_service(self, event: Optional[Event] = None):
        if await self.is_server_responsive():
            self._is_running = True
            await self._broadcast_status()
            return

        if not self._exe_path:
            await self._broadcast_error("Cannot start: Executable unknown.")
            return

        logger.info("OllamaService: Launching 'ollama serve' in tmux...")
        cmd = ["tmux", "new-session", "-d", "-s", self.TMUX_SESSION_NAME, f"{self._exe_path} serve"]
        try:
            await asyncio.to_thread(subprocess.run, cmd, check=True)
            # Wait for readiness
            retries = self.config.get("ollama_service.server_check_retries", 5)
            interval = self.config.get("ollama_service.server_check_interval_seconds", 2)
            for _ in range(retries):
                await asyncio.sleep(interval)
                if await self.is_server_responsive():
                    self._is_running = True
                    await self._broadcast_status()
                    return
            
            await self._broadcast_error("Server failed to start in time.")
        except Exception as e:
            await self._broadcast_error(f"Failed to launch tmux: {e}")

    async def stop_service(self, event: Optional[Event] = None):
        logger.info("OllamaService: Stopping tmux session...")
        cmd = ["tmux", "kill-session", "-t", self.TMUX_SESSION_NAME]
        try:
            await asyncio.to_thread(subprocess.run, cmd, check=False)
            await asyncio.sleep(1)
            self._is_running = await self.is_server_responsive()
            await self._broadcast_status()
        except Exception as e:
            await self._broadcast_error(f"Error stopping service: {e}")

    async def validate_command(self, cmd: str) -> bool:
        """Uses a specialized model to check if the string is a valid command."""
        if not self._is_running: return False
        
        model = self.config.get("ai_models.validator.model", "qwen3:0.6b")
        system_prompt = self.config.get("prompts.validator.system", "")
        user_template = self.config.get("prompts.validator.user_template", "{command_text}")
        prompt = user_template.format(command_text=cmd)
        
        try:
            response = await asyncio.to_thread(
                ollama.generate, model=model, system=system_prompt, prompt=prompt
            )
            text = self._clean_response(response['response']).lower()
            return "yes" in text
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return True # Fail open (assume valid) if validator crashes? Or False? V1 usually fails open or retries.

    async def generate_command(self, prompt: str) -> Optional[str]:
        """High-level method to translate NL to shell command with validation."""
        if not self._is_running:
            return None
        
        model_name = self.config.get("ai_models.primary_translator.model", "llama3.2:3b")
        retries = self.config.get("behavior.translation_validation_cycles", 3)
        
        current_prompt = f"Translate this to a single linux command. Output ONLY the command: {prompt}"
        
        for attempt in range(retries):
            try:
                logger.info(f"OllamaService: Generating (Attempt {attempt+1}/{retries})...")
                response = await asyncio.to_thread(
                    ollama.generate, 
                    model=model_name,
                    prompt=current_prompt
                )
                candidate = self._clean_response(response['response'])
                
                # Validation Step
                logger.info(f"OllamaService: Validating '{candidate}'...")
                is_valid = await self.validate_command(candidate)
                
                if is_valid:
                    return candidate
                else:
                    logger.warning(f"OllamaService: Validation failed for '{candidate}'. Retrying...")
                    # Feedback for next attempt (Chain of Thought simulation)
                    current_prompt += f"\n\nYour previous output '{candidate}' was marked as invalid. Please provide a valid Linux command."
            
            except Exception as e:
                logger.error(f"Ollama generation error: {e}")
                return None
        
        logger.error("OllamaService: Failed to generate valid command after retries.")
        return None

    async def explain_command(self, cmd: str) -> Optional[str]:
        if not self._is_running: return None
        
        model_name = self.config.get("ai_models.explainer.model", "qwen3:0.6b")
        system_prompt = self.config.get("prompts.explainer.system", "")
        user_template = self.config.get("prompts.explainer.user_template", "{command_text}")
        user_prompt = user_template.format(command_text=cmd)

        try:
            response = await asyncio.to_thread(
                ollama.generate,
                model=model_name,
                system=system_prompt,
                prompt=user_prompt
            )
            return self._clean_response(response['response'])
        except Exception as e:
            logger.error(f"Ollama explanation failed: {e}")
            return "Failed to get explanation."

    async def analyze_error(self, cmd: str, output: str) -> str:
        if not self._is_running: return "Ollama not running."
        
        # Use explainer model or primary? Explainer is good for text.
        model_name = self.config.get("ai_models.explainer.model", "qwen3:0.6b")
        prompt = f"The command `{cmd}` failed with the following output:\n\n{output}\n\nExplain why it failed and suggest a fix. Be concise."
        
        try:
            response = await asyncio.to_thread(
                ollama.generate,
                model=model_name,
                prompt=prompt
            )
            return self._clean_response(response['response'])
        except Exception as e:
            return f"Analysis failed: {e}"
