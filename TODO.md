# micro_X Project TODO List

## Current Tasks (v0.0.1057)
- [x] Update `development_directives.md` with refined workflows.
- [x] Update `micro_X-A_Technical_Whitepaper.md` to reflect agentic architecture.
- [ ] Update `CHANGELOG.md` and sync version to `0.0.1057`.
- [ ] Review `docs/source/user_guide/` for outdated setup/cloning instructions.

## Technical Debt & Hardening
- [ ] **UI Consistency:** Ensure feature parity and stable state handling across all UI backends (Textual, Curses, Prompt-toolkit).
- [ ] **Agentic Reliability:**
    - [ ] Improve observability/logging for LangGraph nodes in `lc_agent.py`.
    - [ ] Expand tool coverage for `router_agent.py`.
    - [ ] Optimize embedding storage and retrieval in `embedding_manager.py`.
- [ ] **ShellEngine Hardening:**
    - [ ] Implement unique `tempfile` naming to prevent collisions during concurrent commands.
    - [ ] Audit `shlex` usage and command escaping for edge-case vulnerabilities.
    - [ ] Standardize `finally` blocks in async methods to prevent UI hangs on error.
- [ ] **GitContextManager:** Refine timeout logic and provide more granular error reporting for network-related failures.

## Future Ideas
- [ ] **Configuration Migration:** Transition from JSON to TOML or JSONC to allow for inline documentation of settings.
- [ ] **Dependency Injection:** Refactor `main.py` to use a formal DI pattern for manager initialization.
- [ ] **Sandboxing:** Investigate lightweight containerization or restricted shells for executing AI-generated commands.
