# micro_X Project TODO List

## Completed (v0.0.1057)
- [x] Update `development_directives.md` with refined workflows.
- [x] Update `micro_X-A_Technical_Whitepaper.md` to reflect agentic architecture.
- [x] Update `CHANGELOG.md` and sync version to `0.0.1057`.
- [x] Robust `utils/clone.py` fixes (git worktree prune, orphaned branch reuse).

## Current Tasks (v0.0.1058)
- [x] Documentation Audit:
    - [x] Review `docs/source/user_guide/` for outdated setup/cloning instructions (transition from shutil to worktree).
    - [x] Update README.md if any quick-start instructions are stale.
- [ ] Performance Optimization:
    - [x] (Investigated) Embedding regeneration issue.
    - [ ] Implement a persistent cache for intent embeddings in `EmbeddingManager` to improve startup time.
- [ ] Hardening:
    - [x] (Verified) `ShellEngine` uses unique tempfiles via `NamedTemporaryFile`.
    - [ ] Improve observability in `lc_agent.py` by logging node-level input/outputs and path decisions.

    - [ ] Standardize UI state resets in `ShellEngine` using a centralized 'UI Guard' or decorator pattern for async methods.
- [ ] Feature Parity:
    - [ ] Audit `textual_ui_manager.py` and `curses_ui_manager.py` to ensure they support recent confirmation and categorization flows.

## Technical Debt
- [ ] **Agentic Tools:** Expand `router_agent.py` toolset to include safe git operations (status, commit) and interactive config management.
- [ ] **ShellEngine:** Harden command escaping logic in `process_command` to handle complex nested quotes.
- [ ] **GitContextManager:** Refine timeout logic and provide more granular error reporting for network-related failures.

## Future Ideas
- [ ] **Configuration Migration:** Transition from JSON to TOML or JSONC to allow for inline documentation of settings.
- [ ] **Dependency Injection:** Refactor `main.py` to use a formal DI pattern for manager initialization.
- [ ] **Sandboxing:** Investigate lightweight containerization or restricted shells for executing AI-generated commands.
