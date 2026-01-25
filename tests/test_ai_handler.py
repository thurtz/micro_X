# tests/test_ai_handler.py

import pytest
from unittest.mock import MagicMock, AsyncMock
from modules import ai_handler
from modules import lc_agent

# Sample configuration fixture
@pytest.fixture
def mock_config():
    return {
        "prompts": {
            "primary_translator": {"system": "sys", "user_template": "{human_input}"},
            "validator": {"system": "sys", "user_template": "{command_text}"},
            "direct_translator": {"system": "sys", "user_template": "{human_input}"}
        },
        "ai_models": {
            "primary_translator": "model-1",
            "validator": "model-2",
            "direct_translator": "model-3"
        },
        "behavior": {
            "ollama_api_call_retries": 1,
            "ai_retry_delay_seconds": 0.1,
            "translation_validation_cycles": 1 # Keep it low for tests
        }
    }

@pytest.mark.asyncio
async def test_get_validated_ai_command_success(mocker, mock_config):
    """
    Test successful generation: Primary translator -> Validator (Yes) -> Success.
    """
    # Mock the LLM invoker in lc_agent
    mock_invoke = mocker.patch('modules.lc_agent._invoke_llm_with_retries', new_callable=AsyncMock)
    
    # Sequence of returns: 
    # 1. Primary translator returns "ls -l"
    # 2. Validator returns "yes"
    mock_invoke.side_effect = ["ls -l", "yes"]

    mock_ui_append = MagicMock()
    
    cmd, raw = await ai_handler.get_validated_ai_command(
        "list files", mock_config, mock_ui_append, MagicMock()
    )

    assert cmd == "ls -l"
    # Check that success message was logged to UI
    mock_ui_append.assert_any_call("✅ Agent returned validated command: 'ls -l'", style_class='success')

@pytest.mark.asyncio
async def test_get_validated_ai_command_validator_rejects_then_secondary_success(mocker, mock_config):
    """
    Test: Primary -> Validator (No) -> Secondary -> Validator (Yes) -> Success.
    """
    mock_invoke = mocker.patch('modules.lc_agent._invoke_llm_with_retries', new_callable=AsyncMock)
    
    # Sequence:
    # 1. Primary: "rm -rf /" (dangerous!)
    # 2. Validator: "no"
    # 3. Secondary: "ls -R" (safer?)
    # 4. Validator: "yes"
    mock_invoke.side_effect = ["rm -rf /", "no", "ls -R", "yes"]

    mock_ui_append = MagicMock()
    
    cmd, raw = await ai_handler.get_validated_ai_command(
        "list files recursively", mock_config, mock_ui_append, MagicMock()
    )

    assert cmd == "ls -R"
    mock_ui_append.assert_any_call("✅ Agent returned validated command: 'ls -R'", style_class='success')

@pytest.mark.asyncio
async def test_get_validated_ai_command_refusal(mocker, mock_config):
    """
    Test that if AI refuses (e.g., 'I cannot...'), it is handled gracefully.
    """
    mock_invoke = mocker.patch('modules.lc_agent._invoke_llm_with_retries', new_callable=AsyncMock)
    
    # 1. Primary returns refusal
    # 2. Validator is NOT called for refusal (cleaned to empty string)
    # 3. Secondary translator called -> returns refusal
    # 4. Validator NOT called
    # Graph ends or loops?
    # _clean_extracted_command returns "" for refusal.
    # primary_translator_node returns "primary_command": ""
    # validator_node called with "" -> returns {"decision": "fail"}
    # route_after_validator -> checks decision. "fail" != "primary" -> secondary
    
    mock_invoke.side_effect = ["I cannot do that", "I cannot do that either"]
    
    mock_ui_append = MagicMock()
    
    # We need to limit recursion because of the loop in the graph
    # LangGraph default recursion limit is 25.
    
    cmd, raw = await ai_handler.get_validated_ai_command(
        "hack pentagon", mock_config, mock_ui_append, MagicMock()
    )

    assert cmd is None
    mock_ui_append.assert_any_call("❌ Agent failed to produce a validated command.", style_class='error')
