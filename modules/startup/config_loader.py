import os
import sys
import logging
import modules.config_handler

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "default_config.json"
USER_CONFIG_FILENAME = "user_config.json"

def merge_configs(base, override):
    """ Helper function to recursively merge dictionaries. """
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_configuration_early(script_dir, config_dir_name="config"):
    """
    Loads configurations from default and user JSONC files early in the startup process.
    """
    default_config_path = os.path.join(script_dir, config_dir_name, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(script_dir, config_dir_name, USER_CONFIG_FILENAME)

    base_config = modules.config_handler.load_jsonc_file(default_config_path)
    if base_config is None:
        error_msg = f"CRITICAL ERROR: Default configuration file not found or failed to parse at '{default_config_path}'. Application cannot start."
        logger.critical(error_msg)
        print(error_msg)
        sys.exit(1)

    logger.info(f"Successfully loaded base configuration from {default_config_path}")
    config = base_config

    user_settings = modules.config_handler.load_jsonc_file(user_config_path)
    if user_settings:
        config = merge_configs(config, user_settings)
        logger.info(f"Loaded and merged user configurations from {user_config_path}")
    else:
        logger.info(f"{user_config_path} not found or is invalid. No user configuration overrides applied.")
    
    return config
