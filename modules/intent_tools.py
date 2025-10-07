# modules/intent_tools.py

from langchain.tools import tool
from typing import Literal

# This file defines the tools that the Router Agent can use.
# Each tool corresponds to a high-level capability of the micro_X shell.
# The docstrings are crucial as they are used by the LLM to decide which tool to use.

@tool
def run_tests(branch: Literal["main", "testing", "dev", "all"] = "dev") -> str:
    """Runs the test suite on a specified branch. Defaults to the 'dev' branch if not specified."""
    if branch == "all":
        return "/utils dev --run-tests-all"
    return f"/utils dev --run-tests-{branch}"

@tool
def generate_snapshot(
    branch: Literal["main", "testing", "dev", "all"] = "dev",
    summary: str = None,
    include_logs: bool = False,
    summarize_modules: bool = False
) -> str:
    """
    Creates a snapshot of a specified project branch. Defaults to the 'dev' branch.
    Use the 'summary' parameter to add a message.
    Only set 'include_logs' to True if the user explicitly asks for logs.
    Only set 'summarize_modules' to True if the user explicitly asks to summarize, shorten, or reduce the size of the snapshot.
    If 'branch' is 'all', snapshots are generated for main, testing, and dev branches.
    The 'snapshot' command is an alias for 'generate_snapshot'.
    """
    # Determine the base command based on whether it's a multi-branch dev command or a single project snapshot
    if branch in ["main", "testing", "dev", "all"]:
        # The 'dev' utility handles the multi-branch logic
        base_command = f"/dev --snapshot-{branch}"
    else:
        # Fallback or direct snapshot for the current project context
        base_command = "/snapshot"

    args = []
    if summary:
        # Use quotes to handle summaries with spaces
        args.append(f'--summary "{summary}"')
    if include_logs:
        args.append("--include-logs")
    if summarize_modules:
        args.append("--summarize")

    # Join the arguments with spaces
    if args:
        return f"{base_command} {' '.join(args)}"
    return base_command

@tool
def list_scripts(script_type: Literal["all", "user", "utils"] = "all") -> str:
    """Lists available scripts. Can filter by 'user' or 'utils' scripts."""
    if script_type == "all":
        return "/list"
    return f"/list --type {script_type}s" # e.g., --type users, --type utils

@tool
def show_help(topic: str = "") -> str:
    """Shows help for a specific topic or the general help message."""
    if topic:
        return f"/help {topic}"
    return "/help"

@tool
def update_system() -> str:
    """Checks for and applies updates to the micro_X system."""
    return "/utils update"

@tool
def get_git_branch() -> str:
    """Gets the current active Git branch name."""
    return "/utils git_branch"


@tool
def add_command_to_category(command_name: str, category: str) -> str:
    """Adds a new command to a specified category for the command categorization system."""
    # Note: The command utility uses positional arguments for --add
    return f'/utils command --add "{command_name}" {category}'


@tool
def remove_command_from_category(command_name: str) -> str:
    """Removes a command from the command categorization system."""
    return f'/utils command --remove "{command_name}"'


@tool
def move_command_to_category(command_name: str, new_category: str) -> str:
    """Moves a command to a new category in the command categorization system."""
    return f'/utils command --move "{command_name}" {new_category}'


@tool
def add_alias(alias_name: str, command: str) -> str:
    """Creates a new user-specific command alias."""
    return f'/utils alias --add {alias_name} "{command}"'


@tool
def remove_alias(alias_name: str) -> str:
    """Removes a user-specific command alias."""
    return f'/utils alias --remove {alias_name}'


@tool
def query_knowledge_base(query: str, kb_name: str = "default") -> str:
    """
    Searches a specified knowledge base to answer a user's question. Use this for any query that asks to 'search', 'find', 'look up', 'what is', or 'how does' something.
    If the user's query mentions a specific knowledge base, provide its name using the 'kb_name' parameter.
    """
    return f'/knowledge --name {kb_name} query "{query}"'


@tool
def add_file_to_knowledge_base(path: str, kb_name: str = "default") -> str:
    """
    Adds, ingests, or stores a local file in a specified knowledge base. Use this when the user asks to 'add a file', 'index this document', or 'learn from this file'.
    If a knowledge base name is mentioned, provide it as 'kb_name'.
    """
    return f'/knowledge --name {kb_name} add-file {path}'


@tool
def add_directory_to_knowledge_base(path: str, kb_name: str = "default") -> str:
    """
    Adds, ingests, or stores all files from a local directory into a specified knowledge base. Use this when the user asks to 'add a directory', 'index this folder', or 'learn from these documents'.
    If a knowledge base name is mentioned, provide it as 'kb_name'.
    """
    return f'/knowledge --name {kb_name} add-dir {path}'


@tool
def add_url_to_knowledge_base(url: str, kb_name: str = "default", recursive: bool = False, depth: int = 1, save_cache: bool = False) -> str:
    """
    Adds, ingests, or stores content from a URL in a specified knowledge base. Use this when the user asks to 'add a url', 'learn from this website', or 'crawl a page'.
    If a knowledge base name is mentioned, provide it as 'kb_name'.
    Set 'recursive' to True or specify a 'depth' greater than 1 to crawl the website.
    Set 'save_cache' to True to keep a local copy of the downloaded pages.
    """
    command = f'/knowledge --name {kb_name} add-url {url}'
    # A depth > 1 implies recursion.
    if recursive or depth > 1:
        command += f' --recursive --depth {depth}'
    if save_cache:
        command += ' --save-cache'
    return command


def get_all_tools():
    """Returns a list of all defined intent tools."""
    return [
        run_tests,
        generate_snapshot,
        list_scripts,
        show_help,
        update_system,
        get_git_branch,
        add_command_to_category,
        remove_command_from_category,
        move_command_to_category,
        add_alias,
        remove_alias,
        query_knowledge_base,
        add_file_to_knowledge_base,
        add_directory_to_knowledge_base,
        add_url_to_knowledge_base,
    ]
