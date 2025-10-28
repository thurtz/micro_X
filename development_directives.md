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

## 4. Utility Script Conventions

When creating a new utility script in the `utils/` directory, it must adhere to the following dual-component help system:

1.  **`HELP_TEXT` Constant**: The script MUST contain a top-level string constant named `HELP_TEXT`. This constant is used by the main `/help <utility_name>` command to display a summary of the utility. The help system parses the file and extracts this constant directly; it does not run the script.

2.  **`argparse` Implementation**: The script SHOULD also use the `argparse` module to handle its own command-line arguments, including its own `--help` flag. This allows the utility to be run with complex arguments and to provide detailed help for its own functionality (e.g., `/utils <script_name> --help`).
