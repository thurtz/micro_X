# **micro\_X Development and Collaboration Principles**

## **1\. Introduction**

This document establishes a set of guiding principles and rules for the ongoing development and quality hardening of the micro\_X project. These rules apply to all future modifications made in our collaborative sessions and are intended to ensure stability, maintain quality, and align our efforts.

## **2\. Core Philosophy**

1. **Stability and Quality First:** Our primary goal is to enhance the existing codebase. We will prioritize bug fixes, performance improvements, security hardening, and code clarity over the introduction of new features.  
2. **Preservation of User Experience:** Changes should not degrade the user experience. Core interactions and established behaviors are to be maintained unless a change is explicitly agreed upon to improve them.  
3. **Explicitness and Transparency:** All changes, and the reasoning behind them, will be made clear. The project's state and our development process should be easy to understand at all times.

## **3\. Development Rules**

### **A. Feature and Behavior Integrity**

1. **No Feature Removal Without Verification:** Existing features, commands, or significant functionalities will not be removed or fundamentally altered without explicit user confirmation and a clear justification based on the Quality Review or a direct request.  
2. **Preservation of Core UX:** Key user-facing behaviors will be preserved. For example, semi\_interactive commands will continue to launch in a foreground tmux window as per the established design. Any deviation must be a conscious, agreed-upon decision to improve usability.  
3. **Configuration Compatibility:** Changes should, whenever possible, avoid breaking compatibility with existing user configuration files (user\_config.json, user\_command\_categories.json). If a breaking change is necessary, it must be clearly documented.
4. **Preservation of alias usage:** Aliases in end user documentation should be prefered and preserved. For example, \/utils generate\_snapshot commands will continue to be launched via \/snapshot per the established README.md documentation. Any deviation must be a conscious, agreed-upon decision to improve usability.

### **B. Code Quality and Maintenance**

1. **Test-Driven Changes:** All bug fixes must be accompanied by a new or updated test that replicates the bug and confirms the fix. Any new logic added during refactoring must be covered by corresponding unit tests.  
2. **Documentation First:** All significant changes to behavior, architecture, or user-facing features must be documented *before* or *alongside* the code implementation. This includes keeping README.md, the User Guide, and this principles document up-to-date.  
    *   **Building Documentation**: To build the documentation, use the `/dev --update-docs` command. This command ensures that the documentation is always built from the `dev` branch, even if you are currently on a different branch. It executes the build process within the `micro_X-dev` directory.
3. **Adherence to Architecture:** New or modified code must respect the existing modular design of the project. Logic should be placed in the appropriate module (e.g., UI logic in ui\_manager, Git logic in git\_context\_manager). Developing micro_X commands should be done with prioritizing their integration as a utility and an alias rather than hardcoded in the base.

### **C. Collaboration and Process**

1. **Explicit Confirmation for Changes:** I (the AI assistant) will always ask for explicit user confirmation before making changes to the codebase.  
2. **Justification of Changes:** All proposed changes will be accompanied by a clear explanation referencing the Quality Review, a direct user request, or these development principles.  
3. **Comprehensive Change Logging:** All implemented changes will be logged in the docs/micro\_X\_Code\_Quality\_Review\_Accomplishments.md file, providing a clear audit trail of our progress.

### D. Utility Script Development

1.  **Dual-Environment Execution**: Utility scripts in the `utils/` directory should be written to function both within the micro_X shell and as standalone scripts in a standard shell.
2.  **API Client Usage**: To achieve this, scripts can use the `utils.shared.api_client.get_input()` function for interactive prompts. This function automatically detects if the script is running inside micro_X by checking for the `MICROX_API_SOCKET` environment variable.
    *   If the variable is present, it uses the micro_X API to prompt the user.
    *   If the variable is absent, it falls back to using standard input (`sys.stdin`) and `stderr` for prompts, allowing it to run in any standard shell.
3.  **Standalone Execution**: When running a utility script directly from a standard shell, it must be executed as a module to ensure Python's import system can correctly locate other modules within the project (like `api_client`).
    *   **Correct**: `python -m utils.your_script_name`
    *   **Incorrect**: `python utils/your_script_name.py`

## **4\. Review and Amendment**

These principles are a living document. They can be reviewed, discussed, and amended at any time through our dialogue to better suit the project's evolving needs.