# tests/test_git_context_manager.py
import pytest
import asyncio # For marker if needed, though pytest-asyncio handles it
from unittest.mock import MagicMock, AsyncMock # AsyncMock for patching async methods if GCM had them

from modules.git_context_manager import GitContextManager

# Requires pytest-asyncio installed

@pytest.fixture
def mock_gcm_subprocess_run(mocker):
    """Fixture to mock subprocess.run used by GitContextManager."""
    mock_run = MagicMock() # subprocess.run is synchronous
    # Patch where asyncio.to_thread calls subprocess.run.
    # If _run_git_command directly used subprocess.run, this would be simpler.
    # For now, let's assume we can control what subprocess.run returns when called by asyncio.to_thread.
    # A more direct approach would be to patch 'modules.git_context_manager.subprocess.run'
    mocker.patch('modules.git_context_manager.subprocess.run', new=mock_run)
    return mock_run

@pytest.fixture
def gcm_instance(mocker):
    """Provides a GitContextManager instance with basic mocks."""
    # Mock shutil.which to simulate git being available
    mocker.patch('modules.git_context_manager.shutil.which', return_value='/usr/bin/git')
    # Mock os.path.isdir for .git directory check
    mocker.patch('modules.git_context_manager.os.path.isdir', return_value=True)
    
    instance = GitContextManager(project_root="/fake/repo")
    # Ensure _is_git_available_cached and _is_git_repo are True for most tests
    # These would normally be set by calling the methods, but for isolated tests:
    instance._is_git_available_cached = True
    instance._git_executable_path = '/usr/bin/git' # Set explicitly
    # We'll let is_repository set itself or mock its internal _run_git_command call
    return instance

@pytest.mark.asyncio
async def test_get_current_branch_success(gcm_instance, mock_gcm_subprocess_run):
    """Test get_current_branch successfully returns a branch name."""
    # Simulate a successful 'git rev-parse --is-inside-work-tree' for is_repository()
    # Simulate a successful 'git rev-parse --abbrev-ref HEAD'
    mock_process_repo_check = MagicMock()
    mock_process_repo_check.returncode = 0
    mock_process_repo_check.stdout = "true"
    mock_process_repo_check.stderr = ""

    mock_process_branch = MagicMock()
    mock_process_branch.returncode = 0
    mock_process_branch.stdout = "dev"
    mock_process_branch.stderr = ""
    
    # _run_git_command calls subprocess.run. We need to control its return value for each call.
    # The first call within is_repository() is rev-parse --is-inside-work-tree
    # The second call within get_current_branch() is rev-parse --abbrev-ref HEAD
    mock_gcm_subprocess_run.side_effect = [
        mock_process_repo_check, # For the is_repository check
        mock_process_branch      # For the get_current_branch call
    ]

    branch = await gcm_instance.get_current_branch()
    assert branch == "dev"
    
    # Check that subprocess.run was called correctly
    assert mock_gcm_subprocess_run.call_count == 2
    first_call_args = mock_gcm_subprocess_run.call_args_list[0][0][0] # Args of first call
    second_call_args = mock_gcm_subprocess_run.call_args_list[1][0][0] # Args of second call
    
    assert first_call_args == ['/usr/bin/git', 'rev-parse', '--is-inside-work-tree']
    assert second_call_args == ['/usr/bin/git', 'rev-parse', '--abbrev-ref', 'HEAD']


@pytest.mark.asyncio
async def test_get_current_branch_detached_head(gcm_instance, mock_gcm_subprocess_run):
    """Test get_current_branch returns 'HEAD' for detached HEAD state."""
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_branch = MagicMock(returncode=0, stdout="HEAD", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_branch]

    branch = await gcm_instance.get_current_branch()
    assert branch == "HEAD"

@pytest.mark.asyncio
async def test_get_current_branch_failure(gcm_instance, mock_gcm_subprocess_run):
    """Test get_current_branch returns None on command failure."""
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_failure = MagicMock(returncode=1, stdout="", stderr="git error")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_failure]
    
    branch = await gcm_instance.get_current_branch()
    assert branch is None

# ... more tests for other methods ...