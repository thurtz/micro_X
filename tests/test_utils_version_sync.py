# tests/test_utils_version_sync.py

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from utils import version_sync

@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock config directory and file
        os.makedirs(os.path.join(tmpdir, "config"))
        config_data = {"application": {"version": "1.2.3"}}
        with open(os.path.join(tmpdir, "config", "default_config.json"), 'w') as f:
            json.dump(config_data, f)
        
        # Create other mock files
        with open(os.path.join(tmpdir, "micro_X.desktop"), 'w') as f:
            f.write("Version=1.0.0\nName=micro_X")
        
        os.makedirs(os.path.join(tmpdir, "docs", "source"), exist_ok=True)
        with open(os.path.join(tmpdir, "docs", "source", "conf.py"), 'w') as f:
            f.write("version = '1.0.0'\nrelease = '1.0.0'")
            
        with open(os.path.join(tmpdir, "micro_X-A_Technical_Whitepaper.md"), 'w') as f:
            f.write("Version: 1.0.0 (Reflecting stability)")
            
        yield tmpdir

def test_load_master_version(temp_project_dir):
    version = version_sync.load_master_version(temp_project_dir)
    assert version == "1.2.3"

def test_load_master_version_missing(temp_project_dir):
    os.remove(os.path.join(temp_project_dir, "config", "default_config.json"))
    version = version_sync.load_master_version(temp_project_dir)
    assert version is None

def test_update_file_success(temp_project_dir):
    filepath = os.path.join(temp_project_dir, "micro_X.desktop")
    pattern = r"Version=[\d\.]+"
    template = "Version={version}"
    
    # Test update
    changed = version_sync.update_file(filepath, pattern, template, "1.2.3")
    assert changed is True
    
    with open(filepath, 'r') as f:
        content = f.read()
    assert "Version=1.2.3" in content

def test_update_file_no_change(temp_project_dir):
    filepath = os.path.join(temp_project_dir, "micro_X.desktop")
    pattern = r"Version=[\d\.]+"
    template = "Version={version}"
    
    # Already has 1.0.0 (from fixture)
    changed = version_sync.update_file(filepath, pattern, template, "1.0.0")
    assert changed is False

def test_update_file_dry_run(temp_project_dir):
    filepath = os.path.join(temp_project_dir, "micro_X.desktop")
    pattern = r"Version=[\d\.]+"
    template = "Version={version}"
    
    changed = version_sync.update_file(filepath, pattern, template, "1.2.3", dry_run=True)
    assert changed is True
    
    with open(filepath, 'r') as f:
        content = f.read()
    assert "Version=1.0.0" in content # Should NOT have changed

@patch("utils.version_sync.get_project_root")
@patch("sys.exit")
def test_main_sync(mock_exit, mock_get_root, temp_project_dir):
    mock_get_root.return_value = temp_project_dir
    
    # Mocking argparse
    with patch("argparse.ArgumentParser.parse_args", return_value=MagicMock(check=False)):
        version_sync.main()
        
    # Verify files were updated
    with open(os.path.join(temp_project_dir, "micro_X.desktop"), 'r') as f:
        assert "Version=1.2.3" in f.read()
    
    with open(os.path.join(temp_project_dir, "docs", "source", "conf.py"), 'r') as f:
        content = f.read()
        assert "version = '1.2.3'" in content
        assert "release = '1.2.3'" in content

    with open(os.path.join(temp_project_dir, "micro_X-A_Technical_Whitepaper.md"), 'r') as f:
        assert "Version: 1.2.3 (Reflecting" in f.read()

@patch("utils.version_sync.get_project_root")
@patch("sys.exit")
def test_main_check_fail(mock_exit, mock_get_root, temp_project_dir):
    mock_get_root.return_value = temp_project_dir
    
    # Mocking argparse with check=True. Files start at 1.0.0, master is 1.2.3.
    with patch("argparse.ArgumentParser.parse_args", return_value=MagicMock(check=True)):
        version_sync.main()
        
    mock_exit.assert_called_with(1)

@patch("utils.version_sync.get_project_root")
@patch("sys.exit")
def test_main_check_pass(mock_exit, mock_get_root, temp_project_dir):
    mock_get_root.return_value = temp_project_dir
    
    # Set files to 1.2.3 first
    version_sync.update_file(os.path.join(temp_project_dir, "micro_X.desktop"), r"Version=[\d\.]+", "Version={version}", "1.2.3")
    version_sync.update_file(os.path.join(temp_project_dir, "docs", "source", "conf.py"), r"version = '[\d\.]+'", "version = '{version}'", "1.2.3")
    version_sync.update_file(os.path.join(temp_project_dir, "docs", "source", "conf.py"), r"release = '[\d\.]+'", "release = '{version}'", "1.2.3")
    version_sync.update_file(os.path.join(temp_project_dir, "micro_X-A_Technical_Whitepaper.md"), r"Version: [\d\.]+ \(Reflecting", "Version: {version} (Reflecting", "1.2.3")

    # Mocking argparse with check=True.
    with patch("argparse.ArgumentParser.parse_args", return_value=MagicMock(check=True)):
        version_sync.main()
        
    mock_exit.assert_called_with(0)
