# tests/test_lc_agent.py

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from modules import lc_agent
from langchain_core.messages import HumanMessage

@pytest.fixture
def mock_config():
    return {
        "ai_models": {
            "primary_translator": "model-1",
            "validator": "model-2",
            "direct_translator": "model-3"
        },
        "prompts": {
            "primary_translator": {"system": "sys", "user_template": "{human_input}"},
            "validator": {"system": "sys", "user_template": "{command_text}"},
            "direct_translator": {"system": "sys", "user_template": "{human_input}"}
        },
        "behavior": {
            "ollama_api_call_retries": 1,
            "ai_retry_delay_seconds": 0.1
        }
    }

@pytest.mark.asyncio
async def test_primary_translator_node(mocker, mock_config):
    mock_invoke = mocker.patch("modules.lc_agent._invoke_llm_with_retries", new_callable=AsyncMock)
    mock_invoke.return_value = "ls -l"
    
    state = {
        "human_query": "list files",
        "config_param": mock_config,
        "messages": []
    }
    
    result = await lc_agent.primary_translator_node(state)
    
    assert result["primary_command"] == "ls -l"
    assert result["raw_response"] == "ls -l"
    assert len(result["messages"]) == 1
    assert "Primary translator output" in result["messages"][0].content

@pytest.mark.asyncio
async def test_validator_node_approve(mocker, mock_config):
    mock_invoke = mocker.patch("modules.lc_agent._invoke_llm_with_retries", new_callable=AsyncMock)
    mock_invoke.return_value = "yes"
    
    state = {
        "primary_command": "ls -l",
        "config_param": mock_config,
        "messages": []
    }
    
    result = await lc_agent.validator_node(state)
    
    assert result["decision"] == "primary"
    assert result["validated_command"] == "ls -l"
    assert "Validator approved" in result["messages"][0].content

@pytest.mark.asyncio
async def test_validator_node_reject(mocker, mock_config):
    mock_invoke = mocker.patch("modules.lc_agent._invoke_llm_with_retries", new_callable=AsyncMock)
    mock_invoke.return_value = "no"
    
    state = {
        "primary_command": "rm -rf /",
        "config_param": mock_config,
        "messages": []
    }
    
    result = await lc_agent.validator_node(state)
    
    assert result["decision"] is None
    assert "Validator rejected" in result["messages"][0].content

def test_route_after_primary():
    state = {"primary_command": "ls"}
    assert lc_agent.route_after_primary(state) == "validator"
    
    state = {"primary_command": ""}
    assert lc_agent.route_after_primary(state) == "secondary_translator"

def test_route_after_validator():
    state = {"decision": "primary"}
    assert lc_agent.route_after_validator(state) == "__end__"
    
    state = {"decision": None}
    assert lc_agent.route_after_validator(state) == "secondary_translator"

def test_route_after_secondary():
    state = {"primary_command": "ls"}
    assert lc_agent.route_after_secondary(state) == "validator"
    
    state = {"primary_command": None}
    assert lc_agent.route_after_secondary(state) == "__end__"

def test_is_ai_refusal():
    assert lc_agent._is_ai_refusal("Sorry, I cannot do that") is True
    assert lc_agent._is_ai_refusal("ls -l") is False

def test_clean_extracted_command():
    assert lc_agent._clean_extracted_command(" `ls -l` ") == "ls -l"
    assert lc_agent._clean_extracted_command(" 'pwd' ") == "pwd"
    assert lc_agent._clean_extracted_command("Sorry, I cannot") == ""
