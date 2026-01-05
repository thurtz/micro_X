# micro_X_v3/core/agent_graph.py

import logging
from typing import TypedDict, Annotated, List, Literal, Union
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from .tools import search_documentation, propose_shell_command, run_internal_utility
from .events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

# --- State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_input: str
    final_action: str | None

# --- Nodes ---

class MicroXAgent:
    def __init__(self, config, bus: EventBus, rag_service, utility_service, ollama_service):
        self.config = config
        self.bus = bus
        self.rag_service = rag_service
        self.utility_service = utility_service
        self.ollama_service = ollama_service
        
        # Initialize LLM
        model_name = config.get('ai_models.router.model', 'qwen3:0.6b')
        self.llm = ChatOllama(model=model_name, temperature=0)
        
        # Bind tools
        self.tools = [search_documentation, propose_shell_command, run_internal_utility]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    async def call_model(self, state: AgentState):
        messages = state['messages']
        response = await self.llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def execute_tools(self, state: AgentState):
        """Custom tool execution node to handle side effects."""
        messages = state['messages']
        last_message = messages[-1]
        
        results = []
        
        for tool_call in last_message.tool_calls:
            name = tool_call['name']
            args = tool_call['args']
            tool_call_id = tool_call['id']
            
            output = ""
            
            if name == "search_documentation":
                # Call RAG Service
                query = args.get('query')
                # We need to bridge to RagService. 
                # RagService logic is async and event-driven. 
                # Ideally we call a method on it directly.
                # Assuming RagService has a direct query method (we need to add one).
                output = await self.rag_service.direct_query(query)
                
            elif name == "run_internal_utility":
                # Call Utility Service
                util_name = args.get('utility_name')
                util_args = args.get('arguments', "").split()
                # Assuming UtilityService has a direct run method
                await self.utility_service.direct_run(util_name, util_args)
                output = f"Utility {util_name} executed."
                
            elif name == "propose_shell_command":
                # Delegate to OllamaService (Translator Model)
                query = args.get('query')
                logger.info(f"Agent delegated translation for: '{query}'")
                
                # We await the specialized translator
                cmd = await self.ollama_service.generate_command(query)
                
                if cmd:
                    output = f"COMMAND_PENDING: {cmd}"
                else:
                    output = "Translation Failed."
            
            results.append(ToolMessage(content=output, tool_call_id=tool_call_id, name=name))
            
        return {"messages": results}

    def route_after_model(self, state: AgentState) -> Literal["tools", "__end__"]:
        messages = state['messages']
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return "__end__"

    def build_graph(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.execute_tools)
        
        workflow.add_edge(START, "agent")
        
        workflow.add_conditional_edges(
            "agent",
            self.route_after_model,
            {"tools": "tools", "__end__": END}
        )
        
        # After tools, we go back to agent to synthesize answer?
        # Or end? 
        # If it was a shell command proposal, we want to END so LogicEngine can handle confirmation.
        workflow.add_edge("tools", END)
        
        return workflow.compile()
