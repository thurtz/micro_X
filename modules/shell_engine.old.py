# modules/shell_engine.py
import asyncio
import os
import shlex
import subprocess
import uuid
import re
import logging

# Imports from other project modules will be added as needed.
# For now, we might need ui_manager for append_output in sanitize_and_validate
# from .ui_manager import UIManager # This will be an instance passed in

logger = logging.getLogger(__name__)

class ShellEngine:
    def __init__(self, config, ui_manager, category_manager_module=None, ai_handler_module=None, main_module_globals=None):
        """
        Initializes the ShellEngine.

        Args:
            config (dict): The application configuration.
            ui_manager (UIManager): An instance of the UIManager.
            category_manager_module: Reference to the category_manager module or relevant functions.
            ai_handler_module: Reference to the ai_handler module or relevant functions.
            main_module_globals (dict, optional): A dictionary for accessing specific globals from main.py
                                                 if direct passing is complex (e.g., for callbacks like
                                                 normal_input_accept_handler, restore_normal_input_handler).
                                                 Ideally, these are passed more directly or handled via UIManager.
        """
        self.config = config
        self.ui_manager = ui_manager
        self.category_manager_module = category_manager_module # Store for later use
        self.ai_handler_module = ai_handler_module # Store for later use
        self.main_module_globals = main_module_globals if main_module_globals else {}

        self.current_directory = os.getcwd()
        # Other state attributes will be added as functions are moved.
        # For example, references to specific functions from category_manager or ai_handler
        # if not passing the whole module.

        logger.info("ShellEngine initialized.")

    def expand_shell_variables(self, command_string: str) -> str:
        """
        Expands shell variables like $PWD, ${PWD}, and others in a command string.
        Custom handling for $PWD and ${PWD} to use the engine's current_directory.

        Args:
            command_string (str): The command string with potential shell variables.

        Returns:
            str: The command string with variables expanded.
        """
        # Use a unique placeholder for PWD to avoid conflicts with other variables
        # that might be legitimately named PWD (e.g. in a script being analyzed).
        pwd_placeholder = f"__MICRO_X_PWD_PLACEHOLDER_{uuid.uuid4().hex}__"

        # Replace $PWD (not followed by other valid variable characters) and ${PWD} with the placeholder
        temp_command_string = re.sub(r'\$PWD(?![a-zA-Z0-9_])', pwd_placeholder, command_string)
        temp_command_string = re.sub(r'\$\{PWD\}', pwd_placeholder, temp_command_string)

        # Expand other environment variables using os.path.expandvars
        # This will not expand the placeholder as it's not a valid env var format
        expanded_string = os.path.expandvars(temp_command_string)

        # Replace the placeholder with the actual current working directory
        # Use self.current_directory which is managed by the ShellEngine
        expanded_string = expanded_string.replace(pwd_placeholder, self.current_directory)

        if command_string != expanded_string:
            logger.debug(f"Expanded shell variables: '{command_string}' -> '{expanded_string}' (PWD: '{self.current_directory}')")
        return expanded_string

    def sanitize_and_validate(self, command: str, original_input_for_log: str) -> str | None:
        """
        Performs basic sanitization and validation of a command string.
        Blocks known dangerous patterns.

        Args:
            command (str): The command string to sanitize.
            original_input_for_log (str): The original user input, for logging purposes.

        Returns:
            str | None: The sanitized command string, or None if blocked.
        """
        # append_output_func is now accessed via self.ui_manager
        # append_output_func = self.ui_manager.append_output # Direct call below

        # List of regex patterns for potentially dangerous commands.
        # - rm -rf / (and similar forceful root deletions)
        # - mkfs (formatting drives)
        # - dd if=/dev/random or /dev/zero to a block device (overwriting drives)
        # - shutdown, reboot, halt, poweroff (system control)
        # - Redirection to /dev/sdX (direct disk write)
        # - Fork bombs like :(){:|:&};:
        # - Piping downloaded content directly to a shell
        dangerous_patterns = [
            r'\brm\s+(-[a-zA-Z0-9]*f[a-zA-Z0-9]*|-f[a-zA-Z0-9]*)\s+/\S*',  # rm -rf / or similar
            r'\bmkfs\b',  # mkfs.*
            r'\bdd\b\s+if=/dev/random', # dd if=/dev/random of=/dev/sdX
            r'\bdd\b\s+if=/dev/zero',   # dd if=/dev/zero of=/dev/sdX
            r'\b(shutdown|reboot|halt|poweroff)\b', # System shutdown commands
            r'>\s*/dev/sd[a-z]+', # Redirect output to a raw disk device
            r':\(\)\{:\|:&};:',  # Fork bomb
            r'\b(wget|curl)\s+.*\s*\|\s*(sh|bash|python|perl)\b' # Piping remote content to shell
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                logger.warning(f"DANGEROUS command blocked (matched pattern '{pattern}'): '{command}' (original input: '{original_input_for_log}')")
                self.ui_manager.append_output(f"🛡️ Command blocked for security: {command}", style_class='security-critical')
                return None
        return command

    # Other methods like process_command, execute_shell_command, etc., will be added here.