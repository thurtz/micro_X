# modules/git_context_manager.py

import asyncio
import subprocess
import shutil
import os
import logging
from typing import Optional, Tuple, List
import httpx
import aiohttp

logger = logging.getLogger(__name__)

# Default timeout for git fetch operations (in seconds)
DEFAULT_GIT_FETCH_TIMEOUT = 10

# Enhanced: Use constants for fetch status results for clarity and consistency.
FETCH_SUCCESS = "success"
FETCH_TIMEOUT = "timeout"
FETCH_OFFLINE = "offline_or_unreachable"
FETCH_ERROR = "other_error"
FETCH_NOT_A_REPO = "not_a_repo"


class GitContextManager:
    """Manages interactions with the Git repository for startup integrity checks
    and gathering context about the project's state (branch, commit).
    """

    def __init__(self, project_root: Optional[str] = None, fetch_timeout: int = DEFAULT_GIT_FETCH_TIMEOUT):
        """Initializes the GitContextManager.

        Args:
            project_root: The root directory of the project. If None,
                uses the current working directory.
            fetch_timeout: Timeout in seconds for git fetch operations.
        """
        self.project_root = os.path.abspath(project_root) if project_root else os.getcwd()
        self.fetch_timeout = fetch_timeout
        self._git_executable_path: Optional[str] = None
        self._is_git_repo: Optional[bool] = None # Cache if it's a git repo
        self._is_git_available_cached: Optional[bool] = None # Cache if git command is available

        logger.info(f"GitContextManager initialized for project root: {self.project_root}")

    async def _run_git_command(self, command_args: List[str], timeout: Optional[int] = None) -> Tuple[bool, str, str]:
        """Runs a git command and returns its status, stdout, and stderr."""
        if not await self.is_git_available(): # Check relies on cached value after first call
            return False, "", "Git executable not found."

        full_command_str = f"git {' '.join(command_args)}"
        logger.debug(f"Executing Git command: '{full_command_str}' in '{self.project_root}' with timeout {timeout}s")
        try:
            process = await asyncio.to_thread(
                subprocess.run,
                [self._git_executable_path] + command_args,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=False, 
                timeout=timeout,
                errors='replace' 
            )
            if process.returncode == 0:
                logger.debug(f"Git command '{full_command_str}' succeeded. Stdout: {process.stdout.strip()}")
                return True, process.stdout.strip(), process.stderr.strip()
            else:
                logger.warning(f"Git command '{full_command_str}' failed with RC {process.returncode}. Stderr: {process.stderr.strip()}, Stdout: {process.stdout.strip()}")
                return False, process.stdout.strip(), process.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"Git command '{full_command_str}' timed out after {timeout} seconds.")
            return False, "", f"Command timed out after {timeout} seconds."
        except FileNotFoundError:
            logger.error(f"Git executable not found at '{self._git_executable_path}' during command execution.")
            self._is_git_available_cached = False 
            return False, "", "Git executable not found."
        except Exception as e:
            logger.error(f"Unexpected error running git command '{full_command_str}': {e}", exc_info=True)
            return False, "", str(e)

    async def is_git_available(self) -> bool:
        """Checks if the 'git' executable is available in the system's PATH."""
        if self._is_git_available_cached is None:
            self._git_executable_path = shutil.which("git")
            if not self._git_executable_path:
                logger.error("Git executable ('git') not found in system PATH.")
                self._is_git_available_cached = False
            else:
                logger.info(f"Git executable found at: {self._git_executable_path}")
                self._is_git_available_cached = True
        return self._is_git_available_cached

    async def is_repository(self) -> bool:
        """Checks if the project_root is a valid Git repository."""
        if not await self.is_git_available():
            self._is_git_repo = False 
            return False

        if self._is_git_repo is None:
            git_dir = os.path.join(self.project_root, ".git")
            if os.path.isdir(git_dir):
                success, _, _ = await self._run_git_command(["rev-parse", "--is-inside-work-tree"])
                self._is_git_repo = success
            else:
                self._is_git_repo = False

            if not self._is_git_repo:
                logger.warning(f"Path '{self.project_root}' does not appear to be a git repository.")
        return self._is_git_repo

    async def get_current_branch(self) -> Optional[str]:
        """Gets the current active branch name (e.g., "main", "dev").

        Returns:
            'HEAD' for a detached HEAD state.
        """
        if not await self.is_repository():
            return None
        success, branch_name, stderr = await self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        if success:
            return branch_name
        else:
            logger.error(f"Could not get current branch: {stderr}")
            return None

    async def get_head_commit_hash(self) -> Optional[str]:
        """Gets the commit hash of the current HEAD."""
        if not await self.is_repository():
            return None
        success, commit_hash, stderr = await self._run_git_command(["rev-parse", "HEAD"])
        return commit_hash if success else None

    async def is_working_directory_clean(self) -> bool:
        """Checks for uncommitted changes or untracked files."""
        if not await self.is_repository():
            return False 

        success, porcelain_output, stderr = await self._run_git_command(["status", "--porcelain"])
        if not success:
            logger.warning(f"Failed to get working directory status: {stderr}")
            return False 

        is_clean = not bool(porcelain_output)
        logger.debug(f"Working directory clean status: {is_clean}. Porcelain output: '{porcelain_output}'")
        return is_clean


    async def fetch_remote_branch(self, branch_name: str, remote_name: str = "origin") -> str:
        """Fetches updates for a specific branch from the specified remote.

        Uses the configured fetch_timeout.

        Returns:
            A status string from predefined constants.
        """
        if not await self.is_repository():
            return FETCH_NOT_A_REPO
        
        logger.info(f"Attempting to fetch '{branch_name}' from remote '{remote_name}' with timeout {self.fetch_timeout}s...")
        success, stdout, stderr = await self._run_git_command(
            ["fetch", remote_name, branch_name],
            timeout=self.fetch_timeout
        )

        if success:
            logger.info(f"Fetch for '{remote_name}/{branch_name}' completed. Stdout: {stdout}, Stderr: {stderr}")
            return FETCH_SUCCESS
        else:
            stderr_lower = stderr.lower()
            if "command timed out" in stderr_lower:
                return FETCH_TIMEOUT
            elif any(s in stderr_lower for s in ["could not resolve hostname", "name or service not known", "network is unreachable", "connection refused"]):
                logger.warning(f"Fetch for '{remote_name}/{branch_name}' failed: Host unreachable or offline. Stderr: {stderr}")
                return FETCH_OFFLINE
            else:
                logger.warning(f"Fetch for '{remote_name}/{branch_name}' failed with other error. Stderr: {stderr}")
                return FETCH_ERROR

    async def get_remote_tracking_branch_hash(self, branch_name: str, remote_name: str = "origin") -> Optional[str]:
        """Gets the commit hash of the remote-tracking branch (e.g., origin/main).
        
        This relies on the local cache of the remote state.
        """
        if not await self.is_repository():
            return None
        remote_branch_ref = f"refs/remotes/{remote_name}/{branch_name}"
        success, commit_hash, stderr = await self._run_git_command(["rev-parse", remote_branch_ref])
        if not success:
            logger.warning(f"Could not get commit hash for remote tracking branch '{remote_branch_ref}': {stderr}")
            return None
        return commit_hash

    async def compare_head_with_remote_tracking(self, branch_name: str, remote_name: str = "origin") -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """Compares HEAD with its remote-tracking branch, attempting to fetch first.

        Args:
            branch_name: The name of the local branch.
            remote_name: The name of the remote.

        Returns:
            A tuple containing (comparison_status, local_hash, remote_hash, 
            fetch_attempt_status). Comparison Status can be: "synced", "ahead",
            "behind", "diverged", "synced_local_cache", "ahead_local_cache", 
            "behind_local_cache", "diverged_local_cache", "no_upstream", 
            "no_upstream_info_locally", "error". Fetch Status can be one of the
            FETCH_* constants.
        """
        if not await self.is_repository():
            return "error", None, None, FETCH_NOT_A_REPO

        fetch_status = await self.fetch_remote_branch(branch_name, remote_name)
        
        local_hash = await self.get_head_commit_hash()
        if not local_hash:
            return "error", None, None, fetch_status # Error getting local hash

        remote_hash = await self.get_remote_tracking_branch_hash(branch_name, remote_name)

        comparison_prefix = ""
        if fetch_status != FETCH_SUCCESS:
            comparison_prefix = "_local_cache" 
            if not remote_hash:
                 logger.info(f"Branch '{branch_name}' has no remote tracking info locally after fetch issue (status: {fetch_status}).")
                 return "no_upstream_info_locally", local_hash, None, fetch_status


        if not remote_hash:
            success_upstream_ref, _, _ = await self._run_git_command(
                ["rev-parse", "--symbolic-full-name", f"{branch_name}@{{upstream}}"]
            )
            if not success_upstream_ref:
                 logger.info(f"Branch '{branch_name}' does not have a configured upstream.")
                 return "no_upstream", local_hash, None, fetch_status
            return "error", local_hash, None, fetch_status

        if local_hash == remote_hash:
            return f"synced{comparison_prefix}", local_hash, remote_hash, fetch_status

        is_local_ancestor_of_remote, _, _ = await self._run_git_command(["merge-base", "--is-ancestor", local_hash, remote_hash])
        if is_local_ancestor_of_remote:
            return f"behind{comparison_prefix}", local_hash, remote_hash, fetch_status

        is_remote_ancestor_of_local, _, _ = await self._run_git_command(["merge-base", "--is-ancestor", remote_hash, local_hash])
        if is_remote_ancestor_of_local:
            return f"ahead{comparison_prefix}", local_hash, remote_hash, fetch_status

        return f"diverged{comparison_prefix}", local_hash, remote_hash, fetch_status

    async def get_and_post_git_status(self):
        """Gathers git status and posts it to the MCP server."""
        if not await self.is_repository():
            return

        branch = await self.get_current_branch()
        commit = await self.get_head_commit_hash()
        is_clean = await self.is_working_directory_clean()
        comp_status, local_h, remote_h, fetch_s = await self.compare_head_with_remote_tracking(branch)

        git_status = {
            "branch": branch,
            "commit": commit,
            "is_clean": is_clean,
            "comparison_status": comp_status,
            "local_hash": local_h,
            "remote_hash": remote_h,
            "fetch_status": fetch_s
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post("http://127.0.0.1:8123/context/git_status", json={"status": git_status})
        except httpx.RequestError as e:
            logger.warning(f"Could not post git status to MCP server: {e}")

    async def verify_commit_signature(self, commit_hash: str) -> Tuple[bool, str]:
        logger.warning("GPG commit signature verification is not yet implemented.")
        return False, "Not implemented"

    async def verify_tag_signature(self, tag_name: str) -> Tuple[bool, str]:
        logger.warning("GPG tag signature verification is not yet implemented.")
        return False, "Not implemented"

async def _main_test():
    """Internal test function for direct execution of this module."""
    print("Testing GitContextManager...")
    project_root_for_test = "."
    try:
        if not os.path.isdir(os.path.join(project_root_for_test, ".git")):
            if os.path.isdir(os.path.join(os.path.dirname(os.getcwd()), ".git")):
                 project_root_for_test = os.path.dirname(os.getcwd())
            else:
                print(f"Warning: Testing with current directory '{os.getcwd()}' as project root. Ensure it's a git repo.")
    except Exception:
        pass

    gcm = GitContextManager(project_root=project_root_for_test)

    if await gcm.is_git_available():
        print(f"Git is available: {gcm._git_executable_path}")
        if await gcm.is_repository():
            print(f"Project root '{gcm.project_root}' is a Git repository.")
            branch = await gcm.get_current_branch()
            print(f"Current branch: {branch}")
            commit = await gcm.get_head_commit_hash()
            print(f"HEAD commit: {commit}")
            is_clean = await gcm.is_working_directory_clean()
            print(f"Is working directory clean? {is_clean}")
            if not is_clean:
                status_porcelain_tuple = await gcm._run_git_command(["status", "--porcelain"])
                print(f"  Porcelain status: \n{status_porcelain_tuple[1]}")

            if branch and branch != "HEAD":
                print(f"\nComparing branch '{branch}' with remote 'origin'...")
                comp_status, local_h, remote_h, fetch_s = await gcm.compare_head_with_remote_tracking(branch)
                print(f"Comparison with remote for '{branch}': {comp_status} (Fetch: {fetch_s})")
                print(f"  Local HEAD: {local_h}")
                print(f"  Remote '{branch}': {remote_h}")
            else:
                print(f"Skipping remote comparison (branch: {branch})")
        else:
            print(f"Project root '{gcm.project_root}' is NOT a Git repository.")
    else:
        print("Git is not available on this system.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("Running GitContextManager direct test...")
    try:
        asyncio.run(_main_test())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
    except Exception as e:
        print(f"Error during test: {e}")
        logger.error("Error during direct test", exc_info=True)