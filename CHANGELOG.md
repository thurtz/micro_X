# Changelog

All notable changes to the **micro_X** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1038] - 2026-01-26
### Added
- **Testing:** Added new test suites: `tests/test_utils_knowledge.py` and `tests/test_utils_update.py`.
- **Testing:** Overall test count increased to 247, adding coverage for the knowledge base CLI and the system update utility.

## [0.0.1037] - 2026-01-26
### Added
- **Testing:** Added new test suites: `tests/test_utils_dev.py`, `tests/test_utils_help.py`, and `tests/test_utils_list_scripts.py`.
- **Testing:** Expanded test count to 237, solidifying the reliability of the development workflow tools and the help system.

## [0.0.1036] - 2026-01-25
### Added
- **Testing:** Added new test suites: `tests/test_utils_history.py`, `tests/test_utils_alias.py`, and `tests/test_query_engine.py`.
- **Testing:** Overall test count increased to 220, achieving high coverage for utility scripts and the RAG query engine.

## [0.0.1035] - 2026-01-25
### Added
- **Testing:** Added `tests/test_textual_ui_manager.py` to verify the adapter logic between the core shell engine and the Textual UI backend.
- **Testing:** Overall test count increased to 204, further ensuring system stability across UI transitions.

## [0.0.1034] - 2026-01-25
### Added
- **Clone Utility:** Added a `--bump` flag to the `/clone` utility (`utils/clone.py`). This allows developers to automatically name new clones by incrementing the project's current patch version (e.g., `clone_v0.0.1035`), streamlining the release workflow.

## [0.0.1033] - 2026-01-25
### Added
- **Testing:** Added new test suites: `tests/test_rag_manager.py` and `tests/test_output_analyzer.py`.
- **Testing:** Significantly expanded `tests/test_category_manager.py` to cover the command subsystem (`/command` parsing), listing, and removal logic.
- **Testing:** Overall test count increased to 186, solidifying core system reliability.

## [0.0.1032] - 2026-01-25
### Added
- **Testing:** Added comprehensive unit tests for `modules/router_agent.py`, `modules/router_tools.py`, and `modules/ollama_manager.py`, significantly improving test coverage for core AI routing and service management logic.

## [0.0.1031] - 2026-01-25
### Fixed
- **AI Agent:** Fixed a `GraphRecursionError` in `lc_agent.py` by implementing proper routing termination when the secondary translator fails to produce a command.
### Added
- **Testing:** Expanded test suite with `tests/test_ai_handler.py` and `tests/test_lc_explainer.py` to cover AI command generation and explanation workflows.

## [0.0.1030] - 2026-01-23
### Fixed
- **Utility:** Fixed a `TypeError` in `utils/ollama_cli.py` where `load_configuration_early()` was called with missing arguments. Removed the redundant call as configuration is handled during module import.

## [0.0.1029] - 2026-01-19
### Refactored
- **Code Polish:** Externalized user-facing messages and prompts from `ShellEngine` into a centralized `modules/messages.py` file to improve maintainability and consistency.

## [0.0.1028] - 2026-01-16
### Changed
- **UX:** Removed the automatic 'quiet' verbosity override for protected branches (`main`, `testing`). Startup banners and status checks now appear by default on all branches.
- **UX:** Execution-time informational logs (alias expansion, tmux launch notifications) now require the `verbosity_level` to be set to `verbose` to keep the default shell experience clean.
### Fixed
- Fixed a bug where `/translate` commands were sometimes misinterpreted as help requests by the intent classifier. Prioritized explicit command handling over fuzzy intent matching.

## [0.0.1027] - 2026-01-16
### Changed
- **Workflow:** Updated `development_directives.md` to explicitly include changelog maintenance in the versioning workflow.
- **Dev Utilities:** Enhanced `/dev --update-docs` to automatically sync the root `CHANGELOG.md` into the documentation source before building.

## [0.0.1026] - 2026-01-16
### Added
- Integrated this `CHANGELOG.md` into the official Sphinx documentation.

## [0.0.1025] - 2026-01-16
### Added
- Created this `CHANGELOG.md` to track project history.

## [0.0.1024] - 2026-01-16
### Fixed
- Fixed an issue where known commands prefixed with `!` (e.g., `!pwd`) were incorrectly flagged as unknown and forced into categorization.

## [0.0.1023] - 2026-01-16
### Refactored
- **Major Refactor of Startup Logic:** Extracted configuration loading, integrity checks, and API server initialization from `main.py` into a new `modules/startup` package.
- Improved error handling in startup sequence by removing a bare `except:` block.

## [0.0.1022] - 2026-01-15
### Added
- New `/docs --build-kb` command flag to explicitly build and index the documentation knowledge base.
### Changed
- Updated the startup hint message to provide the correct command for building the missing knowledge base.

## [0.0.1021] - 2026-01-15
### Documentation
- Updated `development_directives.md` to formalize the "Clone-Based Development Workflow".
- Synchronized version numbers across all metadata files.

## [0.0.1020] - 2026-01-15
### Documentation
- Updated `README.md` and User Guide to fully document modern Textual UI features, including syntax highlighting, Markdown rendering, and the new interactive top bar.

## [0.0.1019] - 2026-01-14
### Added
- **UI Polish:** Implemented Markdown rendering for the welcome message and execution feedback in the Textual UI.

## [0.0.1018] - 2026-01-13
### Added
- **Syntax Highlighting:** Real-time syntax highlighting for shell commands in the input field.

## [0.0.1017] - 2026-01-13
### Added
- **Compact Top Bar:** New interactive top bar layout with right-aligned "Quit" button.

## [0.0.1016] - 2026-01-12
### Added
- **Spawn New Shell:** Added `Ctrl+T` shortcut to spawn a new raw shell session in a new tmux window.

## [0.0.1015] - 2026-01-12
### Fixed
- Improved "Run Once" behavior to respect known command categories instead of always defaulting to `semi_interactive`.

## [0.0.1014] - 2026-01-11
### Added
- **Run Once:** Implemented "Run Once" execution option in the categorization menu to execute commands immediately without saving them.

## [0.0.1013] - 2026-01-11
### Added
- **Safety UI:** Implemented specific Safety Warning Modal for dangerous commands.
- **Default UI:** Set `textual` as the default UI backend.

## [0.0.1012] - 2026-01-10
### Added
- **Persistent History:** Implemented persistent command history for the Textual UI backend.
