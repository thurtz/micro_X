# modules/router_agent.py

import logging
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from modules.intent_tools import get_all_tools

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# This prompt is designed for a ReAct-style agent that thinks step-by-step.
# It instructs the LLM to use the provided tools if they are appropriate.
REACT_PROMPT = ChatPromptTemplate.from_template("""
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}
""")


def create_router_agent(config: dict):
    """Creates and returns a LangChain agent configured for routing intents to tools."""
    logger.debug("Creating Router Agent.")
    
    # For now, we'll use the explainer model, but this could be a dedicated model.
    router_config = config.get('ai_models', {}).get('router', {})
    model_name = router_config.get('model') if isinstance(router_config, dict) else router_config

    if not model_name:
        logger.error("Model for Router Agent not configured. Agent will not work.")
        return None

    llm = ChatOllama(model=model_name, temperature=0)
    tools = get_all_tools()
    
    agent = create_react_agent(llm, tools, REACT_PROMPT)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False, # Set to True for debugging agent thoughts
        handle_parsing_errors=True # Gracefully handle if the LLM messes up formatting
    )
    
    return agent_executor

async def run_router_agent(agent_executor, human_query: str) -> str | None:
    """ 
    Runs the router agent and returns the resulting command if a tool is used.
    
    Returns:
        A string command if a tool was successfully used, otherwise None.
    """
    if not agent_executor:
        logger.warning("Router agent is not available.")
        return None
        
    logger.info(f"Running router agent for query: '{human_query}'")
    try:
        # We are using ainvoke for the async call
        result = await agent_executor.ainvoke({"input": human_query})
        
        # The output of our tools is the command string itself.
        # If a tool was used, the 'output' key will contain that string.
        # If no tool was used, the LLM might just answer directly.
        # We check if the output is one of the commands our tools could have produced.
        
        # This is a simple way to check. A more robust way would be to have tools return
        # a structured object, but for now, this works.
        output = result.get("output", "")
        if output.startswith("/"):
            logger.info(f"Router agent decided to use a tool, resulting in command: {output}")
            return output
        else:
            # This means the LLM decided not to use a tool and just answered the question.
            # In our hybrid system, this is a signal to fall back to the next step.
            logger.info("Router agent did not select a tool.")
            return None
            
    except Exception as e:
        logger.error(f"Error running router agent: {e}", exc_info=True)
        return None
