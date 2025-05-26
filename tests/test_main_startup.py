# tests/test_main_startup.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# We need to import the function we want to test from main.py.
# This assumes main.py is structured in a way that this function can be imported.
# If main.py relies heavily on global state that's hard to set up for tests,
# this might require some minor refactoring in main.py or more complex patching.
# For now, we'll assume 'perform_startup_integrity_checks' and necessary globals
# can be accessed or patched.

# To effectively test, we need to patch the globals main.py uses within this function's scope
# Specifically: git_context_manager_instance, ui_manager_instance, config, SCRIPT_DIR (if used directly)

@pytest.fixture
def mock_main_globals(mocker):
    """Mocks globals used by perform_startup_integrity_checks in main.py"""
    mock_ui = MagicMock()
    mock_ui.append_output = MagicMock()
    mocker.patch('main.ui_manager_instance', new=mock_ui)

    # Default config for tests, can be overridden in specific tests
    mock_cfg = {
        "integrity_check": {
            "protected_branches": ["main", "testing"],
            "developer_branch": "dev",
            "halt_on_integrity_failure": True
        },
        "timeouts": {"git_fetch_timeout": 5} # Example timeout
    }
    mocker.patch('main.config', new=mock_cfg)

    # Mock SCRIPT_DIR as it's used for GitContextManager project_root
    mocker.patch('main.SCRIPT_DIR', new="/fake/project_root")
    
    return mock_ui, mock_cfg

@pytest.fixture
def mock_git_context_manager(mocker):
    """Mocks the GitContextManager class, returning an AsyncMock instance."""
    mock_gcm_instance = AsyncMock() # All its methods used by main are async
    # Ensure _run_git_command exists on the mock as it's called directly in main.py for status details
    mock_gcm_instance._run_git_command = AsyncMock() 
    mock_gcm_class = MagicMock(return_value=mock_gcm_instance)
    mocker.patch('main.GitContextManager', new=mock_gcm_class)
    return mock_gcm_instance, mock_gcm_class


@pytest.mark.asyncio
async def test_git_not_available(mock_main_globals, mock_git_context_manager):
    """Test scenario where Git command is not available."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, _ = mock_main_globals

    mock_gcm_instance.is_git_available.return_value = False

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is True # Should default to dev mode
    assert integrity_ok is True # Checks are skipped, so considered "ok" in this context
    mock_ui.append_output.assert_any_call(
        "⚠️ Git command not found. Integrity checks cannot be performed. Assuming developer mode.",
        style_class='error'
    )

@pytest.mark.asyncio
async def test_not_a_git_repository(mock_main_globals, mock_git_context_manager):
    """Test scenario where the project directory is not a Git repository."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, _ = mock_main_globals

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = False

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is True # Should default to dev mode
    assert integrity_ok is True # Checks are skipped
    
    expected_text_part = "is not a Git repository. Integrity checks cannot be performed. Assuming developer mode."
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if expected_text_part in args[0] and kwargs.get('style_class') == 'error':
            found_message = True
            break
    assert found_message, f"Expected message containing '{expected_text_part}' with style 'error' not found. Calls: {mock_ui.append_output.call_args_list}"


@pytest.mark.asyncio
async def test_on_developer_branch(mock_main_globals, mock_git_context_manager):
    """Test behavior when on the designated developer branch."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    
    dev_branch_name = mock_cfg["integrity_check"]["developer_branch"] 

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = dev_branch_name
    mock_gcm_instance.get_head_commit_hash.return_value = "devcommit123"

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is True
    assert integrity_ok is True 
    
    expected_message = f"✅ Running in Developer Mode (branch: '{dev_branch_name}'). Integrity checks are informational."
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        # UIManager.append_output adds a newline if not present.
        if args[0].strip() == expected_message.strip() and kwargs.get('style_class') == 'success':
            found_message = True
            break
    assert found_message, f"Expected message '{expected_message}' not found or style mismatch. Calls: {mock_ui.append_output.call_args_list}"


@pytest.mark.asyncio
async def test_on_protected_branch_all_clear(mock_main_globals, mock_git_context_manager):
    """Test behavior on a protected branch when all integrity checks pass."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0] 

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.get_head_commit_hash.return_value = "maincommit123"
    mock_gcm_instance.is_working_directory_clean.return_value = True
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("synced", "maincommit123", "maincommit123")

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is True
    
    # Check for the individual success messages
    expected_clean_message = f"✅ Working directory is clean for branch '{protected_branch}'."
    expected_sync_message = f"✅ Branch '{protected_branch}' is synced with 'origin/{protected_branch}'."
    # The overall "All integrity checks passed" message was removed from main.py, so we don't check for it.

    found_clean_message = False
    found_sync_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        msg_text_stripped = args[0].strip()
        style = kwargs.get('style_class')
        if msg_text_stripped == expected_clean_message.strip() and style == 'info':
            found_clean_message = True
        if msg_text_stripped == expected_sync_message.strip() and style == 'success':
            found_sync_message = True
            
    assert found_clean_message, f"Expected clean message '{expected_clean_message}' not found. Calls: {mock_ui.append_output.call_args_list}"
    assert found_sync_message, f"Expected sync success message '{expected_sync_message}' not found. Calls: {mock_ui.append_output.call_args_list}"

@pytest.mark.asyncio
async def test_on_protected_branch_not_clean(mock_main_globals, mock_git_context_manager):
    """Test behavior on a protected branch when the working directory is not clean."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0]

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.get_head_commit_hash.return_value = "maincommit123"
    mock_gcm_instance.is_working_directory_clean.return_value = False 
    # This mock is for the _run_git_command call *inside* perform_startup_integrity_checks
    # when it tries to get details for the error message.
    mock_gcm_instance._run_git_command.return_value = (True, " M some_file.py", "") 

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is False
    
    expected_error_msg = f"❌ Integrity Check Failed (Branch: {protected_branch}): Uncommitted local changes or untracked files detected."
    expected_detail_msg_content = "M some_file.py" # This is part of the detail message
    
    found_error_msg = False
    found_detail_msg_content = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        msg_text = args[0] # Don't strip here, check full message
        style = kwargs.get('style_class')

        if msg_text.strip() == expected_error_msg.strip() and style == 'error':
            found_error_msg = True
        # The detail message starts with "   Git status details:\n"
        if expected_detail_msg_content in msg_text and "Git status details:" in msg_text and style == 'error':
            found_detail_msg_content = True
            
    assert found_error_msg, f"Expected error message '{expected_error_msg}' not found. Calls: {mock_ui.append_output.call_args_list}"
    assert found_detail_msg_content, f"Expected detail message content '{expected_detail_msg_content}' not found. Calls: {mock_ui.append_output.call_args_list}"


@pytest.mark.asyncio
async def test_on_protected_branch_not_synced_ahead(mock_main_globals, mock_git_context_manager):
    """Test behavior on a protected branch when it's ahead of remote."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0]

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.get_head_commit_hash.return_value = "local_ahead"
    mock_gcm_instance.is_working_directory_clean.return_value = True
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("ahead", "local_ahead", "remote_base")

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is False
    expected_message_part = f"Local branch has 'ahead' from 'origin/{protected_branch}'."
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if expected_message_part in args[0] and kwargs.get('style_class') == 'error':
            found_message = True
            break
    assert found_message, f"Expected error message containing '{expected_message_part}' not found. Calls: {mock_ui.append_output.call_args_list}"

@pytest.mark.asyncio
async def test_on_protected_branch_no_upstream(mock_main_globals, mock_git_context_manager):
    """Test behavior on a protected branch when there's no upstream configured."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0]

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.get_head_commit_hash.return_value = "localcommit"
    mock_gcm_instance.is_working_directory_clean.return_value = True
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("no_upstream", "localcommit", None)

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is False 
    expected_message_part = "Cannot reliably compare with remote. Status: no_upstream"
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if expected_message_part in args[0] and kwargs.get('style_class') == 'error':
            found_message = True
            break
    assert found_message, f"Expected error message containing '{expected_message_part}' not found. Calls: {mock_ui.append_output.call_args_list}"


@pytest.mark.asyncio
async def test_on_other_branch_defaults_to_dev_mode(mock_main_globals, mock_git_context_manager):
    """Test behavior on an unrecognized branch (e.g., feature branch)."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, _ = mock_main_globals
    
    other_branch = "feature/new-stuff"

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = other_branch
    mock_gcm_instance.get_head_commit_hash.return_value = "featurecommit"

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is True
    assert integrity_ok is True 
    expected_message = f"ℹ️ Running on unrecognized branch/commit '{other_branch}'. Developer mode assumed. Integrity checks informational."
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if args[0].strip() == expected_message.strip() and kwargs.get('style_class') == 'info':
            found_message = True
            break
    assert found_message, f"Expected info message '{expected_message}' not found. Calls: {mock_ui.append_output.call_args_list}"


@pytest.mark.asyncio
async def test_main_async_runner_halts_on_integrity_failure(mocker):
    """
    Test that main_async_runner halts if perform_startup_integrity_checks
    indicates failure on a protected branch.
    """
    mocker.patch('main.perform_startup_integrity_checks', new_callable=AsyncMock, return_value=(False, False))
    mock_exit_app_main = MagicMock()
    mocker.patch('main._exit_app_main', new=mock_exit_app_main)
    mocker.patch('main.config', {
        "integrity_check": {"halt_on_integrity_failure": True},
        "timeouts": {}, "behavior": {}, "ui": {}, "paths": {}, "prompts": {}, "ollama_service": {} 
    })
    mock_ui_manager_constructor = mocker.patch('main.UIManager') # Mock the constructor
    mock_ui_instance = MagicMock()
    mock_ui_instance.append_output = MagicMock()
    mock_ui_manager_constructor.return_value = mock_ui_instance # UIManager() returns our mock

    # Prevent further execution by not mocking other dependencies if not needed for this specific test path
    mocker.patch('main.ShellEngine', side_effect=AssertionError("ShellEngine should not be initialized if halting"))


    from main import main_async_runner
    await main_async_runner()
    mock_exit_app_main.assert_called_once()

@pytest.mark.asyncio
async def test_main_async_runner_proceeds_if_dev_mode_and_integrity_fails(mocker):
    """
    Test that main_async_runner proceeds if in dev mode, even if integrity_ok is False.
    """
    mocker.patch('main.perform_startup_integrity_checks', new_callable=AsyncMock, return_value=(True, False))
    mock_exit_app_main = MagicMock()
    mocker.patch('main._exit_app_main', new=mock_exit_app_main)
    mocker.patch('main.config', {
        "integrity_check": {"halt_on_integrity_failure": True},
        "timeouts": {}, "behavior": {}, "ui": {}, "paths": {}, "prompts": {}, "ollama_service": {}
    })
    
    mock_ui_manager_constructor = mocker.patch('main.UIManager')
    mock_ui_instance = MagicMock()
    mock_ui_instance.append_output = MagicMock()
    mock_ui_manager_constructor.return_value = mock_ui_instance
    
    mocker.patch('main.ShellEngine', side_effect=RuntimeError("ShellEngine init called, proceeding past integrity check"))

    from main import main_async_runner
    with pytest.raises(RuntimeError, match="ShellEngine init called, proceeding past integrity check"):
        await main_async_runner()
    mock_exit_app_main.assert_not_called()

