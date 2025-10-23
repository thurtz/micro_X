# modules/ai_handler.py

import logging
from modules.lc_agent import run_agent as run_lc_agent
from utils.lc_explainer import get_ai_explanation as get_lc_explanation

# --- Logging Setup ---
logger = logging.getLogger(__name__)

async def get_validated_ai_command(human_query: str, config_param: dict, append_output_func, get_app_func) -> tuple[str | None, str | None]:
    """Translates a natural language query into a validated shell command using the LangGraph agent.

    This function now acts as a simple wrapper, delegating the entire complex workflow
    of translation, validation, and retries to the LangGraph agent implemented in `lc_agent.py`.

    Args:
        human_query (str): The user's natural language query.
        config_param (dict): The main application configuration object.
        append_output_func: A reference to UIManager.append_output for UI updates (passed for compatibility).
        get_app_func: A reference to UIManager.get_app_instance for UI invalidation (passed for compatibility).

    Returns:
        tuple[str | None, str | None]: A tuple containing the validated command
        and the raw AI response from the agent's final step.
    """
    logger.info(f"Delegating validated translation for: '{human_query}' to LangGraph agent.")
    
    # The new LangGraph agent handles all the logic internally.
    validated_command, raw_response = await run_lc_agent(human_query)
    
    if validated_command:
        append_output_func(f"✅ Agent returned validated command: '{validated_command}'", style_class='success')
    else:
        append_output_func("❌ Agent failed to produce a validated command.", style_class='error')
        
    return validated_command, raw_response

async def explain_linux_command_with_ai(command_to_explain: str, config_param: dict, append_output_func) -> str | None:
    """
    Wrapper that calls the LangChain-based explanation utility.

    Args:
        command_to_explain: The command string to be explained.
        config_param: The main application configuration object.
        append_output_func: A reference to UIManager.append_output for UI updates.

    Returns:
        The AI-generated explanation as a string, or a fallback
        message/None on error.
    """
    # This function now delegates to the LangChain implementation.
    return await get_lc_explanation(command_to_explain, config_param)