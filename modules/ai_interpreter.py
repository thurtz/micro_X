# modules/ai_interpreter.py

import ollama
import os

def interpret_human_input(human_input, master_fd, stdout_fd):
    """Sends human input to Ollama for Linux command translation and executes it."""
    try:
        response = ollama.chat(
            model='llama3.2',  # Or another model you have pulled
            messages=[
                {
                    'role': 'user',
                    'content': f'You are a Linux command interpreter. Translate this human input to a single best matching Linux command: "{human_input}". Only respond with the Linux command.'
                }
            ]
        )
        linux_command = response['message']['content'].strip() + '\n'
        os.write(master_fd, linux_command.encode())
    except ollama.OllamaAPIError as e:
        error_message = f"Error communicating with Ollama (API Error): {e}\n"
        os.write(stdout_fd, error_message.encode())
    except Exception as e:
        error_message = f"Error during Ollama interaction: {e}\n"
        os.write(stdout_fd, error_message.encode())