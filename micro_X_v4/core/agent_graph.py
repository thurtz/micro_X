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
1. For questions about micro_X's features or "how-to" guides, use 'search_documentation'.
   Format: <search_documentation query="your query" />
2. For ANY system request that a Linux command can answer, use 'propose_shell_command'.
   Format: <propose_shell_command query="the linux command" />
3. For internal micro_X utility scripts (snapshot, tree, logs), use 'run_internal_utility'.
   Format: <run_internal_utility utility_name="name" />

ALWAYS respond with a tool call in <tool_name ... /> format. 
DO NOT use JSON. DO NOT use generic <tool_name> tags.
Be concise."""

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
        
        # --- FIX: Robust manual parsing for small models ---
        import re
        import json
        import uuid
        
        content = response.content
        if not response.tool_calls and isinstance(content, str):
            # 1. Try JSON parsing (some models fall back to JSON)
            json_pattern = re.compile(r'\{.*"name":\s*"(\w+)".*\}', re.DOTALL)
            json_match = json_pattern.search(content)
            if json_match:
                try:
                    # Find the actual json block
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    data = json.loads(content[start:end])
                    tool_name = data.get('name') or data.get('tool')
                    args = data.get('arguments') or data.get('args') or {}
                    
                    if tool_name and tool_name != "tool_name":
                        response.tool_calls = [{'name': tool_name, 'args': args, 'id': str(uuid.uuid4())}]
                        logger.info(f"Parsed tool call from JSON: {tool_name}")
                        return {"messages": [response]}
                except: pass

            # 2. Try XML parsing
            # We ignore generic <tool_name ... /> and look for specific tool names
            valid_tool_names = [t.name for t in self.tools]
            tool_pattern = re.compile(r'<(\w+)\s+([^>]+?)\s*/?>')
            
            for match in tool_pattern.finditer(content):
                name = match.group(1)
                if name in valid_tool_names:
                    args_str = match.group(2)
                    args = {}
                    arg_pattern = re.compile(r'(\w+)="([^"]+)"')
                    for arg_match in arg_pattern.finditer(args_str):
                        args[arg_match.group(1)] = arg_match.group(2)
                    
                    response.tool_calls = [{'name': name, 'args': args, 'id': str(uuid.uuid4())}]
                    logger.info(f"Parsed tool call from XML: {name}")
                    break

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
