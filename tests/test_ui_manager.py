# tests/test_ui_manager.py

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import os 

from prompt_toolkit.document import Document 

from modules.ui_manager import UIManager
from modules.category_manager import CATEGORY_MAP, CATEGORY_DESCRIPTIONS 

# --- Helper Function (Moved to Module Level) ---

async def simulate_input_sequence(ui_manager, inputs): # Changed from method to function
    """
    Helper to simulate a sequence of user inputs for a flow.
    'ui_manager' is the UIManager instance.
    'inputs' is a list of tuples: (expected_handler_method_name_str, user_response_text)
    """
    for i, (expected_handler_name, response_text) in enumerate(inputs):
        current_handler_func = None
        # Wait for the UIManager to set the correct accept_handler
        for attempt in range(50): # Max ~0.5s wait
            handler_on_mock_buffer = ui_manager.input_field.buffer.accept_handler
            if callable(handler_on_mock_buffer) and hasattr(handler_on_mock_buffer, '__name__') and handler_on_mock_buffer.__name__ == expected_handler_name:
                current_handler_func = handler_on_mock_buffer
                break
            await asyncio.sleep(0.01) 
        
        assert current_handler_func is not None, \
            f"Timeout or incorrect handler at step {i}. Expected: '{expected_handler_name}', Got: '{getattr(ui_manager.input_field.buffer.accept_handler, '__name__', ui_manager.input_field.buffer.accept_handler)}'"
        
        mock_b = MagicMock()
        mock_b.text = response_text
        current_handler_func(mock_b) 
        await asyncio.sleep(0.02) # Allow handler to process and potentially set next state/handler


# --- Fixtures ---

@pytest.fixture
def mock_config():
    """Provides a mock configuration dictionary for UIManager tests."""
    return {
        "behavior": {
            "input_field_height": 3,
            "default_category_for_unclassified": "simple",
        },
        "ui": {"max_prompt_length": 20},
        "prompts": { 
            "explainer": {"system": "Explainer system prompt", "user_template": "Explain: {command_text}"}
        },
        "ai_models": { 
            "explainer": "mock_explainer_model" # Ensure this is present for explain tests
        }
    }

@pytest.fixture
def ui_manager_instance(mock_config):
    """
    Provides an instance of UIManager with mocked external dependencies.
    """
    manager = UIManager(mock_config)
    
    manager.append_output = MagicMock() 

    mock_app_instance = MagicMock()
    mock_app_instance.invalidate = MagicMock()
    mock_app_instance.is_running = True 
    manager.get_app_instance = MagicMock(return_value=mock_app_instance)
    manager.app = mock_app_instance 

    manager.main_restore_normal_input_ref = MagicMock()
    manager.main_exit_app_ref = MagicMock()
    
    buffer_mock = MagicMock(spec=['accept_handler', 'document', 'reset', 'text']) 
    buffer_mock.document = Document("")
    buffer_mock.accept_handler = None 
    buffer_mock.reset = MagicMock()
    manager.input_field = MagicMock()
    manager.input_field.buffer = buffer_mock 
    
    manager.input_field.multiline = False 

    manager.output_field = MagicMock() 
    manager.output_field.buffer = MagicMock()
    manager.output_field.buffer.document = Document("")

    manager.layout = MagicMock()
    if manager.output_field: 
      manager.output_field.window = MagicMock()
      manager.output_field.window.render_info = MagicMock()

    return manager

@pytest.fixture
def mock_buffer_input(): 
    """Creates a mock buffer object to simulate user input text for accept_handlers."""
    buffer = MagicMock()
    buffer.text = "" 
    buffer.document = Document("") 
    return buffer

# --- Test Classes ---

class TestUIManagerInitialization:
    def test_initialization_values(self, ui_manager_instance, mock_config):
        assert ui_manager_instance.config == mock_config
        assert not ui_manager_instance.categorization_flow_active
        assert not ui_manager_instance.confirmation_flow_active
        assert not ui_manager_instance.is_in_edit_mode
        assert ui_manager_instance.kb is not None
        assert ui_manager_instance.auto_scroll is True
        assert ui_manager_instance.output_buffer == []
        assert ui_manager_instance.current_prompt_text == ""

class TestUIManagerModeSetting:
    def test_set_normal_input_mode(self, ui_manager_instance, mock_config):
        mock_accept_handler = MagicMock()
        mock_current_dir = "/test/dir" 
        
        ui_manager_instance.categorization_flow_active = True
        ui_manager_instance.confirmation_flow_active = True
        ui_manager_instance.is_in_edit_mode = True

        ui_manager_instance.set_normal_input_mode(mock_accept_handler, mock_current_dir)

        assert not ui_manager_instance.categorization_flow_active
        assert not ui_manager_instance.confirmation_flow_active
        assert not ui_manager_instance.is_in_edit_mode
        
        assert ui_manager_instance.input_field.buffer.accept_handler == mock_accept_handler
        expected_multiline = mock_config['behavior']['input_field_height'] > 1
        assert ui_manager_instance.input_field.multiline == expected_multiline
        ui_manager_instance.input_field.buffer.reset.assert_called_once()
        
        expected_dir_in_prompt = os.path.basename(mock_current_dir) 
        assert expected_dir_in_prompt in ui_manager_instance.current_prompt_text
        ui_manager_instance.get_app_instance().invalidate.assert_called()

    def test_set_flow_input_mode_categorization(self, ui_manager_instance):
        mock_accept_handler = MagicMock()
        prompt_text = "[Categorize] Test Prompt: "
        ui_manager_instance.set_flow_input_mode(prompt_text, mock_accept_handler, is_categorization=True)
        
        assert ui_manager_instance.categorization_flow_active
        assert not ui_manager_instance.confirmation_flow_active
        assert not ui_manager_instance.is_in_edit_mode
        assert ui_manager_instance.current_prompt_text == prompt_text
        assert ui_manager_instance.input_field.buffer.accept_handler == mock_accept_handler
        assert not ui_manager_instance.input_field.multiline
        ui_manager_instance.input_field.buffer.reset.assert_called_once()
        ui_manager_instance.get_app_instance().invalidate.assert_called()

    def test_set_flow_input_mode_confirmation(self, ui_manager_instance):
        mock_accept_handler = MagicMock()
        prompt_text = "[Confirm] Test Prompt: "
        ui_manager_instance.set_flow_input_mode(prompt_text, mock_accept_handler, is_confirmation=True)

        assert ui_manager_instance.confirmation_flow_active
        assert not ui_manager_instance.categorization_flow_active
        assert not ui_manager_instance.is_in_edit_mode
        assert ui_manager_instance.current_prompt_text == prompt_text
        assert ui_manager_instance.input_field.buffer.accept_handler == mock_accept_handler
        assert not ui_manager_instance.input_field.multiline
        ui_manager_instance.input_field.buffer.reset.assert_called_once()
        ui_manager_instance.get_app_instance().invalidate.assert_called()

    def test_set_edit_mode(self, ui_manager_instance, mock_config):
        mock_accept_handler = MagicMock()
        command_to_edit = "echo 'hello from edit mode'"
        ui_manager_instance.set_edit_mode(mock_accept_handler, command_to_edit)

        assert ui_manager_instance.is_in_edit_mode
        assert not ui_manager_instance.categorization_flow_active
        assert not ui_manager_instance.confirmation_flow_active
        assert ui_manager_instance.current_prompt_text == "[Edit Command]> "
        assert ui_manager_instance.input_field.buffer.accept_handler == mock_accept_handler
        expected_multiline = mock_config['behavior']['input_field_height'] > 1
        assert ui_manager_instance.input_field.multiline == expected_multiline
        
        assert ui_manager_instance.input_field.buffer.document.text == command_to_edit
        assert ui_manager_instance.input_field.buffer.document.cursor_position == len(command_to_edit)
        
        ui_manager_instance.get_app_instance().invalidate.assert_called()

class TestUICategorizationFlow:
    """Tests for the multi-step command categorization flow."""

    # Note: _simulate_input_sequence is now a module-level function

    @pytest.mark.asyncio 
    async def test_cat_flow_cancel_at_step0_5(self, ui_manager_instance, mock_buffer_input): 
        command_proposed = "ls -l"
        command_original = "list files"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_proposed, command_proposed, command_original)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [('_handle_step_0_5_response', '4')]
        )
        result = await flow_task
        assert result == {'action': 'cancel_execution'}
        assert not ui_manager_instance.categorization_flow_active

    @pytest.mark.asyncio 
    async def test_cat_flow_choose_processed_then_simple(self, ui_manager_instance, mock_buffer_input):
        command_proposed = "my_command --processed"
        command_original = "my command original"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_proposed, command_proposed, command_original)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_step_0_5_response', '1'), 
                ('_handle_step_1_main_action_response', '1') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'categorize_and_execute', 'command': command_proposed, 'category': 'simple'}
        assert not ui_manager_instance.categorization_flow_active

    @pytest.mark.asyncio 
    async def test_cat_flow_choose_original_then_interactive(self, ui_manager_instance, mock_buffer_input):
        command_proposed = "processed_htop"
        command_original = "htop --original"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_proposed, command_proposed, command_original)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_step_0_5_response', '2'), 
                ('_handle_step_1_main_action_response', '3') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'categorize_and_execute', 'command': command_original, 'category': 'interactive_tui'}

    @pytest.mark.asyncio 
    async def test_cat_flow_no_diff_then_semi_interactive(self, ui_manager_instance, mock_buffer_input):
        command_common = "common_command"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_common, command_common, command_common)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_step_1_main_action_response', '2') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'categorize_and_execute', 'command': command_common, 'category': 'semi_interactive'}

    @pytest.mark.asyncio 
    async def test_cat_flow_modify_enter_new_then_categorize(self, ui_manager_instance, mock_buffer_input):
        command_proposed = "initial_cmd"
        command_original = "original input"
        new_custom_command = "completely_new_command --option"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_proposed, command_proposed, command_original)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_step_0_5_response', '3'),             
                ('_handle_step_3_5_response', new_custom_command), 
                ('_handle_step_1_main_action_response', '1')  
            ]
        )
        result = await flow_task
        assert result == {'action': 'categorize_and_execute', 'command': new_custom_command, 'category': 'simple'}

    @pytest.mark.asyncio 
    async def test_cat_flow_main_action_modify_then_categorize(self, ui_manager_instance, mock_buffer_input):
        command_initial = "cmd_to_be_modified"
        modified_command = "cmd_is_now_modified --flag"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_initial, command_initial, command_initial)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_step_1_main_action_response', 'm'), 
                ('_handle_step_4_modified_command_response', modified_command), 
                ('_handle_step_4_5_response', '3') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'categorize_and_execute', 'command': modified_command, 'category': 'interactive_tui'}

    @pytest.mark.asyncio 
    async def test_cat_flow_execute_as_default(self, ui_manager_instance, mock_buffer_input):
        command_initial = "some_unknown_cmd"
        flow_task = asyncio.create_task(
            ui_manager_instance.start_categorization_flow(command_initial, command_initial, command_initial)
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_step_1_main_action_response', 'd') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'execute_as_default'}


class TestUIConfirmationFlow:
    """Tests for the multi-step AI command confirmation flow."""

    @pytest.mark.asyncio
    @patch('modules.ui_manager.explain_linux_command_with_ai', new_callable=AsyncMock) 
    async def test_conf_flow_explain_then_execute_yes(self, mock_explain_ai, ui_manager_instance, mock_buffer_input):
        mock_explain_ai.return_value = "This is a detailed explanation of the command."
        command_to_confirm = "ls -la /tmp"
        display_source = "/translate list all in tmp"
        mock_normal_accept_handler = MagicMock() 

        flow_task = asyncio.create_task(
            ui_manager_instance.prompt_for_command_confirmation(
                command_to_confirm, display_source, mock_normal_accept_handler
            )
        )

        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_confirmation_main_choice_response', 'e'),      
                ('_handle_confirmation_after_explain_response', 'y') 
            ]
        )

        result = await flow_task
        assert result == {'action': 'execute', 'command': command_to_confirm}
        mock_explain_ai.assert_called_once_with(command_to_confirm, ui_manager_instance.config, ui_manager_instance.append_output)
        assert not ui_manager_instance.confirmation_flow_active
        
        explanation_found_in_output = False
        for call_args in ui_manager_instance.append_output.call_args_list:
            args, _ = call_args
            if "This is a detailed explanation of the command." in args[0]:
                explanation_found_in_output = True
                break
        assert explanation_found_in_output, "Explanation was not appended to output"


    @pytest.mark.asyncio
    async def test_conf_flow_categorize_simple_direct(self, ui_manager_instance, mock_buffer_input):
        command_to_confirm = "echo 'direct simple'"
        display_source = "/translate echo simple"
        mock_normal_accept_handler = MagicMock()

        flow_task = asyncio.create_task(
            ui_manager_instance.prompt_for_command_confirmation(
                command_to_confirm, display_source, mock_normal_accept_handler
            )
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_confirmation_main_choice_response', 'ys') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'execute_and_categorize', 'command': command_to_confirm, 'category': 'simple'}
        assert not ui_manager_instance.confirmation_flow_active

    @pytest.mark.asyncio
    async def test_conf_flow_modify_command(self, ui_manager_instance, mock_buffer_input):
        command_to_confirm = "some_command_to_edit"
        display_source = "/translate edit this"
        mock_normal_accept_handler = MagicMock()

        flow_task = asyncio.create_task(
            ui_manager_instance.prompt_for_command_confirmation(
                command_to_confirm, display_source, mock_normal_accept_handler
            )
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_confirmation_main_choice_response', 'm') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'edit_mode_engaged', 'command': command_to_confirm}
        assert ui_manager_instance.is_in_edit_mode 
        assert ui_manager_instance.input_field.buffer.document.text == command_to_confirm
        assert ui_manager_instance.input_field.buffer.accept_handler == mock_normal_accept_handler
        assert not ui_manager_instance.confirmation_flow_active 

    @pytest.mark.asyncio
    async def test_conf_flow_cancel_direct(self, ui_manager_instance, mock_buffer_input):
        command_to_confirm = "dangerous_command"
        display_source = "/translate do something risky"
        mock_normal_accept_handler = MagicMock()

        flow_task = asyncio.create_task(
            ui_manager_instance.prompt_for_command_confirmation(
                command_to_confirm, display_source, mock_normal_accept_handler
            )
        )
        await simulate_input_sequence( # Call as module-level function
            ui_manager_instance,
            [
                ('_handle_confirmation_main_choice_response', 'c') 
            ]
        )
        result = await flow_task
        assert result == {'action': 'cancel'}
        assert not ui_manager_instance.confirmation_flow_active

# class TestKeyBindingsInUIManager: 
#     pass
