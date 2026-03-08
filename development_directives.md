# micro_X Project Development Directives

This file contains the rules and guidelines for the Gemini AI assistant when working on the micro_X project.

## 1. Branch Roles and Modification Rules

- **main branch (`~/micro_X/`)**: This is the stable, production-level branch. It should only be used as a reference for the current stable baseline. **DO NOT MODIFY this branch.** The `development_directives.md` file in this branch is a reference and should not be modified directly. Changes should be merged from the `testing` branch.

- **testing branch (`~/micro_X/micro_X-testing/`)**: This branch is for release candidates and pre-production testing. It should only be used as a reference for the current testing baseline. **DO NOT MODIFY this branch.** The `development_directives.md` file in this branch is a reference and should not be modified directly. Changes should be merged from the `dev` branch.

- **dev branch (`~/micro_X/micro_X-dev/`)**: This is the primary development branch. Code modifications can be made here directly for minor fixes, but **significant changes should use the Clone-Based Workflow (Section 8).** The `development_directives.md` file is actively maintained in this branch.

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

## 5. Adding New Intents

Adding a new natural language intent is a two-step process:

1.  **Define the Intent**: In `config/intents.json`, add a new key for your intent name (e.g., `"show_weather"`). The value should be an array of strings containing all the phrases a user might type to express this intent (e.g., `["what is the weather", "show weather"]`).

2.  **Map the Intent**: In `modules/shell_engine.py`, add a new entry to the `INTENT_COMMAND_MAP` dictionary. This entry maps the intent name from step 1 to the exact command that should be executed (e.g., `"show_weather": ("/utils get_weather --now", False)`).

## 6. Setup Script Conventions

When creating or modifying OS-specific setup scripts in the `setup_scripts/` directory, the following conventions apply:

- **Baseline Reference**: The `setup_micro_X_mint.sh` script is considered the baseline or "gold standard". New scripts for other operating systems should follow its structure, verbosity, and error-handling logic as closely as possible.

- **Goal**: The objective is to provide a fully automated setup experience where possible. When full automation is not feasible (e.g., for Ollama on certain OSes), the script should provide clear, step-by-step manual instructions for the user.

## 7. Versioning and Documentation

Before committing significant changes or releases to the `dev` branch, follow these steps to ensure consistency:

1.  **Update Version (If Applicable)**: If the changes warrant a version bump (patch, minor, or major), update the `application.version` key in `config/default_config.json`.
2.  **Sync Version**: Run `/version_sync` (or `python3 utils/version_sync.py`) to propagate the version number to all metadata files (`micro_X.desktop`, `docs/source/conf.py`, whitepaper).
3.  **Update Changelog**: Add an entry to `CHANGELOG.md` detailing the changes, following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.
4.  **Update Documentation**: Run `/dev --update-docs` (or `python3 utils/dev.py --update-docs`) to rebuild the Sphinx documentation. This ensures the HTML output reflects the latest code, version, and changelog.
5.  **Verify**: Check `git diff` to confirm that version numbers and documentation builds are updated and consistent before staging.

## 8. Clone-Based Development Workflow

For significant features, refactoring, or risky changes, use the following workflow to ensure stability:

1.  **Create a Clone**: Use the `/clone` utility (or `utils/clone.py`) to create an isolated copy of the current environment. 
    *   Example: `/clone --bump` (Auto-names based on version)
    *   *Note*: Clones are created as Git worktrees within the `clones/` directory of the `micro_X-dev` root.
2.  **Develop in Clone**: Make all code changes, configuration updates, and tests *within* the clone directory (e.g., `clones/clone_v0.0.1057/`).
3.  **Test in Clone**: Run the application and unit tests (`pytest`) inside the clone to verify functionality.
    *   Example: `cd clones/clone_v0.0.1057 && ./micro_X.sh`
    *   Example: `cd clones/clone_v0.0.1057 && pytest`
4.  **Sync and Documentation**: Before merging, ensure the following are updated *within the clone*:
    *   Bump version in `config/default_config.json`.
    *   Run `/version_sync` to propagate the version.
    *   Add entry to `CHANGELOG.md`.
    *   Run `/dev --update-docs` to rebuild documentation.
5.  **Merge to Local Dev**: Copy the modified files from the clone back to the `dev` branch root.
    *   *Note*: Use `cp` or similar to move files; ensure you are in the `micro_X-dev` root.
6.  **Verify in Dev**: Perform final tests and manual verification in the local `dev` environment to ensure the merge was successful. **Do not commit yet.**
7.  **Commit and Push**: Once (and only once) you have verified the changes in the local `dev` environment, commit them and push to the remote.
    *   Example: `git commit -m "feat: New feature" && git push origin dev`


## 9. Promotion and Release Workflow (dev -> testing)

After changes have been pushed to `origin/dev` and have undergone additional verification if necessary, they are promoted to the `testing` branch:

1.  **Create Promotion PR**: Use the GitHub CLI (`gh`) to create a pull request from `dev` to `testing`. This allows for a final review of the diff on GitHub.
    *   Example: `gh pr create --base testing --head dev --title "chore: Promote dev to testing (v0.0.1057)" --body "Summary of changes..."`
2.  **Merge PR**: Merge the PR on GitHub to update the remote `testing` branch.
    *   Example: `gh pr merge --merge --delete-branch=false`
3.  **Sync Local Testing**: Switch to the local `micro_X-testing` directory and pull the latest changes to ensure the local testing environment is current.
    *   Example: `cd ../micro_X-testing && git pull origin testing`


