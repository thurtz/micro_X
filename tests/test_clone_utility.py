# tests/test_clone_utility.py

import pytest
import json
from unittest.mock import mock_open, patch
from utils import clone

def test_get_next_version_name_success():
    """Test standard version increment."""
    mock_config = json.dumps({"application": {"version": "0.0.1034"}})
    with patch("builtins.open", mock_open(read_data=mock_config)):
        name = clone.get_next_version_name("/dummy/root")
        assert name == "clone_v0.0.1035"

def test_get_next_version_name_short_version():
    """Test fallback when version string is short."""
    mock_config = json.dumps({"application": {"version": "1.0"}})
    with patch("builtins.open", mock_open(read_data=mock_config)):
        name = clone.get_next_version_name("/dummy/root")
        assert name == "clone_v1.0_next"

def test_get_next_version_name_file_not_found():
    """Test handling of missing config file."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        name = clone.get_next_version_name("/dummy/root")
        assert name is None

def test_get_next_version_name_invalid_json():
    """Test handling of invalid JSON."""
    with patch("builtins.open", mock_open(read_data="{invalid_json")):
        name = clone.get_next_version_name("/dummy/root")
        assert name is None
