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
async def test_prompt_for_command_confirmation_cancel(textual_ui_manager):
    textual_ui_manager.app.show_confirmation_modal = AsyncMock(return_value='cancel')
    result = await textual_ui_manager.prompt_for_command_confirmation("ls", "list files")
    assert result == {'action': 'cancel'}

@pytest.mark.asyncio
async def test_prompt_for_command_confirmation_explain(textual_ui_manager, mocker):
    # This one is tricky because it loops. We need to mock show_confirmation_modal 
    # to return 'explain' once, then 'execute'.
    textual_ui_manager.app.show_confirmation_modal = AsyncMock(side_effect=['explain', 'execute'])
    
    # Mock AI explanation
    mock_explain = mocker.patch("modules.ai_handler.explain_linux_command_with_ai", new_callable=AsyncMock)
    mock_explain.return_value = "This is an explanation."
    
    result = await textual_ui_manager.prompt_for_command_confirmation("ls", "list files")
    
    assert result == {'action': 'execute', 'command': 'ls'}
    assert mock_explain.called
    assert ("info", "💡 Explanation:\nThis is an explanation.") in textual_ui_manager.output_buffer

@pytest.mark.asyncio
async def test_prompt_for_command_confirmation_modify(textual_ui_manager):
    textual_ui_manager.app.show_confirmation_modal = AsyncMock(return_value='modify')
    # Mock input_widget for Textual
    textual_ui_manager.app.input_widget = MagicMock()
    
    result = await textual_ui_manager.prompt_for_command_confirmation("ls", "list files")
    
    assert result == {'action': 'edit_mode_engaged'}
    assert textual_ui_manager.is_in_edit_mode is True
    # Verify command was loaded into input widget
    textual_ui_manager.app.call_later.assert_any_call(setattr, textual_ui_manager.app.input_widget, 'text', 'ls')

@pytest.mark.asyncio
async def test_start_categorization_flow_execute_once(textual_ui_manager):
    textual_ui_manager.app.show_categorization_modal = AsyncMock(return_value='execute')
    result = await textual_ui_manager.start_categorization_flow("ls")
    assert result == {'action': 'execute_once', 'command': 'ls'}

@pytest.mark.asyncio
async def test_start_categorization_flow_cancel(textual_ui_manager):
    textual_ui_manager.app.show_categorization_modal = AsyncMock(return_value='cancel')
    result = await textual_ui_manager.start_categorization_flow("ls")
    assert result == {'action': 'cancel_execution'}

@pytest.mark.asyncio
async def test_prompt_for_api_input(textual_ui_manager):
    # Currently it's a mock returning ""
    res = await textual_ui_manager.prompt_for_api_input("prompt")
    assert res == ""

def test_add_interaction_separator(textual_ui_manager):
    textual_ui_manager.add_interaction_separator()
    assert textual_ui_manager.last_output_was_separator is True
    # Check if separator string was added to buffer
    assert any("─" in item[1] for item in textual_ui_manager.output_buffer)

def test_update_status_bar(textual_ui_manager):
    textual_ui_manager.update_status_bar("Thinking...")
    textual_ui_manager.app.call_later.assert_called_once_with(textual_ui_manager.app.show_status, "Thinking...")
    
    textual_ui_manager.app.call_later.reset_mock()
    textual_ui_manager.update_status_bar("")
    textual_ui_manager.app.call_later.assert_called_once_with(textual_ui_manager.app.clear_status)

def test_update_status_bar_no_app(mock_config):
    manager = TextualUIManager(mock_config)
    manager.app = None
    # Should not crash
    manager.update_status_bar("test")

