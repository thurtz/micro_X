# utils/lc_explainer.py

import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

# --- Logging Setup ---
logger = logging.getLogger(__name__)

async def get_ai_explanation(command_to_explain: str, config_param: dict) -> str | None:
    """
    Uses a LangChain chain to explain a given Linux command.

    Args:
        command_to_explain: The command string to be explained.
        config_param: The main application configuration object.

    Returns:
        The AI-generated explanation as a string, or None on error.
    """
    logger.info(f"Requesting LangChain explanation for command: '{command_to_explain}'")
    if not command_to_explain:
        return "Cannot explain an empty command."

    try:
        # 1. Extract configuration from the dict
        explainer_config = config_param.get('ai_models', {}).get('explainer', {})
        if isinstance(explainer_config, dict):
            model_name = explainer_config.get('model')
            model_options = explainer_config.get('options')
        else:
            model_name = explainer_config
            model_options = None

        explainer_prompts = config_param.get('prompts', {}).get('explainer')

        if not model_name or not explainer_prompts:
            logger.error("Explainer AI model or prompts not configured for LangChain.")
            return "AI Explainer model/prompts not configured."

        system_prompt = explainer_prompts['system']
        user_prompt_template = explainer_prompts['user_template']

        # 2. Set up the LangChain chain
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt_template)
        ])
        
        chat_model_args = {"model": model_name}
        if model_options:
            chat_model_args["options"] = model_options
            
        model = ChatOllama(**chat_model_args)
        
        output_parser = StrOutputParser()

        chain = prompt | model | output_parser

        # 3. Invoke the chain
        logger.info(f"Invoking LangChain explainer (model: {model_name}) for: '{command_to_explain}'")
        
        explanation = await chain.ainvoke({"command_text": command_to_explain})
        
        logger.debug(f"LangChain Explainer response: {explanation}")
        return explanation if explanation else "AI Explainer returned an empty response."

    except Exception as e:
        logger.error(f"Error in LangChain explainer for '{command_to_explain}': {e}", exc_info=True)
        return f"An error occurred during explanation: {e}"
