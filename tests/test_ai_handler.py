# tests/test_ai_handler.py
#
# Unit tests for functions in modules/ai_handler.py
# To run:
# 1. Ensure pytest and pytest-mock are installed in your virtual environment:
#    pip install pytest pytest-mock
# 2. Navigate to the root directory of the micro_X project.
# 3. Run pytest:
#    pytest
#
# You might need to adjust PYTHONPATH if your modules are not found, e.g.:
#    PYTHONPATH=. pytest
# or create a conftest.py in the root or tests directory.

import pytest


# ---
# To test is_valid_linux_command_according_to_ai and other functions
# that call ollama.chat, you would use pytest-mock's `mocker` fixture:
# ---
# async def test_is_valid_linux_command_ai_yes(mocker): # Mark test as async
#     # Mock the ollama.chat call
#     mock_ollama_chat = mocker.patch('modules.ai_handler.ollama.chat') # Patch where it's used
#     mock_ollama_chat.return_value = {'message': {'content': 'yes'}}
#
#     config_param = {
#         "prompts": {"validator": {"system": "sys", "user_template": "Is '{command_text}' valid?"}},
#         "ai_models": {"validator": "test-validator-model"},
#         "behavior": {"validator_ai_attempts": 1, "ai_retry_delay_seconds": 0.1, "ollama_api_call_retries": 0}
#     }
#     from modules.ai_handler import is_valid_linux_command_according_to_ai
#     is_valid = await is_valid_linux_command_according_to_ai("ls -l", config_param)
#     assert is_valid is True
#     mock_ollama_chat.assert_called_once()