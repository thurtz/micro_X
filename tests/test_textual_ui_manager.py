# tests/test_textual_ui_manager.py

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from modules.textual_ui_manager import TextualUIManager

@pytest.fixture
def mock_config():
    return {"ui": {"max_prompt_length": 20}}

@pytest.fixture
def textual_ui_manager(mock_config):
    manager = TextualUIManager(mock_config)
    manager.app = MagicMock()
    return manager

def test_append_output_with_app(textual_ui_manager):
    textual_ui_manager.append_output("Hello", "info")
    textual_ui_manager.app.call_later.assert_called_once_with(
        textual_ui_manager.app.append_output, "Hello", "info"
    )
    assert ("info", "Hello") in textual_ui_manager.output_buffer

def test_append_output_no_app(mock_config):
    manager = TextualUIManager(mock_config)
    with patch('builtins.print') as mock_print:
        manager.append_output("Hello", "info")
        mock_print.assert_called_once_with("Hello")
    assert ("info", "Hello") in manager.output_buffer

def test_update_input_prompt(textual_ui_manager):
    textual_ui_manager.update_input_prompt("/home/user")
    # Verify call_later was used to schedule the attribute set
    assert textual_ui_manager.app.call_later.called

@pytest.mark.asyncio
async def test_prompt_for_command_confirmation_execute(textual_ui_manager):
    # Mock show_confirmation_modal to return 'execute'
    textual_ui_manager.app.show_confirmation_modal = AsyncMock(return_value='execute')
    
    result = await textual_ui_manager.prompt_for_command_confirmation("ls", "list files")
    
    assert result == {'action': 'execute', 'command': 'ls'}
    textual_ui_manager.app.show_confirmation_modal.assert_called_once_with("ls", "list files", None)

@pytest.mark.asyncio
async def test_prompt_for_command_confirmation_categorize(textual_ui_manager):
    textual_ui_manager.app.show_confirmation_modal = AsyncMock(return_value='execute_simple')
    
    result = await textual_ui_manager.prompt_for_command_confirmation("ls", "list files")
    
    assert result == {'action': 'execute_and_categorize', 'category': 'simple', 'command': 'ls'}

@pytest.mark.asyncio
async def test_start_categorization_flow_simple(textual_ui_manager):
    textual_ui_manager.app.show_categorization_modal = AsyncMock(return_value='simple')
    
    result = await textual_ui_manager.start_categorization_flow("ls")
    
    assert result == {'action': 'categorize_and_execute', 'category': 'simple', 'command': 'ls', 'save': True}

@pytest.mark.asyncio
async def test_prompt_for_caution_confirmation_proceed(textual_ui_manager):
    textual_ui_manager.app.show_safety_modal = AsyncMock(return_value=True)
    
    result = await textual_ui_manager.prompt_for_caution_confirmation("rm -rf /")
    
    assert result == {'proceed': True}
    textual_ui_manager.app.show_safety_modal.assert_called_once_with("rm -rf /", "Potentially Dangerous Command")

def test_update_status_bar(textual_ui_manager):
    textual_ui_manager.update_status_bar("Thinking...")
    textual_ui_manager.app.call_later.assert_called_once_with(textual_ui_manager.app.show_status, "Thinking...")
    
    textual_ui_manager.app.call_later.reset_mock()
    textual_ui_manager.update_status_bar("")
    textual_ui_manager.app.call_later.assert_called_once_with(textual_ui_manager.app.clear_status)
