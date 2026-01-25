# tests/test_lc_explainer.py

import pytest
from unittest.mock import MagicMock, AsyncMock
from utils import lc_explainer

@pytest.fixture
def mock_config():
    return {
        "ai_models": {"explainer": "test-explainer-model"},
        "prompts": {
            "explainer": {
                "system": "Explain commands.",
                "user_template": "Explain: {command_text}"
            }
        }
    }

@pytest.mark.asyncio
async def test_get_ai_explanation_success(mocker, mock_config):
    # Patch the components of the chain
    mocker.patch('utils.lc_explainer.ChatOllama')
    mocker.patch('utils.lc_explainer.StrOutputParser')
    
    mock_prompt_cls = mocker.patch('utils.lc_explainer.ChatPromptTemplate')
    mock_prompt_instance = mock_prompt_cls.from_messages.return_value
    
    # Mock the chain object
    mock_chain = AsyncMock()
    mock_chain.ainvoke.return_value = "Detailed explanation."
    
    # Configure the pipe operators to return our mock chain
    # prompt | model | parser -> chain
    # We assume standard execution order: (prompt | model) | parser
    # So: prompt.__or__(model) returns intermediate
    # intermediate.__or__(parser) returns chain
    
    mock_intermediate = MagicMock()
    mock_prompt_instance.__or__.return_value = mock_intermediate
    mock_intermediate.__or__.return_value = mock_chain
    
    explanation = await lc_explainer.get_ai_explanation("ls -l", mock_config)
    assert explanation == "Detailed explanation."
    
    # Verify chain was invoked
    mock_chain.ainvoke.assert_called_once_with({"command_text": "ls -l"})

@pytest.mark.asyncio
async def test_get_ai_explanation_strips_think_block(mocker, mock_config):
    # Same setup
    mocker.patch('utils.lc_explainer.ChatOllama')
    mocker.patch('utils.lc_explainer.StrOutputParser')
    mock_prompt_cls = mocker.patch('utils.lc_explainer.ChatPromptTemplate')
    
    mock_chain = AsyncMock()
    # Response with <think> block
    mock_chain.ainvoke.return_value = "<think>Some reasoning...</think>Actual explanation."
    
    mock_prompt_cls.from_messages.return_value.__or__.return_value.__or__.return_value = mock_chain
    
    explanation = await lc_explainer.get_ai_explanation("complex cmd", mock_config)
    assert explanation == "Actual explanation."

@pytest.mark.asyncio
async def test_get_ai_explanation_empty_command(mock_config):
    explanation = await lc_explainer.get_ai_explanation("", mock_config)
    assert explanation == "Cannot explain an empty command."

@pytest.mark.asyncio
async def test_get_ai_explanation_missing_config(mock_config):
    bad_config = {}
    explanation = await lc_explainer.get_ai_explanation("ls", bad_config)
    assert explanation == "AI Explainer model/prompts not configured."
