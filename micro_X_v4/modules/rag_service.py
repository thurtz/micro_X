# micro_X_v4/modules/rag_service.py

import os
import logging
import asyncio
from typing import Optional
from langchain_chroma import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings

from ..core.events import EventBus, Event, EventType
from ..core.config import ConfigManager

logger = logging.getLogger(__name__)

class RagService:
    """
    V2 RAG Service.
    Handles querying the vector store for documentation.
    """
    def __init__(self, bus: EventBus, config: ConfigManager, ollama_service):
        self.bus = bus
        self.config = config
        self.ollama_service = ollama_service
        self.vector_store = None
        self._initialized = False
        
        # Subscribe
        self.bus.subscribe_async(EventType.APP_STARTED, self._initialize)
        self.bus.subscribe_async(EventType.RAG_QUERY_REQUESTED, self._on_query)

    async def _initialize(self, event: Event):
        # Run init in thread to avoid blocking loop
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self):
        try:
            model_name = self.config.get('intent_classification.embedding_model', 'nomic-embed-text')
            base_dir = self.config.get_base_dir() if hasattr(self.config, 'get_base_dir') else os.getcwd()
            
            # Hardcoded to the known docs path for V2 demo
            db_path = os.path.join(base_dir, "knowledge_bases", "micro_X_docs")
            
            if not os.path.exists(db_path):
                logger.warning(f"RAG DB path not found: {db_path}")
                return

            embeddings = OllamaEmbeddings(model=model_name)
            self.vector_store = Chroma(
                collection_name="microx_rag_micro_X_docs",
                embedding_function=embeddings,
                persist_directory=db_path
            )
            self._initialized = True
            logger.info("RAG Service initialized.")
        except Exception as e:
            logger.error(f"Failed to init RAG: {e}")

    async def direct_query(self, query: str) -> str:
        """Direct method for agents to query RAG."""
        if not self._initialized:
            return "RAG Service not initialized."
            
        try:
            results = await asyncio.to_thread(self._query_sync, query)
            if not results:
                return "No relevant documentation found."
            
            answer = await self._generate_answer(query, results)
            return answer
        except Exception as e:
            logger.error(f"RAG direct query failed: {e}")
            return f"Error querying docs: {e}"

    async def _on_query(self, event: Event):
        if not self._initialized:
            await self._broadcast_response("⚠️ RAG Service not initialized (database missing?).")
            return

        query = event.payload.get('query', "")
        if not query: return
        
        await self.bus.publish(Event(EventType.AI_PROCESSING_STARTED, sender="RagService"))
        
        try:
            # 1. Retrieve
            results = await asyncio.to_thread(self._query_sync, query)
            
            if not results:
                await self._broadcast_response("No relevant documentation found.")
                return

            # 2. Generate
            answer = await self._generate_answer(query, results)
            
            # 3. Format Output (Hide snippets to match V1 style)
            full_response = f"📘 **Documentation Answer**:\n{answer}"
            
            await self._broadcast_response(full_response)
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            await self._broadcast_response("❌ Failed to query documentation.")

    async def _generate_answer(self, query: str, docs) -> str:
        """Uses Ollama to synthesize an answer from the docs."""
        context = "\n\n---\n\n".join([d.page_content for d in docs])
        
        # V1 uses the 'router' model for RAG (often a better chat model)
        model_name = self.config.get("ai_models.router.model", "qwen3:0.6b")
        
        # Prompt from V1
        prompt = (
            "You are an assistant for question-answering tasks. "
            "Use the following pieces of retrieved context to answer the question. "
            "If you don't know the answer, just say that you don't know. "
            "Keep the answer concise and relevant. "
            "Do not include your thinking process or any XML-style tags like <think> in your final response.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )
        
        try:
            if not self.ollama_service._is_running:
                return "Ollama service is not available."

            import ollama
            response = await asyncio.to_thread(
                ollama.generate,
                model=model_name,
                prompt=prompt
            )
            raw_text = response['response'].strip()
            return self._clean_response(raw_text)
        except Exception as e:
            logger.error(f"RAG generation failed: {e}")
            return "Could not generate answer from context."

    def _clean_response(self, text: str) -> str:
        """Strips reasoning tags like <think>...</think> from the AI output."""
        import re
        if not text: return ""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()

    def _query_sync(self, query: str):
        # Simple similarity search
        return self.vector_store.similarity_search(query, k=5)

    def _format_results(self, docs) -> str:
        if not docs:
            return "No relevant documentation found."
        
        text = "📚 Documentation Results:\n"
        for i, doc in enumerate(docs):
            source = doc.metadata.get('source', 'Unknown')
            content = doc.page_content[:200].replace("\n", " ") + "..."
            text += f"\n{i+1}. [{os.path.basename(source)}]\n   {content}\n"
        return text

    async def _broadcast_response(self, text: str):
        # We output this as an "Execution Output" so it shows in the log
        # but logically it finishes the flow
        await self.bus.publish(Event(
            type=EventType.EXECUTION_OUTPUT,
            payload={'output': text},
            sender="RagService"
        ))
        await self.bus.publish(Event(EventType.EXECUTION_FINISHED))
