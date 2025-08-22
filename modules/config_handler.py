# modules/config_handler.py

import os
import sys
import json
import re
import logging
from typing import Any, Dict, Optional

# --- Module-specific logger ---
logger = logging.getLogger(__name__)

def load_jsonc_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Loads a JSON file that may contain single-line (//) and multi-line (/* */) comments.

    Args:
        filepath (str): The full path to the .jsonc or .json file.

    Returns:
        Optional[Dict[str, Any]]: A dictionary with the file's contents,
                                  or None if the file is not found or cannot be parsed.
    """
    if not os.path.exists(filepath):
        logger.info(f"Configuration file not found at: {filepath}")
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # Regular expression to strip comments
        # 1. Matches // to the end of the line
        # 2. Matches /* ... */ across multiple lines (non-greedy)
        comment_pattern = re.compile(r'//.*?$|/\*.*?\*/', re.DOTALL | re.MULTILINE)
        content_without_comments = re.sub(comment_pattern, '', file_content)

        return json.loads(content_without_comments)

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filepath}: {e}", exc_info=True)
        print(f"❌ Error: Could not parse the configuration file at {filepath}. Please check for syntax errors.", file=sys.stderr)
        return None
    except IOError as e:
        logger.error(f"Error reading file {filepath}: {e}", exc_info=True)
        print(f"❌ Error: Could not read the file at {filepath}.", file=sys.stderr)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading {filepath}: {e}", exc_info=True)
        return None

def save_json_file(filepath: str, data: Dict[str, Any]) -> bool:
    """
    Saves a dictionary to a file in standard JSON format.

    Args:
        filepath (str): The full path where the file will be saved.
        data (Dict[str, Any]): The dictionary data to save.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    try:
        # Ensure the directory exists before writing
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        logger.info(f"Successfully saved configuration to {filepath}")
        return True
    except IOError as e:
        logger.error(f"Error saving data to {filepath}: {e}", exc_info=True)
        print(f"❌ Error: Could not write to the file at {filepath}.", file=sys.stderr)
        return False
    except TypeError as e:
        logger.error(f"Data for {filepath} is not serializable: {e}", exc_info=True)
        print(f"❌ Error: The data provided could not be converted to JSON.", file=sys.stderr)
        return False
