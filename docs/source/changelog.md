# Changelog

All notable changes to the **micro_X** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1060] - 2026-03-09
### Fixed
- **Docker UI Aesthetics:** Updated `Dockerfile` to generate and configure UTF-8 locales and enable TrueColor support, ensuring UI parity between containerized and native execution.
- **Dynamic Container Naming:** Improved `docker-micro_X.sh` to name containers and tag images based on the current Git branch (e.g., `micro_x_dev_timestamp`), providing better clarity across different environments.
- **Script Permissions:** Updated `setup.sh` to explicitly enforce executable permissions on `docker-micro_X.sh` and core project scripts.

## [0.0.1059] - 2026-03-08
### Added
- **Dockerized Distribution:** Introduced a production-ready Docker deployment system.
    - **Self-Contained Image:** A Debian Trixie base with system dependencies, GitHub CLI (`gh`), and pre-configured internal virtual environment.
    - **Host Breakout Mode:** High-power mode using `chroot` to allow the containerized shell to control the host system.
    - **Refined Breakout Logic:** All commands breakout to the host by default, maintaining the correct working directory. Internal micro_X commands stay within the stable container environment.
    - **Manual Breakout:** Use the standard `!` prefix to force any command to execute natively on the host.
    - **AI Connectivity:** Fixed Ollama connectivity issues for containerized environments by respecting host-gateway networking.
### Changed
- **Documentation:** Updated README.md and User Guide to reflect Docker as the recommended installation and usage method.

## [0.0.1058] - 2026-03-07
### Changed
- **Documentation:** Extensively audited the user guide and README.md to ensure all instructions reflect the new `git worktree`-based cloning system. Refined `development_directives.md` to explicitly separate the merge and commit steps for better final verification in the `dev` environment.
- **Project Management:** Refined `TODO.md` based on a deep architectural analysis, identifying key areas for performance optimization and hardening.

## [0.0.1057] - 2026-03-07
### Changed
- **Documentation:** Updated `development_directives.md` to reflect the refined multi-stage development workflow, ensuring `dev` is used as a final verification environment before promotion to `testing`.
- **Whitepaper:** Updated `micro_X-A_Technical_Whitepaper.md` to reflect the new agentic architecture, including LangGraph-based translation and semantic intent classification.
### Added
- **Project Management:** Created a centralized `TODO.md` in the root directory to track development tasks, technical debt, and future ideas.

## [0.0.1056] - 2026-03-07
### Fixed
- **Clone Utility:** Improved `utils/clone.py` to be much more robust against manual directory deletion. 
    - Added automatic `git worktree prune` to clean up metadata.
    - Added detection for existing branches, allowing the utility to reuse and reset orphaned branches (via `git worktree add -B`) that no longer have a directory.
    - Added a safety check to ensure a branch is not already in use by another active worktree.

## [0.0.1055] - 2026-03-06
### Fixed
- **Clone Utility:** Improved `utils/clone.py` to correctly identify the `micro_X-dev` root directory regardless of which branch or clone it is executed from. This ensures that new clones are always sourced from the `dev` branch and created within the `micro_X-dev/clones/` directory as intended.

## [0.0.1054] - 2026-03-05
### Changed
- **AI Models:** Updated to use `granite4:7b-a1b-h` for better consistency with the production environment.
- **Version:** Bumped application version to `0.0.1054`.
### Removed
- **Git Configuration:** Removed `.gitattributes` to resolve persistent line-ending normalization issues and integrity check failures in mixed Windows/WSL environments.

## [0.0.1053] - 2026-03-04
### Changed
- **Refactoring:** Refactored `utils/clone.py` to use `git worktree` instead of `shutil.copytree`. This transition provides full Git integration for clones, allowing for branch-based development and easier merging.
### Added
- **Testing:** Updated `tests/test_clone_utility.py` to cover the new `git worktree` implementation and added robust functional tests.

## [0.0.1052] - 2026-02-27
### Added
- **Testing:** Improved test coverage for `modules/git_context_manager.py` (reached 93%), `utils/alias.py` (reached 94%), and `utils/version_sync.py` (reached 97%), adding robust tests for edge cases, error handling, and CLI execution paths.
...
