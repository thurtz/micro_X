# tests/test_git_context_manager.py
import pytest
import asyncio
import subprocess # For TimeoutExpired
from unittest.mock import MagicMock, AsyncMock, patch # AsyncMock for async methods if GCM had them

from modules.git_context_manager import GitContextManager

# Requires pytest-asyncio installed

@pytest.fixture
def mock_gcm_subprocess_run(mocker):
    """Fixture to mock subprocess.run used by GitContextManager._run_git_command."""
    mock_run = MagicMock(spec=subprocess.run) # Use spec for better mocking
    # Patch where asyncio.to_thread calls subprocess.run.
    mocker.patch('modules.git_context_manager.subprocess.run', new=mock_run)
    return mock_run

@pytest.fixture
def gcm_instance(mocker):
    """Provides a GitContextManager instance with basic mocks for git availability and repo status."""
    mocker.patch('modules.git_context_manager.shutil.which', return_value='/usr/bin/git')
    mocker.patch('modules.git_context_manager.os.path.isdir', return_value=True) # Assume .git dir exists
    
    instance = GitContextManager(project_root="/fake/repo") # Uses default fetch_timeout
    # Pre-populate caches for simplicity in many tests, can be overridden
    instance._is_git_available_cached = True
    instance._git_executable_path = '/usr/bin/git'
    # _is_git_repo will be set based on mocked _run_git_command for 'rev-parse --is-inside-work-tree'
    return instance

@pytest.fixture
def gcm_instance_custom_timeout(mocker):
    """Provides a GCM instance with a custom fetch_timeout for specific tests."""
    mocker.patch('modules.git_context_manager.shutil.which', return_value='/usr/bin/git')
    mocker.patch('modules.git_context_manager.os.path.isdir', return_value=True)
    
    instance = GitContextManager(project_root="/fake/repo", fetch_timeout=3) # Custom timeout
    instance._is_git_available_cached = True
    instance._git_executable_path = '/usr/bin/git'
    return instance


@pytest.fixture
def gcm_instance_no_git(mocker):
    """Provides a GCM instance where git is not available."""
    mocker.patch('modules.git_context_manager.shutil.which', return_value=None)
    instance = GitContextManager(project_root="/fake/repo_no_git")
    return instance

@pytest.fixture
def gcm_instance_not_a_repo(mocker):
    """Provides a GCM instance where it's not a git repository."""
    mocker.patch('modules.git_context_manager.shutil.which', return_value='/usr/bin/git')
    mocker.patch('modules.git_context_manager.os.path.isdir', return_value=False) # .git dir does not exist
    instance = GitContextManager(project_root="/fake/not_a_repo")
    instance._is_git_available_cached = True
    instance._git_executable_path = '/usr/bin/git'
    return instance


# --- Tests for is_git_available ---
@pytest.mark.asyncio
async def test_is_git_available_success(gcm_instance, mocker): # gcm_instance already mocks shutil.which
    assert await gcm_instance.is_git_available() is True
    assert gcm_instance._git_executable_path == '/usr/bin/git'
    # Test caching: call again, shutil.which should not be called again
    mock_shutil_which = mocker.patch('modules.git_context_manager.shutil.which')
    await gcm_instance.is_git_available() # Call again
    mock_shutil_which.assert_not_called()

@pytest.mark.asyncio
async def test_is_git_available_failure(gcm_instance_no_git, mocker):
    assert await gcm_instance_no_git.is_git_available() is False
    assert gcm_instance_no_git._git_executable_path is None
    # Test caching
    mock_shutil_which = mocker.patch('modules.git_context_manager.shutil.which')
    await gcm_instance_no_git.is_git_available()
    mock_shutil_which.assert_not_called()

# --- Tests for is_repository ---
@pytest.mark.asyncio
async def test_is_repository_success(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_gcm_subprocess_run.return_value = mock_process_repo_check # For 'rev-parse --is-inside-work-tree'
    
    assert await gcm_instance.is_repository() is True
    mock_gcm_subprocess_run.assert_called_once_with(
        ['/usr/bin/git', 'rev-parse', '--is-inside-work-tree'],
        capture_output=True, text=True, cwd=gcm_instance.project_root, check=False, timeout=None, errors='replace'
    )
    # Test caching
    mock_gcm_subprocess_run.reset_mock()
    await gcm_instance.is_repository() # Call again
    mock_gcm_subprocess_run.assert_not_called()


@pytest.mark.asyncio
async def test_is_repository_failure_not_repo_dir(gcm_instance_not_a_repo, mock_gcm_subprocess_run):
    # os.path.isdir for .git is already mocked to False by the fixture
    assert await gcm_instance_not_a_repo.is_repository() is False
    mock_gcm_subprocess_run.assert_not_called() # Should not even try git commands if .git dir is missing

@pytest.mark.asyncio
async def test_is_repository_failure_git_command_fails(gcm_instance, mock_gcm_subprocess_run):
    mock_process_failure = MagicMock(returncode=1, stdout="", stderr="git error")
    mock_gcm_subprocess_run.return_value = mock_process_failure # For 'rev-parse --is-inside-work-tree'
    
    assert await gcm_instance.is_repository() is False

@pytest.mark.asyncio
async def test_is_repository_git_not_available(gcm_instance_no_git, mock_gcm_subprocess_run):
    assert await gcm_instance_no_git.is_repository() is False
    mock_gcm_subprocess_run.assert_not_called()


# --- Tests for get_current_branch ---
@pytest.mark.asyncio
async def test_get_current_branch_success(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="") # For is_repository
    mock_process_branch = MagicMock(returncode=0, stdout="dev", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_branch]

    branch = await gcm_instance.get_current_branch()
    assert branch == "dev"
    assert mock_gcm_subprocess_run.call_count == 2
    assert mock_gcm_subprocess_run.call_args_list[1][0][0] == ['/usr/bin/git', 'rev-parse', '--abbrev-ref', 'HEAD']

@pytest.mark.asyncio
async def test_get_current_branch_detached_head(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_branch = MagicMock(returncode=0, stdout="HEAD", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_branch]
    branch = await gcm_instance.get_current_branch()
    assert branch == "HEAD"

@pytest.mark.asyncio
async def test_get_current_branch_failure(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_failure = MagicMock(returncode=1, stdout="", stderr="git error")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_failure]
    branch = await gcm_instance.get_current_branch()
    assert branch is None

# --- Tests for get_head_commit_hash ---
@pytest.mark.asyncio
async def test_get_head_commit_hash_success(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_commit = MagicMock(returncode=0, stdout="abcdef123456", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_commit]
    commit = await gcm_instance.get_head_commit_hash()
    assert commit == "abcdef123456"

@pytest.mark.asyncio
async def test_get_head_commit_hash_failure(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_failure = MagicMock(returncode=1, stdout="", stderr="git error")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_failure]
    commit = await gcm_instance.get_head_commit_hash()
    assert commit is None

# --- Tests for is_working_directory_clean ---
@pytest.mark.asyncio
async def test_is_working_directory_clean_when_clean(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_status_clean = MagicMock(returncode=0, stdout="", stderr="") # Empty stdout for clean
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_status_clean]
    assert await gcm_instance.is_working_directory_clean() is True

@pytest.mark.asyncio
async def test_is_working_directory_clean_when_dirty_modified(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_status_dirty = MagicMock(returncode=0, stdout=" M modified_file.py", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_status_dirty]
    assert await gcm_instance.is_working_directory_clean() is False

@pytest.mark.asyncio
async def test_is_working_directory_clean_when_dirty_untracked(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_status_dirty = MagicMock(returncode=0, stdout="?? untracked_file.py", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_status_dirty]
    assert await gcm_instance.is_working_directory_clean() is False # Untracked also means not clean by this check

@pytest.mark.asyncio
async def test_is_working_directory_clean_status_fails(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_status_fail = MagicMock(returncode=1, stdout="", stderr="git status error")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_status_fail]
    assert await gcm_instance.is_working_directory_clean() is False # Treat as not clean

# --- Tests for fetch_remote_branch ---
@pytest.mark.asyncio
async def test_fetch_remote_branch_success(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_fetch = MagicMock(returncode=0, stdout="Fetched.", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_fetch]
    assert await gcm_instance.fetch_remote_branch("main") is True

@pytest.mark.asyncio
async def test_fetch_remote_branch_failure(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_fetch_fail = MagicMock(returncode=1, stdout="", stderr="Fetch error")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_fetch_fail]
    assert await gcm_instance.fetch_remote_branch("main") is False

@pytest.mark.asyncio
async def test_fetch_remote_branch_timeout(gcm_instance_custom_timeout, mock_gcm_subprocess_run):
    # Use gcm_instance_custom_timeout to ensure self.fetch_timeout is what we expect
    gcm_instance = gcm_instance_custom_timeout 
    
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    # This TimeoutExpired should be raised when _run_git_command calls subprocess.run
    # with timeout=gcm_instance.fetch_timeout (which is 3 for this fixture)
    mock_gcm_subprocess_run.side_effect = [
        mock_process_repo_check,  # For is_repository() call
        subprocess.TimeoutExpired(cmd="git fetch origin main", timeout=gcm_instance.fetch_timeout) 
    ]
    
    assert await gcm_instance.fetch_remote_branch("main") is False # No explicit timeout here
    
    # Verify that _run_git_command (which calls subprocess.run) was called for fetch
    # with the instance's configured timeout.
    # The first call to subprocess.run is for is_repository, second is for fetch.
    assert mock_gcm_subprocess_run.call_count == 2
    fetch_call_kwargs = mock_gcm_subprocess_run.call_args_list[1][1] # kwargs of the second call
    assert fetch_call_kwargs.get('timeout') == gcm_instance.fetch_timeout # Should be 3


# --- Tests for get_remote_tracking_branch_hash ---
@pytest.mark.asyncio
async def test_get_remote_tracking_branch_hash_success(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_remote_hash = MagicMock(returncode=0, stdout="fedcba987654", stderr="")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_remote_hash]
    remote_hash = await gcm_instance.get_remote_tracking_branch_hash("main")
    assert remote_hash == "fedcba987654"

@pytest.mark.asyncio
async def test_get_remote_tracking_branch_hash_failure(gcm_instance, mock_gcm_subprocess_run):
    mock_process_repo_check = MagicMock(returncode=0, stdout="true", stderr="")
    mock_process_remote_hash_fail = MagicMock(returncode=1, stdout="", stderr="No such remote ref")
    mock_gcm_subprocess_run.side_effect = [mock_process_repo_check, mock_process_remote_hash_fail]
    remote_hash = await gcm_instance.get_remote_tracking_branch_hash("nonexistent-remote-branch")
    assert remote_hash is None


# --- Tests for compare_head_with_remote_tracking ---
@pytest.mark.asyncio
async def test_compare_head_synced(gcm_instance, mock_gcm_subprocess_run):
    common_hash = "123abc456def"
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0, stdout="true", stderr=""),                  # is_repository check
        MagicMock(returncode=0, stdout="Fetched.", stderr=""),              # fetch_remote_branch (internal call to _run_git_command)
        MagicMock(returncode=0, stdout=common_hash, stderr=""),             # get_head_commit_hash
        MagicMock(returncode=0, stdout=common_hash, stderr=""),             # get_remote_tracking_branch_hash
    ]
    status, local_h, remote_h = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "synced"
    assert local_h == common_hash
    assert remote_h == common_hash

@pytest.mark.asyncio
async def test_compare_head_ahead(gcm_instance, mock_gcm_subprocess_run):
    local_hash = "ahead123"
    remote_hash = "base456"
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0, stdout="true", stderr=""),                  # is_repository
        MagicMock(returncode=0, stdout="Fetched.", stderr=""),              # fetch
        MagicMock(returncode=0, stdout=local_hash, stderr=""),              # get_head
        MagicMock(returncode=0, stdout=remote_hash, stderr=""),             # get_remote_tracking
        MagicMock(returncode=1, stdout="", stderr=""),                      # is_ancestor local remote (local is NOT ancestor of remote)
        MagicMock(returncode=0, stdout="", stderr=""),                      # is_ancestor remote local (remote IS ancestor of local)
    ]
    status, lh, rh = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "ahead"
    assert lh == local_hash
    assert rh == remote_hash

@pytest.mark.asyncio
async def test_compare_head_behind(gcm_instance, mock_gcm_subprocess_run):
    local_hash = "base456"
    remote_hash = "behind789"
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0, stdout="true", stderr=""),                  # is_repository
        MagicMock(returncode=0, stdout="Fetched.", stderr=""),              # fetch
        MagicMock(returncode=0, stdout=local_hash, stderr=""),              # get_head
        MagicMock(returncode=0, stdout=remote_hash, stderr=""),             # get_remote_tracking
        MagicMock(returncode=0, stdout="", stderr=""),                      # is_ancestor local remote (local IS ancestor of remote)
    ]
    status, lh, rh = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "behind"

@pytest.mark.asyncio
async def test_compare_head_diverged(gcm_instance, mock_gcm_subprocess_run):
    local_hash = "diverged_local"
    remote_hash = "diverged_remote"
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0, stdout="true", stderr=""),                  # is_repository
        MagicMock(returncode=0, stdout="Fetched.", stderr=""),              # fetch
        MagicMock(returncode=0, stdout=local_hash, stderr=""),              # get_head
        MagicMock(returncode=0, stdout=remote_hash, stderr=""),             # get_remote_tracking
        MagicMock(returncode=1, stdout="", stderr=""),                      # is_ancestor local remote -> False
        MagicMock(returncode=1, stdout="", stderr=""),                      # is_ancestor remote local -> False
    ]
    status, lh, rh = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "diverged"

@pytest.mark.asyncio
async def test_compare_head_no_upstream(gcm_instance, mock_gcm_subprocess_run):
    local_hash = "localonly123"
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0, stdout="true", stderr=""),                  # is_repository
        MagicMock(returncode=0, stdout="Fetched.", stderr=""),              # fetch (succeeds)
        MagicMock(returncode=0, stdout=local_hash, stderr=""),              # get_head
        MagicMock(returncode=1, stdout="", stderr="No such ref"),           # get_remote_tracking_branch_hash fails
        MagicMock(returncode=1, stdout="", stderr="No upstream configured"),# rev-parse --symbolic-full-name <branch>@{upstream} fails
    ]
    status, lh, rh = await gcm_instance.compare_head_with_remote_tracking("local-branch")
    assert status == "no_upstream"
    assert lh == local_hash
    assert rh is None

@pytest.mark.asyncio
async def test_compare_head_fetch_fails_then_no_remote_hash(gcm_instance, mock_gcm_subprocess_run):
    """Test when fetch fails, and subsequently remote hash cannot be found."""
    local_hash = "localhash_fetchfail"
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0, stdout="true", stderr=""),                      # is_repository
        MagicMock(returncode=1, stdout="", stderr="Fetch failed error"),        # fetch_remote_branch (internal _run_git_command) fails
        MagicMock(returncode=0, stdout=local_hash, stderr=""),                  # get_head_commit_hash
        MagicMock(returncode=1, stdout="", stderr="No such ref for remote"),    # get_remote_tracking_branch_hash fails
        MagicMock(returncode=1, stdout="", stderr="No upstream configured"),    # rev-parse --symbolic-full-name <branch>@{upstream} fails
    ]
    status, lh, rh = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "no_upstream" 
    assert lh == local_hash
    assert rh is None

