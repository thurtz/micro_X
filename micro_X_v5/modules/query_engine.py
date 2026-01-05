
import logging
import os
import sys
import re
from .rag_manager import RAGManager
from modules import config_handler
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

def merge_configs(base, override):
    """ Helper function to recursively merge dictionaries. """
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_config():
    """Loads the main application configuration."""
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'config')
    DEFAULT_CONFIG_FILENAME = "default_config.json"
    USER_CONFIG_FILENAME = "user_config.json"

    default_config_path = os.path.join(CONFIG_DIR, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(CONFIG_DIR, USER_CONFIG_FILENAME)

    config = config_handler.load_jsonc_file(default_config_path)
    if config is None:
        logger.error("CRITICAL: Default configuration not found. Exiting.")
        sys.exit(1)

    user_settings = config_handler.load_jsonc_file(user_config_path)
    if user_settings:
        config = merge_configs(config, user_settings)

    return config

def query_knowledge_base(kb_name: str, query: str) -> str:
    """
    Queries a specified knowledge base.

    Args:
        kb_name: The name of the knowledge base to query.
        query: The query string.

    Returns:
        The query result.
    """
    try:
        config = load_config()
        rag_manager = RAGManager(config=config, name=kb_name)
        rag_manager.initialize()
        if not rag_manager.vector_store:
            return f"Knowledge base '{kb_name}' not found or failed to load."
        
        result_chunks = rag_manager.query(query)
        
        # Join the chunks and clean up whitespace
        if result_chunks:
            full_response = "\n\n---\n\n".join(result_chunks)
            # Replace multiple newlines with a single one, and strip leading/trailing whitespace
            clean_response = re.sub(r'\n{3,}', '\n\n', full_response).strip()
            return clean_response
        else:
            return "No relevant information found in the knowledge base."
    except Exception as e:
        logger.error(f"An error occurred while querying the knowledge base: {e}")
        return "An error occurred while querying the knowledge base."

async def query_knowledge_base_rag(kb_name: str, query: str) -> str:
    """Retrieves context from RAG and generates a response using an LLM."""
    config = load_config()
    rag_manager = RAGManager(config=config, name=kb_name)
    rag_manager.initialize()
    if not rag_manager.vector_store:
        return f"Knowledge base '{kb_name}' not found or failed to load."

    context_chunks = rag_manager.query(query, n_results=5)

    if not context_chunks:
        return "I could not find any relevant information in the knowledge base to answer your question."

    context = "\n\n---\n\n".join(context_chunks)

    template = """
    You are an assistant for question-answering tasks.
    Use the following pieces of retrieved context to answer the question.
    If you don't know the answer, just say that you don't know.
    Keep the answer concise and relevant.
    Do not include your thinking process or any XML-style tags like <think> in your final response.

    Context:
    {context}

    Question: {question}

    Answer:
    """
    prompt = ChatPromptTemplate.from_template(template)

    llm_model_name = config.get('ai_models', {}).get('router', {}).get('model', 'herawen/lisa')
    llm = OllamaLLM(model=llm_model_name)

    chain = prompt | llm

    raw_response = await chain.ainvoke({"context": context, "question": query})
    
    # Programmatically strip the <think> block as a fallback
    clean_response = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
    
    return clean_response
