# Model Context Protocol (MCP) Server Integration Strategy

This document outlines the strategy and phased implementation plan for integrating a Model Context Protocol (MCP) server into the `micro_X` shell.

## 1. Introduction

The MCP server will act as a central nervous system for `micro_X`. It will manage and provide the application's state and context (e.g., current directory, command history, Git status) through a standardized API. This architectural upgrade will decouple components, enhance AI capabilities, and allow for powerful integrations with external tools.

Our implementation will adhere to the standards set by **Anthropic's Model Context Protocol (MCP)** to ensure future compatibility with a broader ecosystem of developer tools.

## 2. Technical Stack

- **Web Framework:** `FastAPI` will be used for its high performance, asynchronous capabilities, and automatic API documentation.
- **ASGI Server:** `uvicorn` will be used to run the FastAPI application within `micro_X`'s `asyncio` event loop.

## 3. Phased Implementation Plan

The integration will be performed in four distinct phases to ensure stability and iterative progress.

### Phase 1: Foundational Setup - The Server Core

**Goal:** Establish a basic, functioning MCP server within `micro_X` and migrate a single piece of context (the current directory) to be managed by it as a proof-of-concept.

- **Steps:**
    1.  Add `fastapi` and `uvicorn` to `requirements.txt`.
    2.  Create a new `modules/context_server.py` module to house the FastAPI application.
    3.  Integrate the server into the `main.py` startup sequence, running it as a background `asyncio` task.
    4.  Implement a `/context/directory` endpoint on the server.
    5.  Refactor the `ShellEngine`'s `cd` command to `POST` the new directory to the server.
    6.  Refactor the `UIManager` to `GET` the current directory from the server when updating the prompt.

### Phase 2: Migrating Core Context - The Shell as Producer

**Goal:** Transition all of the shell's session state from the `ShellEngine` to the MCP server, making the server the single source of truth.

- **Steps:**
    1.  Expand the server's API with endpoints for command history, Git status, etc.
    2.  Refactor `ShellEngine` to `POST` all significant events (command execution, AI translation) and their associated data to the MCP server.
    3.  Remove internal state variables from `ShellEngine`, making it a more stateless orchestrator.

### Phase 3: Refactoring the AI - The AI as Consumer

**Goal:** Fully decouple the AI components from the `ShellEngine` by making them clients of the MCP server.

- **Steps:**
    1.  Refactor `AIHandler` to fetch all necessary context (history, directory, etc.) via a `GET` request to the MCP server's API.
    2.  Refactor the `RouterAgent` and `EmbeddingManager` to similarly query the server for the context they need for classification and routing.

### Phase 4: External Integration & Advanced Features

**Goal:** Leverage the new architecture to enable advanced capabilities and external tooling.

- **Steps:**
    1.  Publish the auto-generated API documentation for developers.
    2.  Implement state persistence with `/context/save` and `/context/load` endpoints to allow for session resumption.
    3.  Explore building proof-of-concept external tools (e.g., a VS Code extension) that can communicate with `micro_X` via the MCP server API.
