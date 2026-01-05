# micro_X_v4/core/agent_graph.py

import logging
from typing import TypedDict, Annotated, List, Literal, Union
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from .tools import search_documentation, propose_shell_command, run_internal_utility
from .events import EventBus, Event, EventType

logger = logging.getLogger(__name__)

# --- Prompts ---
SYSTEM_PROMPT = """You are micro_X, a specialized AI shell assistant. 
Your goal is to help users manage their system efficiently.

RULES:
1. For questions about micro_X's features, documentation, or "how-to" guides, ALWAYS use the 'search_documentation' tool.
2. For ANY request that can be answered by a Linux command (including "what is...", "show me...", "check..."), ALWAYS use the 'propose_shell_command' tool.
   - Example: "what is the current directory" -> propose_shell_command("pwd")
   - Example: "list files" -> propose_shell_command("ls")
3. For running specific internal micro_X utility scripts (like 'snapshot', 'tree', 'logs'), use 'run_internal_utility'.
4. If the user is just greeting you or chatting, respond directly without tools.

Be concise and professional."""

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
        # Prepend system prompt if not present
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
            
        response = await self.llm_with_tools.ainvoke(messages)
        
        # --- FIX: Manual parsing for small models (Qwen 0.5B) that output XML ---
        import re
        content = response.content
        if not response.tool_calls and isinstance(content, str):
            # Regex for <tool_name query="..."> format
            # Example: <search_documentation query="what is micro_X?" />
            tool_pattern = re.compile(r'<(\w+)\s+([^>]+?)\s*/?>')
            match = tool_pattern.search(content)
            
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                
                # Parse args (simple "key=value" parsing)
                args = {}
                # Regex for key="value"
                arg_pattern = re.compile(r'(\w+)="([^"]+)"')
                for arg_match in arg_pattern.finditer(args_str):
                    args[arg_match.group(1)] = arg_match.group(2)
                
                # Construct manual tool call
                import uuid
                tool_call = {
                    'name': tool_name,
                    'args': args,
                    'id': str(uuid.uuid4())
                }
                
                logger.info(f"Manually parsed tool call from XML: {tool_name} with args {args}")
                
                # Verify it's a valid tool
                valid_tools = [t.name for t in self.tools]
                if tool_name in valid_tools:
                    response.tool_calls = [tool_call]
                    # response.content = "" # Optional: Clear content so we don't print the raw XML

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
