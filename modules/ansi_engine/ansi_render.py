# modules/ansi_engine/ansi_render.py

from prompt_toolkit.formatted_text import FormattedText, ANSI
import logging

# Initialize a logger specific to this module
logger = logging.getLogger(__name__)

def format_ansi_text(text_content: str) -> FormattedText:
    """
    Converts a string containing ANSI SGR escape codes into prompt_toolkit's FormattedText.

    Args:
        text_content: The input string, which may contain ANSI escape codes.

    Returns:
        A FormattedText object (which behaves like a list of 
        (style_string, text_fragment) tuples).
        Returns an empty list if the input is None or empty.
        Returns the original text as a single unstyled fragment if an error occurs during parsing.
    """
    if not text_content:
        # Return an empty list, which is a valid FormattedText representation for no text.
        return [] 

    try:
        # The ANSI class from prompt_toolkit handles the parsing and conversion.
        # The returned object is directly usable as FormattedText.
        formatted_text_object = ANSI(text_content)
        
        # Optional: You can log the raw input and the type of the output for debugging if needed.
        # logger.debug(f"Input for ANSI formatting: '{text_content[:100]}...'")
        # logger.debug(f"Output type from ANSI(): {type(formatted_text_object)}")
        # If you need to inspect the list of tuples, you can do:
        # logger.debug(f"Formatted ANSI text structure: {list(formatted_text_object)}")
        
        return formatted_text_object
    except Exception as e:
        # Log the error and return the original text as a single, unstyled fragment.
        # This ensures that if ANSI parsing fails for some reason, 
        # the user still sees the text, albeit without styling.
        logger.error(
            f"Error parsing ANSI content: {e}. "
            f"Falling back to plain text for content: '{text_content[:100]}...'", 
            exc_info=True
        )
        # Return as a list with a single tuple representing unstyled text.
        return [("", text_content)]

if __name__ == '__main__':
    # Example usage for direct testing of this module (optional)
    logging.basicConfig(level=logging.DEBUG) # Setup basic logging for testing
    
    test_strings = [
        "This is plain text.",
        "\x1b[31mThis is red text.\x1b[0m",
        "Normal then \x1b[1;34mbold blue\x1b[0m and normal again.",
        "\x1b[4;32mGreen underlined\x1b[0m",
        "Malformed \x1b[31mRed", # Incomplete sequence
        "",
        None # Test None input
    ]

    for i, s in enumerate(test_strings):
        print(f"\n--- Test Case {i+1} ---")
        print(f"Input String: {repr(s)}")
        formatted_output = format_ansi_text(s)
        print(f"Output Type: {type(formatted_output)}")
        # To see the actual structure prompt_toolkit uses:
        # (The ANSI object is iterable and yields the (style, text) tuples)
        if formatted_output: # Check if not None or empty list
            try:
                print("Formatted Output Structure:")
                for style_str, text_str in formatted_output: # Iterate if it's a list/iterable
                    print(f"  Style: '{style_str}', Text: '{text_str}'")
            except TypeError: # If it's not directly iterable in this way (e.g. if ANSI returns a callable that wasn't called)
                print(f"  Formatted Output (raw): {formatted_output}")
        else:
            print(f"  Formatted Output: {formatted_output}")

