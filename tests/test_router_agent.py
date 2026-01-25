# tests/test_router_agent.py

import pytest
from unittest.mock import MagicMock, AsyncMock
from modules import router_agent

@pytest.fixture
def mock_config():
    return {
        "ai_models": {
            "router": "test-router-model"
        }
    }

def test_create_router_agent_success(mocker, mock_config):
    # Mock ChatOllama and create_tool_calling_agent
    mocker.patch('modules.router_agent.ChatOllama')
    mocker.patch('modules.router_agent.create_tool_calling_agent')
    mocker.patch('modules.router_agent.AgentExecutor')
    
    agent = router_agent.create_router_agent(mock_config)
    assert agent is not None

def test_create_router_agent_missing_model(mock_config):
    bad_config = {"ai_models": {}}
    agent = router_agent.create_router_agent(bad_config)
    assert agent is None

@pytest.mark.asyncio
async def test_run_router_agent_success(mocker):
    mock_agent_executor = AsyncMock()
    
    # Simulate a successful tool call result structure from AgentExecutor
    # return_intermediate_steps=True means result contains "intermediate_steps"
    # intermediate_steps is a list of (AgentAction, output) tuples
    mock_tool_output = "/help"
    mock_result = {
        "output": "I will show the help menu.",
        "intermediate_steps": [
            (MagicMock(), mock_tool_output)
        ]
    }
    mock_agent_executor.ainvoke.return_value = mock_result
    
    command = await router_agent.run_router_agent(mock_agent_executor, "help me")
    
    assert command == "/help"
    mock_agent_executor.ainvoke.assert_called_once_with({"input": "help me"})

@pytest.mark.asyncio
async def test_run_router_agent_no_tool_used(mocker):
    mock_agent_executor = AsyncMock()
    
    # Simulate response where no tool was called
    mock_result = {
        "output": "I am sorry, but I cannot answer that question.",
        "intermediate_steps": []
    }
    mock_agent_executor.ainvoke.return_value = mock_result
    
    command = await router_agent.run_router_agent(mock_agent_executor, "unknown request")
    
    assert command is None

@pytest.mark.asyncio
async def test_run_router_agent_exception(mocker):
    mock_agent_executor = AsyncMock()
    mock_agent_executor.ainvoke.side_effect = Exception("Agent failed")
    
    command = await router_agent.run_router_agent(mock_agent_executor, "crash")
    
    assert command is None
