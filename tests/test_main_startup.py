# tests/test_main_startup.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Import the custom exception from main to test for it specifically
from main import StartupIntegrityError
from modules.git_context_manager import FETCH_SUCCESS, FETCH_TIMEOUT, FETCH_OFFLINE, FETCH_ERROR

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
            "halt_on_integrity_failure": True,
            "allow_run_if_behind_remote": True
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
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("synced", "maincommit123", "maincommit123", FETCH_SUCCESS)

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is True
    
    expected_clean_message = f"✅ Working directory is clean for branch '{protected_branch}'."
    expected_sync_message = f"✅ Branch '{protected_branch}' is synced with 'origin/{protected_branch}'."

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
    mock_gcm_instance._run_git_command.return_value = (True, " M some_file.py", "") 

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is False
    
    expected_error_msg = f"❌ Integrity Check Failed (Branch: {protected_branch}): Uncommitted local changes or untracked files detected."
    expected_detail_msg_content = "M some_file.py"
    
    found_error_msg = False
    found_detail_msg_content = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        msg_text = args[0]
        style = kwargs.get('style_class')

        if msg_text.strip() == expected_error_msg.strip() and style == 'error':
            found_error_msg = True
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
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("ahead", "local_ahead", "remote_base", FETCH_SUCCESS)

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
async def test_on_protected_branch_behind_and_disallowed(mock_main_globals, mock_git_context_manager):
    """Test halting when branch is behind and config disallows running."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0]
    mock_cfg["integrity_check"]["allow_run_if_behind_remote"] = False # Override config for this test

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.is_working_directory_clean.return_value = True
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("behind", "local_base", "remote_new", FETCH_SUCCESS)

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is False
    expected_message_part = "behind (and configuration disallows running)"
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if expected_message_part in args[0] and kwargs.get('style_class') == 'error':
            found_message = True
            break
    assert found_message, f"Expected error message for disallowed 'behind' state not found. Calls: {mock_ui.append_output.call_args_list}"

@pytest.mark.asyncio
async def test_on_protected_branch_fetch_offline_and_ahead_cache(mock_main_globals, mock_git_context_manager):
    """Test halting when fetch is offline and local cache shows 'ahead'."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0]

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.is_working_directory_clean.return_value = True
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("ahead_local_cache", "local_ahead", "remote_base", FETCH_OFFLINE)

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is False
    expected_message_part = "Local branch has unpushed changes or diverged from the last known remote state. Status: ahead_local_cache"
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if expected_message_part in args[0] and kwargs.get('style_class') == 'error':
            found_message = True
            break
    assert found_message, f"Expected error for 'ahead_local_cache' not found. Calls: {mock_ui.append_output.call_args_list}"

@pytest.mark.asyncio
async def test_on_protected_branch_fetch_offline_and_synced_cache(mock_main_globals, mock_git_context_manager):
    """Test proceeding when fetch is offline but local cache is synced."""
    from main import perform_startup_integrity_checks
    mock_gcm_instance, _ = mock_git_context_manager
    mock_ui, mock_cfg = mock_main_globals
    protected_branch = mock_cfg["integrity_check"]["protected_branches"][0]

    mock_gcm_instance.is_git_available.return_value = True
    mock_gcm_instance.is_repository.return_value = True
    mock_gcm_instance.get_current_branch.return_value = protected_branch
    mock_gcm_instance.is_working_directory_clean.return_value = True
    mock_gcm_instance.compare_head_with_remote_tracking.return_value = ("synced_local_cache", "common_hash", "common_hash", FETCH_TIMEOUT)

    is_dev_mode, integrity_ok = await perform_startup_integrity_checks()

    assert is_dev_mode is False
    assert integrity_ok is True # Integrity is considered OK in this case
    expected_message_part = "Running in offline-verified mode"
    found_message = False
    for call_args_tuple in mock_ui.append_output.call_args_list:
        args, kwargs = call_args_tuple
        if expected_message_part in args[0] and kwargs.get('style_class') == 'info':
            found_message = True
            break
    assert found_message, f"Expected message for 'offline-verified mode' not found. Calls: {mock_ui.append_output.call_args_list}"


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
    indicates failure on a protected branch. This test now passes if the
    correct exception is raised.
    """
    mocker.patch('main.perform_startup_integrity_checks', new_callable=AsyncMock, return_value=(False, False))
    mocker.patch('main.config', {
        "integrity_check": {"halt_on_integrity_failure": True},
        "timeouts": {}, "behavior": {}, "ui": {"ui_backend": "prompt_toolkit"}, "paths": {}, "prompts": {}, "ollama_service": {} 
    })
    mock_ui_manager_constructor = mocker.patch('main.UIManager')
    mock_ui_instance = MagicMock()
    mock_ui_instance.append_output = MagicMock()
    mock_ui_manager_constructor.return_value = mock_ui_instance
    
    from main import main_async_runner
    # This context manager asserts that the specific error is raised.
    # If it is, the test passes. If it's not, or a different error is raised, it fails.
    with pytest.raises(StartupIntegrityError, match="Failed integrity checks on a protected branch."):
        await main_async_runner()


@pytest.mark.asyncio
async def test_main_async_runner_proceeds_if_dev_mode_and_integrity_fails(mocker):
    """
    Test that main_async_runner proceeds if in dev mode, even if integrity_ok is False.
    This test is corrected to patch the right module.
    """
    mocker.patch('main.perform_startup_integrity_checks', new_callable=AsyncMock, return_value=(True, False)) # is_dev_mode=True, integrity_ok=False
    mocker.patch('main.config', {
        "integrity_check": {"halt_on_integrity_failure": True}, # Halt is true, but dev mode should override
        "timeouts": {}, "behavior": {}, "ui": {"ui_backend": "prompt_toolkit"}, "paths": {}, "prompts": {}, "ollama_service": {}
    })
    
    mock_ui_manager_constructor = mocker.patch('main.UIManager')
    mock_ui_instance = MagicMock()
    mock_ui_instance.append_output = MagicMock()
    mock_ui_instance.initialize_ui_elements = MagicMock()
    mock_ui_manager_constructor.return_value = mock_ui_instance
    
    mock_shell_engine_constructor = mocker.patch('main.ShellEngine')
    mock_shell_engine = MagicMock()
    # *** START OF FIX ***
    # Configure the mock shell engine instance to have an awaitable mock for the ollama service check
    mock_shell_engine.ollama_manager_module.ensure_ollama_service = AsyncMock(return_value=True)
    # *** END OF FIX ***
    mock_shell_engine_constructor.return_value = mock_shell_engine

    mock_git_context_manager_constructor = mocker.patch('main.GitContextManager')
    mock_git_context_manager = MagicMock()
    mock_git_context_manager_constructor.return_value = mock_git_context_manager
    
    mocker.patch('main.init_category_manager', MagicMock())
    mocker.patch('main.FileHistory', MagicMock())
    mock_app_run_async = mocker.patch('main.Application.run_async', new_callable=AsyncMock)

    from main import main_async_runner
    await main_async_runner()
    
    # Assert that ShellEngine was initialized, showing the runner proceeded
    mock_shell_engine_constructor.assert_called_once()
    
    # Assert that the application was run
    mock_app_run_async.assert_called_once()


@pytest.mark.asyncio
async def test_main_async_runner_proceeds_if_integrity_ok_and_not_halting(mocker):
    """
    Test that main_async_runner proceeds if integrity is OK, even if halt_on_failure is true.
    This test is corrected to patch the right module.
    """
    mocker.patch('main.perform_startup_integrity_checks', new_callable=AsyncMock, return_value=(False, True)) # is_dev_mode=False, integrity_ok=True
    mocker.patch('main.config', {
        "integrity_check": {"halt_on_integrity_failure": True}, # Halt is true, but integrity is OK
        "timeouts": {}, "behavior": {}, "ui": {"ui_backend": "prompt_toolkit"}, "paths": {}, "prompts": {}, "ollama_service": {}
    })
    
    mock_ui_manager_constructor = mocker.patch('main.UIManager')
    mock_ui_instance = MagicMock()
    mock_ui_instance.append_output = MagicMock()
    mock_ui_instance.initialize_ui_elements = MagicMock()
    mock_ui_manager_constructor.return_value = mock_ui_instance
    
    mock_shell_engine_constructor = mocker.patch('main.ShellEngine')
    mock_shell_engine = MagicMock()
    # *** START OF FIX ***
    # Configure the mock shell engine instance to have an awaitable mock for the ollama service check
    mock_shell_engine.ollama_manager_module.ensure_ollama_service = AsyncMock(return_value=True)
    # *** END OF FIX ***
    mock_shell_engine_constructor.return_value = mock_shell_engine
    
    mock_git_context_manager_constructor = mocker.patch('main.GitContextManager')
    mock_git_context_manager = MagicMock()
    mock_git_context_manager_constructor.return_value = mock_git_context_manager
    
    mocker.patch('main.init_category_manager', MagicMock())
    mocker.patch('main.FileHistory', MagicMock())
    mock_app_run_async = mocker.patch('main.Application.run_async', new_callable=AsyncMock)

    from main import main_async_runner
    await main_async_runner()

    # Assert that ShellEngine was initialized, showing the runner proceeded
    mock_shell_engine_constructor.assert_called_once()
    
    # Assert that the application was run
    mock_app_run_async.assert_called_once()
