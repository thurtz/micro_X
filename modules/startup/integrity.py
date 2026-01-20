import logging
from typing import Tuple
from modules.git_context_manager import GitContextManager

logger = logging.getLogger(__name__)

class StartupIntegrityError(Exception):
    """Custom exception to signal a fatal integrity check failure during startup."""
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details

async def perform_startup_integrity_checks(
    config,
    ui_manager,
    script_dir,
    git_context_manager: GitContextManager = None
) -> Tuple[bool, bool]:
    """
    Performs Git integrity checks at startup. Returns: (is_developer_mode, integrity_ok)
    """
    is_developer_mode = False
    integrity_ok = True
    integrity_config = config.get("integrity_check", {})
    protected_branches = integrity_config.get("protected_branches", ["main", "testing"])
    developer_branch = integrity_config.get("developer_branch", "dev")
    halt_on_failure = integrity_config.get("halt_on_integrity_failure", True)
    allow_run_if_behind = integrity_config.get("allow_run_if_behind_remote", True)

    git_fetch_timeout_from_config = config.get('timeouts', {}).get('git_fetch_timeout')

    version = config.get("application", {}).get("version", "unknown")
    if config.get("behavior", {}).get("verbosity_level") != "quiet":
        ui_manager.append_output(f"🚀 micro_X Version: {version}", style_class='info')

    # If git_context_manager is not provided, create one
    if git_context_manager is None:
        if git_fetch_timeout_from_config is not None:
            git_context_manager = GitContextManager(project_root=script_dir, fetch_timeout=git_fetch_timeout_from_config)
        else:
            git_context_manager = GitContextManager(project_root=script_dir) # Uses default timeout

    if not await git_context_manager.is_git_available():
        ui_manager.append_output("⚠️ Git command not found. Integrity checks cannot be performed. Assuming developer mode.", style_class='error')
        logger.error("Git command not found. Integrity checks skipped. Defaulting to developer mode.")
        return True, True

    if not await git_context_manager.is_repository():
        ui_manager.append_output(f"⚠️ Project directory '{script_dir}' is not a Git repository. Integrity checks cannot be performed. Assuming developer mode.", style_class='error')
        logger.error(f"Not a Git repository at '{script_dir}'. Integrity checks skipped. Defaulting to developer mode.")
        return True, True

    current_branch = await git_context_manager.get_current_branch()

    # Set verbosity based on branch if not overridden by user
    if config.get("behavior", {}).get("verbosity_level") == "default":
        if current_branch == developer_branch:
            config["behavior"]["verbosity_level"] = "normal"

    head_commit = await git_context_manager.get_head_commit_hash()
    logger.info(f"Detected Git branch: {current_branch}, HEAD: {head_commit}")
    if config.get("behavior", {}).get("verbosity_level") != "quiet":
        ui_manager.append_output(f"ℹ️ Git context: Branch '{current_branch}', Commit '{head_commit[:7] if head_commit else 'N/A'}'", style_class='info')

    if current_branch == developer_branch:
        is_developer_mode = True
        if config.get("behavior", {}).get("verbosity_level") != "quiet":
            ui_manager.append_output(f"✅ Running in Developer Mode (branch: '{developer_branch}'). Integrity checks are informational.", style_class='success')
        logger.info(f"Developer mode enabled: '{developer_branch}' branch checked out.")
    elif current_branch in protected_branches:
        is_developer_mode = False
        if config.get("behavior", {}).get("verbosity_level") != "quiet":
            ui_manager.append_output(f"ℹ️ Running on protected branch '{current_branch}'. Performing integrity checks...", style_class='info')

        is_clean = await git_context_manager.is_working_directory_clean()
        if not is_clean:
            status_output_tuple = await git_context_manager._run_git_command(["status", "--porcelain"])
            status_output_details = status_output_tuple[1] if status_output_tuple[0] else "Could not get detailed status."
            error_msg = f"Integrity Check Failed (Branch: {current_branch}): Uncommitted local changes or untracked files detected."
            detail_msg = f"Git status details:\n{status_output_details}"
            logger.critical(f"{error_msg}\n{detail_msg}")
            if halt_on_failure:
                raise StartupIntegrityError(error_msg, details=detail_msg)
            integrity_ok = False
        else:
            if config.get("behavior", {}).get("verbosity_level") != "quiet":
                ui_manager.append_output(f"✅ Working directory is clean for branch '{current_branch}'.", style_class='info')

        if integrity_ok:
            comparison_status, local_h, remote_h, fetch_status = await git_context_manager.compare_head_with_remote_tracking(current_branch)

            if fetch_status == "success":
                if comparison_status == "synced":
                    if config.get("behavior", {}).get("verbosity_level") != "quiet":
                        ui_manager.append_output(f"✅ Branch '{current_branch}' is synced with 'origin/{current_branch}'.", style_class='success')
                    logger.info(f"Branch '{current_branch}' (Local: {local_h[:7] if local_h else 'N/A'}) is synced with remote (Remote: {remote_h[:7] if remote_h else 'N/A'}).")
                elif comparison_status == "behind" and allow_run_if_behind:
                    warn_msg = f"⚠️ Your local branch '{current_branch}' is behind 'origin/{current_branch}'. New updates are available."
                    suggest_msg = "   Suggestion: Run the '/update' command to get the latest version."
                    ui_manager.append_output(warn_msg, style_class='warning')
                    ui_manager.append_output(suggest_msg, style_class='info')
                    logger.warning(f"{warn_msg} Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}")
                elif comparison_status in ["ahead", "diverged"] or (comparison_status == "behind" and not allow_run_if_behind):
                    status_description = comparison_status
                    if comparison_status == "behind" and not allow_run_if_behind:
                        status_description = "behind (and configuration disallows running)"
                    error_msg = f"Integrity Check Failed (Branch: {current_branch}): Local branch has '{status_description}' from 'origin/{current_branch}'."
                    detail_msg = f"Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}"
                    logger.critical(f"{error_msg} {detail_msg}")
                    if halt_on_failure:
                        raise StartupIntegrityError(error_msg, details=detail_msg)
                    integrity_ok = False
                else:
                    error_msg = f"Integrity Check Failed (Branch: {current_branch}): Cannot reliably compare with remote after successful fetch. Status: {comparison_status}."
                    detail_msg = f"Local: {local_h[:7] if local_h else 'N/A'}, Remote: {remote_h[:7] if remote_h else 'N/A'}"
                    logger.critical(f"{error_msg} {detail_msg}")
                    if halt_on_failure:
                        raise StartupIntegrityError(error_msg, details=detail_msg)
                    integrity_ok = False
            elif fetch_status in ["timeout", "offline_or_unreachable"]:
                ui_manager.append_output(f"⚠️ Could not contact remote for branch '{current_branch}' (Reason: {fetch_status}). Comparing against local cache.", style_class='warning')
                if comparison_status == "synced_local_cache" or comparison_status == "behind_local_cache":
                    ui_manager.append_output(f"ℹ️ Branch '{current_branch}' is consistent with the last known state of 'origin/{current_branch}'. Running in offline-verified mode.", style_class='info')
                elif comparison_status == "ahead_local_cache" or comparison_status == "diverged_local_cache":
                    error_msg = f"Integrity Check Failed (Branch: {current_branch}, Offline): Local branch has unpushed changes or diverged from the last known remote state. Status: {comparison_status}"
                    detail_msg = f"Local: {local_h[:7] if local_h else 'N/A'}, Last Known Remote: {remote_h[:7] if remote_h else 'N/A'}"
                    logger.critical(f"{error_msg} {detail_msg}")
                    if halt_on_failure:
                        raise StartupIntegrityError(error_msg, details=detail_msg)
                    integrity_ok = False
                elif comparison_status == "no_upstream_info_locally":
                    error_msg = f"Integrity Check Failed (Branch: {current_branch}, Offline): No local information about the remote tracking branch. Cannot verify integrity."
                    logger.critical(error_msg)
                    if halt_on_failure:
                        raise StartupIntegrityError(error_msg)
                    integrity_ok = False
                else:
                    error_msg = f"Integrity Check Failed (Branch: {current_branch}, Offline): Error comparing with local cache. Status: {comparison_status}"
                    logger.critical(error_msg)
                    if halt_on_failure:
                        raise StartupIntegrityError(error_msg)
                    integrity_ok = False
            elif fetch_status == "other_error":
                error_msg = f"Integrity Check Failed (Branch: {current_branch}): A non-network error occurred during 'git fetch'."
                logger.critical(f"{error_msg} - Check git fetch logs or permissions.")
                if halt_on_failure:
                    raise StartupIntegrityError(error_msg, details="Check git fetch logs or permissions.")
                integrity_ok = False

        if integrity_ok:
            logger.info(f"Integrity checks completed for branch '{current_branch}'. Final status: OK")
        elif halt_on_failure:
            logger.critical(f"Application integrity compromised on protected branch '{current_branch}'. Halting as per configuration.")
    else:
        is_developer_mode = True
        ui_manager.append_output(f"ℹ️ Running on unrecognized branch/commit '{current_branch}'. Developer mode assumed. Integrity checks informational.", style_class='info')
        logger.info(f"Developer mode assumed for unrecognized branch/commit: '{current_branch}'.")

    return is_developer_mode, integrity_ok
