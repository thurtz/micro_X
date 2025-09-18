# --- API DOCUMENTATION for modules/output_analyzer.py ---
#
# **Purpose:** Analyzes command output to detect TUI-like content by measuring the
# density of ANSI escape codes. This helps prevent garbled text from being
# printed to the main output area for commands that should be fully interactive.
#
# **Public Functions:**
#
# def is_tui_like_output(text_content: str, line_threshold_pct: float, char_threshold_pct: float) -> bool:
#     """
#     Analyzes text to determine if it's likely TUI-specific output.
#
#     It checks if the percentage of lines containing ANSI codes or the percentage
#     of total characters that are part of ANSI codes exceeds given thresholds.
#
#     Args:
#         text_content (str): The string content captured from a command's output.
#         line_threshold_pct (float): The minimum percentage of lines that must
#                                     contain ANSI codes to be flagged as TUI-like.
#         char_threshold_pct (float): The minimum percentage of total characters
#                                     that must be part of ANSI codes to be flagged.
#
#     Returns:
#         bool: True if the output is determined to be TUI-like, False otherwise.
#     """
#
# **Key Global Constants/Variables:**
#   (None intended for direct external use)
#
# --- END API DOCUMENTATION ---

#!/usr/bin/env python

import re
import logging

# Module-specific logger
# To see these logs when running the main micro_X application,
# the main application's logging configuration would need to allow logs from this logger name.
logger = logging.getLogger(__name__)

# Regex for common ANSI CSI (Control Sequence Introducer) patterns.
# ESC ( \x1B or \033 ) followed by '[' then any number of parameters (digits and semicolons)
# ending with a single letter (e.g., m, K, J, H, A, B, C, D).
# This pattern is a good starting point for detecting screen manipulation codes.
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B\[[0-9;]*[a-zA-Z]')

# Default thresholds for detection. These might require tuning based on testing.
# If these percentages are met or exceeded, the output is considered TUI-like.
DEFAULT_LINE_THRESHOLD_PERCENT = 30.0  # Percentage of lines containing ANSI codes.
DEFAULT_CHAR_THRESHOLD_PERCENT = 3.0   # Percentage of total characters that are part of ANSI codes.

def is_tui_like_output(
    text_content: str,
    line_threshold_pct: float = DEFAULT_LINE_THRESHOLD_PERCENT,
    char_threshold_pct: float = DEFAULT_CHAR_THRESHOLD_PERCENT
) -> bool:
    """Analyzes text to determine if it's likely TUI-specific output.

    It checks if the percentage of lines containing ANSI codes or the percentage
    of total characters that are part of ANSI codes exceeds given thresholds.

    Args:
        text_content: The string content captured from a command's output.
        line_threshold_pct: The minimum percentage of lines that must
            contain ANSI codes to be flagged as TUI-like.
        char_threshold_pct: The minimum percentage of total characters
            that must be part of ANSI codes to be flagged.

    Returns:
        True if the output is determined to be TUI-like, False otherwise.
    """
    if not text_content:
        logger.debug("is_tui_like_output: Received empty content. Returning False.")
        return False

    lines = text_content.splitlines()
    if not lines:
        logger.debug("is_tui_like_output: Content split into zero lines. Returning False.")
        return False

    num_lines = len(lines)
    ansi_lines_count = 0  # Number of lines that contain at least one ANSI sequence
    total_ansi_chars_count = 0  # Total number of characters that are part of ANSI sequences
    total_chars_in_content = len(text_content) # Total characters in the original string

    logger.debug(f"is_tui_like_output: Analyzing {num_lines} lines, {total_chars_in_content} total characters.")

    for line_num, line in enumerate(lines):
        # Find all ANSI sequences in the current line
        found_sequences = ANSI_ESCAPE_PATTERN.findall(line)
        if found_sequences:
            ansi_lines_count += 1
            for seq in found_sequences:
                total_ansi_chars_count += len(seq)
            # Uncomment for very detailed logging of sequences found per line:
            # logger.debug(f"Line {line_num+1}/{num_lines} contains ANSI sequences: {found_sequences}")

    # Heuristic 1: Based on the percentage of lines containing ANSI codes
    if num_lines > 0: # Ensure no division by zero
        percentage_of_ansi_lines = (ansi_lines_count / num_lines) * 100
        logger.debug(
            f"is_tui_like_output: ANSI lines: {ansi_lines_count}/{num_lines} "
            f"({percentage_of_ansi_lines:.2f}%)"
        )
        if percentage_of_ansi_lines >= line_threshold_pct:
            logger.info(
                f"TUI-like output DETECTED based on line threshold: "
                f"{percentage_of_ansi_lines:.2f}% >= {line_threshold_pct:.2f}%"
            )
            return True
    else:
        percentage_of_ansi_lines = 0.0

    # Heuristic 2: Based on the percentage of total characters that are part of ANSI codes
    if total_chars_in_content > 0: # Ensure no division by zero
        percentage_of_ansi_chars = (total_ansi_chars_count / total_chars_in_content) * 100
        logger.debug(
            f"is_tui_like_output: ANSI characters: {total_ansi_chars_count}/{total_chars_in_content} "
            f"({percentage_of_ansi_chars:.2f}%)"
        )
        if percentage_of_ansi_chars >= char_threshold_pct:
            logger.info(
                f"TUI-like output DETECTED based on character threshold: "
                f"{percentage_of_ansi_chars:.2f}% >= {char_threshold_pct:.2f}%"
            )
            return True
    else:
        percentage_of_ansi_chars = 0.0

    logger.debug(
        f"Output NOT considered TUI-like. Line %%: {percentage_of_ansi_lines:.2f}, "
        f"Char %%: {percentage_of_ansi_chars:.2f}"
    )
    return False

# This block allows for direct testing of the module if run as a script.
if __name__ == '__main__':
    # Configure basic logging for direct script execution testing
    # This will show logs from this module (e.g., "output_analyzer")
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # --- Test Cases ---
    sample_clean_output = "This is a normal line of text.\nAnother normal line.\nError: something happened."
    
    sample_colored_output = (
        "\x1B[31mError:\x1B[0m Something went wrong.\n"
        "\x1B[32mSuccess:\x1B[0m Operation completed.\n"
        "This is just a normal line with no color."
    )
    
    # A more realistic, dense TUI-like output snippet
    sample_htop_like_output_dense = (
        "\x1B[H\x1B[2J\x1B[1;1HCPU[\x1B[32m|||||     \x1B[0m25%] \x1B[1;20HMem[\x1B[32m||||||||||\x1B[0m50%]\n"
        "\x1B[2;1H\x1B[7m PID USER      PRI  NI  VIRT   RES   SHR S CPU% MEM%   TIME+  Command\x1B[0m\n"
        "\x1B[3;1H 123 root       20   0  1.2G  500M  100M R  12.0  5.0  1:23.45 /usr/bin/someprocess\n"
        "\x1B[4;1H 456 user       20   0  500M  100M   50M S   2.0  1.0  0:10.00 /usr/bin/another\n"
        "\x1B[5;1H\x1B[KRandom text here to fill space and test non-ANSI parts.\n"
        "\x1B[6;1H\x1B[44mStatus Bar - Press F10 to quit\x1B[49m\x1B[K\n"
        "\x1B[3;30H\x1B[31mAlert!\x1B[0m\n"
    ) * 3 # Repeat to make it more substantial for testing character percentages

    sample_mixed_output_borderline = (
        "Starting process...\n"
        "\x1B[34mINFO:\x1B[0m Process ID 1234 started.\n" # ANSI line
        "Output line 1.\n"
        "\x1B[1A\x1B[KUpdating status: \x1B[32mOK\x1B[0m\n" # ANSI line (cursor up, erase, color)
        "Output line 2.\n"
        "Finalizing...\n"
        "\x1B[31mWARN:\x1B[0m Checksum mismatch on file X.\n" # ANSI line
        "This is a very long line with no ANSI codes at all, just to dilute the character percentage."
        "This is another very long line with no ANSI codes at all, just to dilute the character percentage."
    )

    git_log_colored_example = (
        "\x1b[33mcommit c9b8f7a6d5e4c3b2a1f0e9d8c7b6a5f4d3e2c1b0\x1b[m\x1b[33m (HEAD -> main, origin/main)\x1b[m\n"
        "Author: Test User <test@example.com>\n"
        "Date:   Tue May 14 10:00:00 2024 -0700\n"
        "\n"
        "    Some commit message explaining things\n"
        "\n"
        "\x1b[33mcommit a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0\x1b[m\n"
        "Author: Another User <another@example.com>\n"
        "Date:   Mon May 13 15:30:00 2024 -0700\n"
        "\n"
        "    Previous commit message with details\n"
    )

    # Test cases
    logger.info("--- Testing with clean output ---")
    result_clean = is_tui_like_output(sample_clean_output)
    print(f"Clean output TUI-like: {result_clean} (Expected: False)\n")

    logger.info("--- Testing with standard colored output ---")
    result_colored = is_tui_like_output(sample_colored_output)
    print(f"Colored output TUI-like: {result_colored} (Expected: False with default thresholds)\n")

    logger.info("--- Testing with dense htop-like output ---")
    result_htop = is_tui_like_output(sample_htop_like_output_dense)
    print(f"htop-like output TUI-like: {result_htop} (Expected: True)\n")
    
    logger.info("--- Testing with mixed output (borderline) using default thresholds ---")
    result_mixed_default = is_tui_like_output(sample_mixed_output_borderline)
    print(f"Mixed output (default thresholds) TUI-like: {result_mixed_default} (Expected: depends on defaults, likely False)\n")

    logger.info("--- Testing with mixed output (borderline) using lower thresholds ---")
    result_mixed_lower = is_tui_like_output(sample_mixed_output_borderline, line_threshold_pct=20.0, char_threshold_pct=1.0)
    print(f"Mixed output (lower thresholds) TUI-like: {result_mixed_lower} (Expected: more likely True)\n")

    logger.info("--- Testing with git log (colored) using default thresholds ---")
    result_git_default = is_tui_like_output(git_log_colored_example)
    print(f"Git log (default thresholds) TUI-like: {result_git_default} (Expected: False)\n")

    logger.info("--- Testing with git log (colored) using very sensitive thresholds ---")
    result_git_sensitive = is_tui_like_output(git_log_colored_example, line_threshold_pct=5.0, char_threshold_pct=0.5)
    print(f"Git log (sensitive thresholds) TUI-like: {result_git_sensitive} (Expected: might become True, shows sensitivity)\n")

    logger.info("--- Testing with empty string ---")
    result_empty = is_tui_like_output("")
    print(f"Empty string TUI-like: {result_empty} (Expected: False)\n")

    logger.info("--- Testing with only ANSI codes ---")
    only_ansi = "\x1B[1m\x1B[31m\x1B[4m"
    result_only_ansi = is_tui_like_output(only_ansi)
    print(f"Only ANSI codes TUI-like: {result_only_ansi} (Expected: True)\n")