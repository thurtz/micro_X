"""
This module provides shared utility functions for handling help text
across different modules in the micro_X project.
"""

import os
import ast
import logging

logger = logging.getLogger(__name__)

def get_help_text_from_module(module_path: str) -> str | None:
    """
    Extracts the HELP_TEXT constant from a given Python module file.

    This function reads the source code of a Python file, parses it into an
    Abstract Syntax Tree (AST), and looks for a top-level string variable
    named 'HELP_TEXT'.

    Args:
        module_path: The absolute path to the Python module file.

    Returns:
        The string value of the HELP_TEXT constant if found, otherwise None.
    """
    if not os.path.exists(module_path):
        logger.error(f"Help text module not found at: {module_path}")
        return None

    try:
        with open(module_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        tree = ast.parse(source_code)
        
        for node in tree.body:
            # We are looking for a top-level assignment
            if isinstance(node, ast.Assign):
                # Check if the assignment is to a variable named HELP_TEXT
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'HELP_TEXT':
                        # Check if the value is a string constant
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.s, str):
                            return node.value.s
                        # Handle the case where it might be an f-string (though less likely for static help)
                        elif isinstance(node.value, ast.JoinedStr):
                             # For simplicity, we'll just try to evaluate it. This is a basic implementation.
                             # A more robust solution might be needed if f-strings are complex.
                            try:
                                # This is a limited and potentially unsafe way to handle f-strings.
                                # Given the context of static help text, we assume they are simple.
                                compiled = compile(ast.Expression(node.value), filename='<ast>', mode='eval')
                                return eval(compiled)
                            except Exception as e:
                                logger.error(f"Could not evaluate f-string HELP_TEXT in {module_path}: {e}")
                                return None
        
        logger.warning(f"HELP_TEXT constant not found in {module_path}")
        return None

    except (IOError, SyntaxError, Exception) as e:
        logger.error(f"Failed to read or parse help text from {module_path}: {e}", exc_info=True)
        return None
