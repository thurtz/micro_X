# modules/ai_interpreter.py

def interpret_human_input(human_input):
    """Simulates AI interpretation of human input to Linux commands."""
    human_input_lower = human_input.lower()
    if "list files" in human_input_lower:
        return "ls -l\n"
    elif "current directory" in human_input_lower:
        return "pwd\n"
    else:
        return f"echo 'AI could not interpret: {human_input}'\n"