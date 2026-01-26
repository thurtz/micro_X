# tests/test_output_analyzer.py

import pytest
from modules import output_analyzer

def test_is_tui_like_output_clean():
    """Test that standard text output is NOT flagged as TUI."""
    clean_text = "This is a normal line of text.\nAnother normal line.\nError: something happened."
    assert output_analyzer.is_tui_like_output(clean_text) is False

def test_is_tui_like_output_colored_below_threshold():
    """Test that sparse color codes are NOT flagged as TUI."""
    # We construct a text where:
    # Lines: 4 total. 1 has ANSI. (25% line coverage) -> Below 30% default.
    # Chars: Ensure ANSI chars are < 3% of total.
    
    # 5 chars of ANSI. We need > 166 chars total for < 3%.
    colored_line = "\x1B[31mError\x1B[0m" # 9 ANSI chars approx? \x1B is 1 char. [31m is 4. Total 5. \x1B[0m is 4. Total 9 ANSI chars.
    # Wait, \x1B is 1 char.
    # \x1B [ 3 1 m = 5 chars.
    # \x1B [ 0 m = 4 chars.
    # Total ANSI = 9 chars.
    # Need 9 / total < 0.03 => total > 300 chars.
    
    padding = "a" * 100
    text = (
        f"{padding}\n"
        f"{padding}\n"
        f"{padding}\n"
        f"This line has color: {colored_line}"
    )
    # Lines: 4. ANSI lines: 1. 25%.
    # Chars: ~330. ANSI: 9. ~2.7%.
    
    assert output_analyzer.is_tui_like_output(text) is False

def test_is_tui_like_output_htop_dense():
    """Test that dense TUI output (like htop) IS flagged."""
    htop_like = (
        "\x1B[H\x1B[2J\x1B[1;1HCPU[\x1B[32m|||||     \x1B[0m25%] \x1B[1;20HMem[\x1B[32m||||||||||\x1B[0m50%]\n"
        "\x1B[2;1H\x1B[7m PID USER      PRI  NI  VIRT   RES   SHR S CPU% MEM%   TIME+  Command\x1B[0m\n"
        "\x1B[3;1H 123 root       20   0  1.2G  500M  100M R  12.0  5.0  1:23.45 /usr/bin/someprocess\n"
    )
    assert output_analyzer.is_tui_like_output(htop_like) is True

def test_is_tui_like_output_empty():
    """Test that empty strings are safe."""
    assert output_analyzer.is_tui_like_output("") is False
    assert output_analyzer.is_tui_like_output(None) is False

def test_is_tui_like_output_custom_thresholds():
    """Test that custom thresholds change the sensitivity."""
    # A multi-line string to avoid 100% line coverage trap for single lines
    # 10 lines. 1 has ANSI. 10% line coverage.
    # ANSI chars: 9. Total ~100. ~9%.
    
    lines = ["Normal"] * 9
    lines.append("\x1B[31mColor\x1B[0m")
    text = "\n".join(lines)
    
    # Default line=30%. 10 < 30.
    # Default char=3%. 9 > 3. Returns True by default due to chars.
    
    # Test 1: Relax char threshold to 20%
    assert output_analyzer.is_tui_like_output(text, char_threshold_pct=20.0) is False
    
    # Test 2: Strict line threshold (5%)
    # Even if we relax char threshold, strict line threshold should catch it.
    assert output_analyzer.is_tui_like_output(text, line_threshold_pct=5.0, char_threshold_pct=20.0) is True

def test_is_tui_like_output_line_threshold_isolation():
    """Test the line-based heuristic in isolation."""
    # 2 lines, 1 has ANSI. 50% line coverage.
    text = (
        "Normal line.\n"
        "\x1B[31mColored line.\x1B[0m"
    )
    # Default line threshold is 30.0%. 50% > 30%, so True.
    # We must set char_threshold_pct high to ignore char density
    assert output_analyzer.is_tui_like_output(text, char_threshold_pct=100.0) is True
    
    # If we raise the line threshold to 60%, it should be False.
    assert output_analyzer.is_tui_like_output(text, line_threshold_pct=60.0, char_threshold_pct=100.0) is False
