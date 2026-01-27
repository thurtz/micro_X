# tests/test_startup_config_loader.py

import pytest
import os
import logging
from unittest.mock import MagicMock, patch
from modules.startup import config_loader

def test_merge_configs():
    base = {"a": 1, "b": {"c": 2}}
    override = {"b": {"d": 3}, "e": 4}
    merged = config_loader.merge_configs(base, override)
    assert merged == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
    # Ensure original not modified
    assert base == {"a": 1, "b": {"c": 2}}

@patch("modules.config_handler.load_jsonc_file")
@patch("os.path.join")
def test_load_configuration_early_success_base_only(mock_join, mock_load_jsonc, caplog):
    caplog.set_level(logging.INFO)
    mock_join.side_effect = lambda *args: "/".join(args)
    
    # First call (base): valid dict. Second call (user): None
    mock_load_jsonc.side_effect = [{"base": "config"}, None]
    
    config = config_loader.load_configuration_early("/app", "config")
    
    assert config == {"base": "config"}
    assert "Successfully loaded base configuration" in caplog.text
    assert "No user configuration overrides applied" in caplog.text

@patch("modules.config_handler.load_jsonc_file")
@patch("os.path.join")
def test_load_configuration_early_success_with_user(mock_join, mock_load_jsonc):
    mock_join.side_effect = lambda *args: "/".join(args)
    
    mock_load_jsonc.side_effect = [{"a": 1}, {"a": 2}]
    
    config = config_loader.load_configuration_early("/app", "config")
    
    assert config == {"a": 2} # User override

@patch("modules.config_handler.load_jsonc_file")
@patch("builtins.print")
def test_load_configuration_early_fail_base(mock_print, mock_load_jsonc):
    mock_load_jsonc.return_value = None # Base config fail
    
    with pytest.raises(SystemExit) as e:
        config_loader.load_configuration_early("/app")
    assert e.value.code == 1
    mock_print.assert_called_with("CRITICAL ERROR: Default configuration file not found or failed to parse at '/app/config/default_config.json'. Application cannot start.")
