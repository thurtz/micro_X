# Changelog

All notable changes to the **micro_X** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1054] - 2026-03-05
### Changed
- **AI Models:** Updated to use `granite4:7b-a1b-h` for better consistency with the production environment.
- **Version:** Bumped application version to `0.0.1054`.

## [0.0.1053] - 2026-03-04
### Changed
- **Refactoring:** Refactored `utils/clone.py` to use `git worktree` instead of `shutil.copytree`. This transition provides full Git integration for clones, allowing for branch-based development and easier merging.
### Added
- **Testing:** Updated `tests/test_clone_utility.py` to cover the new `git worktree` implementation and added robust functional tests.

## [0.0.1052] - 2026-02-27
### Added
- **Testing:** Improved test coverage for `modules/git_context_manager.py` (reached 93%), `utils/alias.py` (reached 94%), and `utils/version_sync.py` (reached 97%), adding robust tests for edge cases, error handling, and CLI execution paths.
...
