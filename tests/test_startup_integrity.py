# tests/test_startup_integrity.py

import pytest
from unittest.mock import MagicMock, AsyncMock
from modules.startup import integrity

@pytest.fixture
def mock_ui_manager():
    return MagicMock()

@pytest.fixture
def mock_git_manager():
    manager = MagicMock()
    manager.is_git_available = AsyncMock(return_value=True)
    manager.is_repository = AsyncMock(return_value=True)
    manager.get_current_branch = AsyncMock(return_value="main")
    manager.get_head_commit_hash = AsyncMock(return_value="abc1234")
    manager.is_working_directory_clean = AsyncMock(return_value=True)
    manager.compare_head_with_remote_tracking = AsyncMock(return_value=("synced", "abc", "abc", "success"))
    return manager

@pytest.fixture
def mock_config():
    return {
        "integrity_check": {
            "protected_branches": ["main"],
            "developer_branch": "dev",
            "halt_on_integrity_failure": True,
            "allow_run_if_behind_remote": True
        },
        "behavior": {"verbosity_level": "normal"},
        "application": {"version": "0.0.0"}
    }

@pytest.mark.asyncio
async def test_integrity_success(mock_config, mock_ui_manager, mock_git_manager):
    is_dev, is_ok = await integrity.perform_startup_integrity_checks(
        mock_config, mock_ui_manager, "/root", mock_git_manager
    )
    assert is_dev is False
    assert is_ok is True
    mock_ui_manager.append_output.assert_any_call("✅ Branch 'main' is synced with 'origin/main'.", style_class='success')

@pytest.mark.asyncio
async def test_integrity_not_git_repo(mock_config, mock_ui_manager, mock_git_manager):
    mock_git_manager.is_repository.return_value = False
    
    is_dev, is_ok = await integrity.perform_startup_integrity_checks(
        mock_config, mock_ui_manager, "/root", mock_git_manager
    )
    # Falls back to dev mode logic (returns True, True based on code)
    assert is_dev is True
    assert is_ok is True
    # Verify warning message
    calls = [str(call) for call in mock_ui_manager.append_output.call_args_list]
    assert any("not a Git repository" in c for c in calls)

@pytest.mark.asyncio
async def test_integrity_dirty_workdir_halt(mock_config, mock_ui_manager, mock_git_manager):
    mock_git_manager.is_working_directory_clean.return_value = False
    mock_git_manager._run_git_command = AsyncMock(return_value=(True, " M file.py"))
    
    with pytest.raises(integrity.StartupIntegrityError):
        await integrity.perform_startup_integrity_checks(
            mock_config, mock_ui_manager, "/root", mock_git_manager
        )

@pytest.mark.asyncio
async def test_integrity_behind_remote_warn(mock_config, mock_ui_manager, mock_git_manager):
    mock_git_manager.compare_head_with_remote_tracking.return_value = ("behind", "abc", "def", "success")
    
    is_dev, is_ok = await integrity.perform_startup_integrity_checks(
        mock_config, mock_ui_manager, "/root", mock_git_manager
    )
    
    assert is_ok is True
    calls = [str(call) for call in mock_ui_manager.append_output.call_args_list]
    assert any("behind" in c for c in calls)
