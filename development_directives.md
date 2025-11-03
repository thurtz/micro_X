# micro_X Project Development Directives

This file contains the rules and guidelines for the Gemini AI assistant when working on the micro_X project.

## 1. Branch Roles and Modification Rules

- **main branch (`~/micro_X/`)**: This is the stable, production-level branch. It should only be used as a reference for the current stable baseline. **DO NOT MODIFY this branch.** The `development_directives.md` file in this branch is a reference and should not be modified directly. Changes should be merged from the `testing` branch.

- **testing branch (`~/micro_X/micro_X-testing/`)**: This branch is for release candidates and pre-production testing. It should only be used as a reference for the current testing baseline. **DO NOT MODIFY this branch.** The `development_directives.md` file in this branch is a reference and should not be modified directly. Changes should be merged from the `dev` branch.

- **dev branch (`~/micro_X/micro_X-dev/`)**: This is the primary development branch. **All code modifications must be made in this branch.** The `development_directives.md` file is actively maintained in this branch. Ask for confirmation before moving from one coding task to another when there is a list of bugs or tasks to be worked on.

## 2. Workspace Structure

- The primary VS Code workspace is configured to have its root at the `micro_X-dev` directory.
- While the workspace is focused on the `dev` branch, I must remain aware of the other two branches for context and comparison.

## 3. Committing Changes

- When committing changes using the `run_shell_command` tool, use the `-m` flag for each line of the commit message. This avoids complex shell escaping issues.
- Example: `git commit -m "feat: Add new feature" -m "Detailed description of the feature."`
- Files listed in the `.gitignore` file are not tracked by Git and therefore cannot be committed. Do not attempt to commit these files.

## 4. Dependency Management with Poetry

- **Primary Tool**: All Python dependencies for the `micro_X` project must be managed exclusively through Poetry. The legacy `requirements.txt` files are deprecated and should not be used.

- **Adding Dependencies**:
    - To add a new **main (production)** dependency, use the command:
        ```bash
        poetry add <package-name>
        ```
    - To add a new **development** dependency (e.g., for testing, linting, or documentation), you must add it to the `dev` group:
        ```bash
        poetry add --group dev <package-name>
        ```

- **The Lock File**: The `poetry.lock` file, which ensures deterministic and reproducible builds, is a critical project file. It **must** be committed to the repository every time you add, update, or remove a dependency.

- **Installation**: To install or update the project environment according to the `poetry.lock` file, simply run:
    ```bash
    poetry install
    ```

- **Running Commands**: To run a command within the Poetry-managed virtual environment, use `poetry run`. For example:
    ```bash
    poetry run python main.py
    poetry run pytest
    ```
    Alternatively, you can activate the virtual environment directly with `poetry shell`.

## 5. Utility Script Conventions

When creating a new utility script in the `utils/` directory, it must adhere to the following dual-component help system:

1.  **`HELP_TEXT` Constant**: The script MUST contain a top-level string constant named `HELP_TEXT`. This constant is used by the main `/help <utility_name>` command to display a summary of the utility. The help system parses the file and extracts this constant directly; it does not run the script.

2.  **`argparse` Implementation**: The script SHOULD also use the `argparse` module to handle its own command-line arguments, including its own `--help` flag. This allows the utility to be run with complex arguments and to provide detailed help for its own functionality (e.g., `/utils <script_name> --help`).

## 6. Adding New Intents

Adding a new natural language intent is a two-step process:

1.  **Define the Intent**: In `config/intents.json`, add a new key for your intent name (e.g., `"show_weather"`). The value should be an array of strings containing all the phrases a user might type to express this intent (e.g., `["what is the weather", "show weather"]`).

2.  **Map the Intent**: In `modules/shell_engine.py`, add a new entry to the `INTENT_COMMAND_MAP` dictionary. This entry maps the intent name from step 1 to the exact command that should be executed (e.g., `"show_weather": ("/utils get_weather --now", False)`).

## 7. Setup Script Conventions

When creating or modifying OS-specific setup scripts in the `setup_scripts/` directory, the following conventions apply:

- **Baseline Reference**: The `setup_micro_X_mint.sh` script is considered the baseline or "gold standard". New scripts for other operating systems should follow its structure, verbosity, and error-handling logic as closely as possible.

- **Goal**: The objective is to provide a fully automated setup experience where possible. When full automation is not feasible (e.g., for Ollama on certain OSes), the script should provide clear, step-by-step manual instructions for the user.