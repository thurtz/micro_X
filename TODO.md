# micro_X Project TODO List

## Completed (v0.0.1057)
- [x] Update `development_directives.md` with refined workflows.
- [x] Update `micro_X-A_Technical_Whitepaper.md` to reflect agentic architecture.
- [x] Update `CHANGELOG.md` and sync version to `0.0.1057`.
- [x] Robust `utils/clone.py` fixes (git worktree prune, orphaned branch reuse).

## Completed (v0.0.1058)
- [x] Documentation Audit:
    - [x] Review `docs/source/user_guide/` for outdated setup/cloning instructions (transition from shutil to worktree).
    - [x] Update README.md if any quick-start instructions are stale.
- [x] Refine `development_directives.md` multi-stage workflow.

## Completed (v0.0.1059)
- [x] Dockerized Distribution:
    - [x] Create `Dockerfile` (Debian Trixie base) with system dependencies and `gh`.
    - [x] Create `docker-micro_X.sh` wrapper with host-path mapping and user identity passthrough.
    - [x] Implement Host Breakout Mode (privileged/chroot) via `!` command prefix.
    - [x] Ensure path alignment between container and host for breakout commands.
    - [x] Fix Ollama AI connectivity for containerized environments.
    - [x] Update `README.md` and User Guide with Docker instructions.
    - [x] Add `tests/test_docker_integration.py` to verify breakout and environment logic.

## Completed (v0.0.1060)
- [x] Docker Refinements:
    - [x] **UI Aesthetics:** Fixed terminal color/encoding in Docker via UTF-8 locales and TrueColor support.
    - [x] **Dynamic Naming:** Updated `docker-micro_X.sh` to name containers and tag images based on current branch.
    - [x] **Permissions:** Enforced executable bit for core scripts in `setup.sh`.

## Current Tasks (v0.0.1061)
- [ ] Docker Hardening:
    - [ ] **Non-Root Execution:** Refactor container to run as current host user while maintaining breakout via passwordless sudo.
- [ ] AI & Reliability:
    - [ ] **Ollama Detection:** Migrate to "API-First" detection (attempt curl/request to version endpoint).
- [ ] Documentation:
    - [ ] Update `README.md` and User Guide to state "Clone First" prerequisite for Docker.

## Performance & Hardening (Carryover)
- [ ] Implement persistent cache for intent embeddings in `EmbeddingManager`.
- [ ] Improve observability in `lc_agent.py` (node-level logging).
- [ ] Standardize UI state resets in `ShellEngine`.

## Technical Debt
- [ ] **Agentic Tools:** Expand `router_agent.py` toolset.
- [ ] **ShellEngine:** Harden command escaping logic.
- [ ] **GitContextManager:** Refine timeout logic.

## Future Ideas
- [ ] **Configuration Migration:** Transition from JSON to TOML or JSONC.
- [ ] **Dependency Injection:** Refactor `main.py`.
