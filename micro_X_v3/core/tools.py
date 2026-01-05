# micro_X_v3/core/tools.py

import logging
from typing import Annotated
from langchain_core.tools import tool

from ..modules.rag_service import RagService
from ..modules.utility_service import UtilityService
# We don't import ShellService here directly because Shell Execution is special (needs human review)
# Instead, we define a "Proposal Tool" that outputs the command for review.

logger = logging.getLogger(__name__)

# We need a way to access the services instance from within the tool.
# Usually we bind tools with partials or context, but for simplicity here we might use a registry or pass context in state.
# LangGraph state access inside tools is tricky.
# Better pattern: The TOOL returns a structured object, and the NODE executes it.

# Actually, LangChain Tools are meant to be executed.
# Let's define them as wrappers that return strings for the Agent to process.

@tool
def search_documentation(
    query: Annotated[str, "The user's question about micro_X features, usage, or configuration."]
):
    """
    Search the micro_X project documentation to answer questions about how to use the shell.
    Use this for questions like 'how do I use snapshot?', 'what is micro_X?', or 'help me configure aliases'.
    """
    # This function will be replaced/bound at runtime with the actual service call
    return "Searching docs..."

@tool
def propose_shell_command(
    query: Annotated[str, "The user's original request or description of the action (e.g. 'list files', 'what is current dir')."]
):
    """
    Delegate the request to the specialized Shell Translator AI.
    Use this for ANY request that can be answered or performed by running a Linux command.
    Examples: 'what is the current directory' (pwd), 'show ip' (ip addr), 'list files' (ls), 'check disk space' (df).
    The Translator will generate the actual Linux command syntax.
    """
    return f"TRANSLATE_REQUEST: {query}"

@tool
def run_internal_utility(
    utility_name: Annotated[str, "The name of the utility (e.g., 'snapshot', 'tree', 'dev')."],
    arguments: Annotated[str, "Optional arguments for the utility."] = ""
):
    """
    Run an internal micro_X utility script.
    Available utilities: snapshot, tree, dev, update, list, logs, setup_brew, test.
    """
    return f"RUN_UTILITY: {utility_name} {arguments}"
