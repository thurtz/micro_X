# modules/router_agent.py

import logging
import contextlib
import io
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from .router_tools import get_all_tools

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# This is a much simpler prompt designed for native tool-calling models.
# It instructs the model that it has access to tools and should use them when appropriate.
TOOL_CALLING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a specialized assistant with one job: to select a tool to answer the user's question and output the result.
- If a tool is used, your final answer MUST be only the direct output from that tool.
- Do not add any conversation, explanation, or extra text.
- If no tool is appropriate, you must output the phrase 'I am sorry, but I cannot answer that question.'"""),
    ("user", "{input}"),
    # This placeholder is where the agent will add its tool usage history.
    ("placeholder", "{agent_scratchpad}"),
])


def create_router_agent(config: dict):
    """Creates and returns a LangChain agent configured for native tool calling."""
    logger.debug("Creating Tool-Calling Router Agent.")
    
    router_config = config.get('ai_models', {}).get('router', {})
    model_name = router_config.get('model') if isinstance(router_config, dict) else router_config

    if not model_name:
        logger.error("Model for Router Agent not configured. Agent will not work.")
        return None

    # Llama 3 models are particularly good at tool calling.
    llm = ChatOllama(model=model_name, temperature=0)
    tools = get_all_tools()
    
    # This agent is designed to work with models that support native tool calling.
    # It is more robust than the ReAct agent.
    agent = create_tool_calling_agent(llm, tools, TOOL_CALLING_PROMPT)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False, # Keep verbose for now to confirm it works
        handle_parsing_errors=True,
        return_intermediate_steps=True # This is the crucial change
    )
    
    return agent_executor

async def run_router_agent(agent_executor, human_query: str) -> str | None:
    """ 
    Runs the router agent and returns the resulting command if a tool is used.
    Redirects verbose stdout to the logger.
    """
    if not agent_executor:
        logger.warning("Router agent is not available.")
        return None
        
    logger.info(f"Running tool-calling router agent for query: '{human_query}'")
    try:
        # Redirect the agent's verbose print output to the logger
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = await agent_executor.ainvoke({"input": human_query})
        agent_output_log = f.getvalue()
        if agent_output_log:
            logger.info(f"Router Agent Internal Steps:\n{agent_output_log}")

        logger.debug(f"Full agent result: {result}")

        # The robust way to get the tool's output is to parse the intermediate steps.
        intermediate_steps = result.get("intermediate_steps", [])
        if intermediate_steps:
            logger.debug(f"Intermediate steps found: {intermediate_steps}")
            # The last step contains the most recent tool call and its output.
            last_step = intermediate_steps[-1]
            action, tool_output = last_step
            
            # The output of our tools is the command string itself.
            if isinstance(tool_output, str) and (tool_output.startswith("/") or tool_output == "pwd"):
                logger.info(f"Router agent extracted command from tool output: {tool_output}")
                return tool_output

        # Fallback for safety, but the primary logic is above.
        logger.warning(f"Could not extract command from intermediate steps. Final agent output: '{result.get('output')}'")
        return None
            
    except Exception as e:
        logger.error(f"Error running router agent: {e}", exc_info=True)
        return None
