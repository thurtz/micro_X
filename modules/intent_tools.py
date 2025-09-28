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
def generate_snapshot(branch: Literal["main", "testing", "dev", "all"] = "dev", include_logs: bool = False, summarize: bool = False) -> str:
    """Creates a snapshot of a specified project branch. Defaults to the 'dev' branch.
    Can optionally include logs or summarize the snapshot."""
    command = f"/utils dev --snapshot-{branch}"
    if include_logs:
        command += " --include-logs"
    if summarize:
        command += " --summarize"
    return command

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
        return f"/utils help {topic}"
    return "/utils help"

@tool
def update_system() -> str:
    """Checks for and applies updates to the micro_X system."""
    return "/utils update"

@tool
def get_git_branch() -> str:
    """Gets the current active Git branch name."""
    return "/utils git_branch"


# We can add more tools here over time, covering more intents.

def get_all_tools():
    """Returns a list of all defined intent tools."""
    return [
        run_tests,
        generate_snapshot,
        list_scripts,
        show_help,
        update_system,
        get_git_branch,
    ]
