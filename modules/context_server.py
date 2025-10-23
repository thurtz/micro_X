# modules/context_server.py

import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from typing import List, Dict, Any
import logging

# --- Logging Setup ---
logger = logging.getLogger(__name__)

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "default": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# --- Data Models ---
class ShellContext(BaseModel):
    """Defines the structure of the shell's context."""
    current_directory: str = "/"
    command_history: List[str] = []
    git_status: Dict[str, Any] = {}
    config: Dict[str, Any] = {}

# --- Globals ---
app = FastAPI()
context = ShellContext()

# --- API Endpoints ---
@app.get("/")
def read_root():
    """Root endpoint for the MCP server."""
    return {"message": "micro_X Model Context Protocol Server"}

@app.get("/context", response_model=ShellContext)
async def get_context():
    """Returns the current shell context."""
    return context

@app.post("/context/directory")
async def update_directory(directory_update: dict):
    """Updates the current directory in the context."""
    global context
    new_directory = directory_update.get("directory")
    if new_directory:
        context.current_directory = new_directory
        return {"status": "success", "new_directory": new_directory}
    return {"status": "error", "message": "Directory not provided"}

@app.post("/context/history")
async def add_history(command_update: dict):
    """Adds a command to the history."""
    global context
    command = command_update.get("command")
    if command:
        context.command_history.append(command)
        return {"status": "success"}
    return {"status": "error", "message": "Command not provided"}

@app.post("/context/git_status")
async def update_git_status(status_update: dict):
    """Updates the git status in the context."""
    global context
    status = status_update.get("status")
    if status:
        context.git_status = status
        return {"status": "success"}
    return {"status": "error", "message": "Status not provided"}

@app.post("/context/config")
async def update_config(config_update: dict):
    """Updates the config in the context."""
    global context
    config = config_update.get("config")
    if config:
        context.config = config
        return {"status": "success"}
    return {"status": "error", "message": "Config not provided"}

@app.post("/context/save")
async def save_context():
    """Saves the current context to a file."""
    try:
        with open("micro_x_context.json", "w") as f:
            f.write(context.model_dump_json())
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/context/load")
async def load_context():
    """Loads the context from a file."""
    global context
    try:
        with open("micro_x_context.json", "r") as f:
            data = json.load(f)
            context = ShellContext(**data)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# --- Server Control ---
class MCPServer:
    """A wrapper for the Uvicorn server to run it in an asyncio task."""
    def __init__(self, host="127.0.0.1", port=8123):
        self.config = uvicorn.Config(app, host=host, port=port, log_config=LOG_CONFIG)
        self.server = uvicorn.Server(self.config)
        self._task = None

    async def start(self):
        """Starts the Uvicorn server in the background."""
        if self.is_running():
            print("Server is already running.")
            return
        # The 'serve' method is a coroutine, so we can run it as a task.
        self._task = asyncio.create_task(self.server.serve())

    async def stop(self):
        """Stops the Uvicorn server."""
        if self.is_running() and self._task:
            self.server.should_exit = True
            await self._task
            self._task = None

    def is_running(self) -> bool:
        """Checks if the server task is running."""
        return self._task is not None and not self._task.done()

# This allows running the server standalone for testing if needed
if __name__ == "__main__":
    server = MCPServer()
    async def main():
        await server.start()
        # Keep the server running for a while for testing
        try:
            await asyncio.sleep(3600)
        finally:
            await server.stop()

    asyncio.run(main())
