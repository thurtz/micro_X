# tests/test_git_context_manager.py
import pytest
import asyncio
import subprocess
import os
from unittest.mock import MagicMock, AsyncMock, patch
from modules.git_context_manager import GitContextManager, FETCH_SUCCESS, FETCH_TIMEOUT, FETCH_OFFLINE, FETCH_ERROR

@pytest.fixture
def mock_gcm_subprocess_run(mocker):
    mock_run = MagicMock(spec=subprocess.run)
    mocker.patch('modules.git_context_manager.subprocess.run', new=mock_run)
    return mock_run

@pytest.fixture
def gcm_instance(mocker):
    mocker.patch('modules.git_context_manager.shutil.which', return_value='/usr/bin/git')
    mocker.patch('modules.git_context_manager.os.path.isdir', return_value=True)
    instance = GitContextManager(project_root="/fake/repo")
    instance._is_git_available_cached = True
    instance._git_executable_path = '/usr/bin/git'
    return instance

@pytest.mark.asyncio
async def test_is_git_available_caching(gcm_instance, mocker):
    assert await gcm_instance.is_git_available() is True
    mock_shutil_which = mocker.patch('modules.git_context_manager.shutil.which')
    await gcm_instance.is_git_available()
    mock_shutil_which.assert_not_called()

@pytest.mark.asyncio
async def test_is_repository_caching(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.return_value = MagicMock(returncode=0, stdout="true")
    assert await gcm_instance.is_repository() is True
    mock_gcm_subprocess_run.reset_mock()
    await gcm_instance.is_repository()
    mock_gcm_subprocess_run.assert_not_called()

@pytest.mark.asyncio
async def test_run_git_command_with_error(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal error")
    success, stdout, stderr = await gcm_instance._run_git_command(["status"])
    assert success is False
    assert stderr == "fatal error"

@pytest.mark.asyncio
async def test_fetch_remote_branch_offline_pattern(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=1, stderr="Could not resolve hostname: github.com")
    ]
    res = await gcm_instance.fetch_remote_branch("main")
    assert res == FETCH_OFFLINE

@pytest.mark.asyncio
async def test_compare_head_diverged_explicit(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=0), # fetch
        MagicMock(returncode=0, stdout="local_hash"), # head
        MagicMock(returncode=0, stdout="remote_hash"), # remote
        MagicMock(returncode=1), # local not ancestor of remote
        MagicMock(returncode=1), # remote not ancestor of local
    ]
    status, _, _, _ = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "diverged"

@pytest.mark.asyncio
async def test_compare_head_no_upstream_info(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=1, stderr="fetch error"), # fetch fail
        MagicMock(returncode=0, stdout="local"), # head
        MagicMock(returncode=1, stderr="no such ref"), # remote hash fail
    ]
    status, _, _, _ = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "no_upstream_info_locally"

@pytest.mark.asyncio
async def test_get_current_branch_fail(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=1)  # rev-parse fail
    ]
    assert await gcm_instance.get_current_branch() is None

@pytest.mark.asyncio
async def test_run_git_command_timeout(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=5)
    success, stdout, stderr = await gcm_instance._run_git_command(["fetch"], timeout=5)
    assert success is False
    assert "timed out after 5 seconds" in stderr

@pytest.mark.asyncio
async def test_run_git_command_file_not_found(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = FileNotFoundError()
    success, stdout, stderr = await gcm_instance._run_git_command(["status"])
    assert success is False
    assert "Git executable not found" in stderr
    assert gcm_instance._is_git_available_cached is False

@pytest.mark.asyncio
async def test_run_git_command_unexpected_exception(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = Exception("Unexpected")
    success, stdout, stderr = await gcm_instance._run_git_command(["status"])
    assert success is False
    assert stderr == "Unexpected"

@pytest.mark.asyncio
async def test_is_git_available_failure(mocker):
    mocker.patch('modules.git_context_manager.shutil.which', return_value=None)
    gcm = GitContextManager()
    assert await gcm.is_git_available() is False

@pytest.mark.asyncio
async def test_fetch_remote_branch_timeout(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        subprocess.TimeoutExpired(cmd="git fetch", timeout=5)
    ]
    res = await gcm_instance.fetch_remote_branch("main")
    assert res == FETCH_TIMEOUT

@pytest.mark.asyncio
async def test_fetch_remote_branch_other_error(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=1, stderr="Permission denied")
    ]
    res = await gcm_instance.fetch_remote_branch("main")
    assert res == FETCH_ERROR

@pytest.mark.asyncio
async def test_fetch_remote_branch_not_a_repo(gcm_instance, mocker):
    gcm_instance.is_repository = AsyncMock(return_value=False)
    res = await gcm_instance.fetch_remote_branch("main")
    assert res == "not_a_repo"

@pytest.mark.asyncio
async def test_compare_head_ahead_local_cache(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=1, stderr="could not resolve hostname"), # fetch fail (offline)
        MagicMock(returncode=0, stdout="local_hash"), # head
        MagicMock(returncode=0, stdout="remote_hash"), # remote hash success (from cache)
        MagicMock(returncode=1), # local not ancestor of remote
        MagicMock(returncode=0), # remote IS ancestor of local
    ]
    status, _, _, fetch_status = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "ahead_local_cache"
    assert fetch_status == FETCH_OFFLINE

@pytest.mark.asyncio
async def test_compare_head_no_upstream(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=0), # fetch success
        MagicMock(returncode=0, stdout="local"), # head
        MagicMock(returncode=1, stderr="no such ref"), # remote hash fail
        MagicMock(returncode=1, stderr="no upstream"), # rev-parse --symbolic-full-name fail
    ]
    status, _, _, _ = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "no_upstream"

@pytest.mark.asyncio
async def test_is_working_directory_clean_fail(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=1, stderr="status error")
    ]
    assert await gcm_instance.is_working_directory_clean() is False

@pytest.mark.asyncio
async def test_compare_head_error_local_hash(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=0), # fetch success
        MagicMock(returncode=1, stderr="head error") # head fail
    ]
    status, _, _, _ = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "error"

@pytest.mark.asyncio
async def test_compare_head_no_remote_hash_but_upstream_exists_error(gcm_instance, mock_gcm_subprocess_run):
    mock_gcm_subprocess_run.side_effect = [
        MagicMock(returncode=0), # is_repo
        MagicMock(returncode=0), # fetch success
        MagicMock(returncode=0, stdout="local"), # head
        MagicMock(returncode=1, stderr="no such ref"), # remote hash fail
        MagicMock(returncode=0, stdout="refs/remotes/origin/main"), # upstream exists
    ]
    status, _, _, _ = await gcm_instance.compare_head_with_remote_tracking("main")
    assert status == "error"