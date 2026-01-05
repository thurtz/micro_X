# utils/test_api.py

import sys
from utils.shared import api_client

HELP_TEXT = "A test utility to demonstrate the micro_X API for interactive input."

def main():
    print("Hello from test_api.py!")
    
    name = api_client.get_input("What is your name? ")
    print(f"Nice to meet you, {name}!")

    age = api_client.get_input(f"How old are you, {name}? ")
    try:
        age_int = int(age)
        print(f"So, you are {age_int} years old.")
    except ValueError:
        print(f"'{age}' doesn't look like a valid age.")

    print("Test API script finished.")

if __name__ == "__main__":
    main()