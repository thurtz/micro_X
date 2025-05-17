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
from modules.ai_handler import _clean_extracted_command # Assuming ai_handler.py is in a 'modules' subdirectory

# Test cases for _clean_extracted_command
# Each tuple: (input_string, expected_output_string)
clean_command_test_cases = [
    # Basic tag stripping
    ("<bash>ls -l</bash>", "ls -l"),
    ("  <bash>  ls -l  </bash>  ", "ls -l"),
    ("<code>pwd</code>", "pwd"),
    ("<cmd>echo hello</cmd>", "echo hello"),
    ("<command>git status</command>", "git status"),
    ("<pre>cat file.txt</pre>", "cat file.txt"),

    # Stripping quotes and backticks
    ("<bash>'ls -l'</bash>", "ls -l"),
    ("<bash>`ls -l`</bash>", "ls -l"),
    ("'echo test'", "echo test"), # Outer quotes without tags
    ("`cat file`", "cat file"),   # Outer backticks without tags

    # Mixed cases
    ("  <bash> '  echo \"Hello World\"  ' </bash>  ", 'echo "Hello World"'),
    # Current _clean_extracted_command behavior: strips one layer of backticks from ```
    ("```bash\nls -la\n```", "``bash\nls -la\n``"),
    ("```\n  git diff --cached \n```", "``\n  git diff --cached \n``"),

    # AI refusal phrases
    ("Sorry, I cannot fulfill that request.", ""),
    # This test WILL FAIL until _clean_extracted_command in ai_handler.py is fixed
    # to correctly identify "I am unable to..." as a refusal.
    # The expected output "" is the DESIRED behavior of the function.
    ("I am unable to generate that command.", ""),
    ("Cannot translate safely", ""),
    # _clean_extracted_command does not strip <unsafe> tags as per its current tag list.
    ("<unsafe>Cannot translate safely</unsafe>", "<unsafe>Cannot translate safely</unsafe>"),

    # Already clean commands
    ("ls -l", "ls -l"),
    ("echo 'Hello World'", "echo 'Hello World'"),

    # Leading slash removal (specific fix from original code)
    ("/ls", "ls"),
    ("/pwd", "pwd"),
    ("cd /home/user", "cd /home/user"),

    # Nested-like structures
    ("<bash><cmd>ls</cmd></bash>", "<cmd>ls</cmd>"),
    ("<code>'pwd'</code>", "pwd"),

    # Edge cases
    ("", ""),
    ("   ", ""),
    ("<bash></bash>", ""),
    ("<code> </code>", ""),

    # Shell command prefixes
    ("bash ls -l", "bash ls -l"),
    ("sh <command>", "command"),
    ("bash <my_command --arg>", "my_command --arg"),
    ("bash <ls | grep py>", "bash <ls | grep py>"),

    # Angle brackets not part of a command structure
    ("<ls -l>", "ls -l"),
    ("<echo hello world>", "echo hello world"),
    ("<cat file.txt | grep error>", "<cat file.txt | grep error>")
]

@pytest.mark.parametrize("input_str, expected_output", clean_command_test_cases)
def test_clean_extracted_command(input_str, expected_output):
    """
    Tests the _clean_extracted_command function with various inputs.
    """
    assert _clean_extracted_command(input_str) == expected_output

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