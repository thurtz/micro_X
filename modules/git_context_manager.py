# modules/git_context_manager.py

import asyncio
import subprocess
import shutil
import os
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# Default timeout for git fetch operations (in seconds)
DEFAULT_GIT_FETCH_TIMEOUT = 10

class GitContextManager:
    """
    Manages interactions with Git for integrity checks and context gathering.
    """

    def __init__(self, project_root: Optional[str] = None, fetch_timeout: int = DEFAULT_GIT_FETCH_TIMEOUT):
        """
        Initializes the GitContextManager.

        Args:
            project_root (Optional[str]): The root directory of the project.
                                          If None, uses the current working directory.
            fetch_timeout (int): Timeout in seconds for git fetch operations.
        """
        self.project_root = os.path.abspath(project_root) if project_root else os.getcwd()
        self.fetch_timeout = fetch_timeout
        self._git_executable_path: Optional[str] = None
        self._is_git_repo: Optional[bool] = None # Cache if it's a git repo
        self._is_git_available_cached: Optional[bool] = None # Cache if git command is available

        logger.info(f"GitContextManager initialized for project root: {self.project_root}")

    async def _run_git_command(self, command_args: List[str], timeout: Optional[int] = None) -> Tuple[bool, str, str]:
        """
        Runs a git command and returns its status, stdout, and stderr.

        Args:
            command_args (List[str]): The git command and its arguments.
            timeout (Optional[int]): Optional timeout for the command.

        Returns:
            Tuple[bool, str, str]: (success, stdout_str, stderr_str)
                                   success is True if return code is 0.
        """
        if not await self.is_git_available(): # Check relies on cached value after first call
            return False, "", "Git executable not found."

        try:
            # Use asyncio.to_thread to run the blocking subprocess call
            process = await asyncio.to_thread(
                subprocess.run,
                [self._git_executable_path] + command_args,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=False, # We check returncode manually
                timeout=timeout,
                errors='replace' # Handle potential encoding errors in git output
            )
            if process.returncode == 0:
                logger.debug(f"Git command '{' '.join(command_args)}' succeeded. Output: {process.stdout.strip()}")
                return True, process.stdout.strip(), process.stderr.strip()
            else:
                logger.warning(f"Git command '{' '.join(command_args)}' failed. RC: {process.returncode}, Stderr: {process.stderr.strip()}, Stdout: {process.stdout.strip()}")
                return False, process.stdout.strip(), process.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"Git command '{' '.join(command_args)}' timed out after {timeout} seconds.")
            return False, "", f"Command timed out after {timeout} seconds."
        except FileNotFoundError:
            logger.error(f"Git executable not found at '{self._git_executable_path}' during command execution.")
            self._is_git_available_cached = False # Update cache
            return False, "", "Git executable not found."
        except Exception as e:
            logger.error(f"Error running git command '{' '.join(command_args)}': {e}", exc_info=True)
            return False, "", str(e)

    async def is_git_available(self) -> bool:
        """Checks if the git executable is available in PATH. Caches the result."""
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
        """Checks if the project_root is a git repository. Caches the result."""
        if not await self.is_git_available():
            self._is_git_repo = False # Cannot be a repo if git is not available
            return False

        if self._is_git_repo is None:
            git_dir = os.path.join(self.project_root, ".git")
            if os.path.isdir(git_dir):
                # More robust check using a lightweight git command
                success, _, _ = await self._run_git_command(["rev-parse", "--is-inside-work-tree"])
                self._is_git_repo = success
            else:
                self._is_git_repo = False

            if not self._is_git_repo:
                logger.warning(f"Path '{self.project_root}' does not appear to be a git repository.")
        return self._is_git_repo

    async def get_current_branch(self) -> Optional[str]:
        """Gets the current active branch name. Returns 'HEAD' for detached HEAD state."""
        if not await self.is_repository():
            return None
        # `git symbolic-ref --short HEAD` is good for branches, fails on detached HEAD.
        # `git rev-parse --abbrev-ref HEAD` handles detached HEAD by returning "HEAD".
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
        """
        Checks if the working directory is clean (no uncommitted changes to tracked files
        and no untracked files that aren't ignored).
        """
        if not await self.is_repository():
            # If not a repo, arguably it's "clean" in the sense of no git changes.
            # Or, this check should only be called if is_repository() is true.
            return False # Or raise an error, or return True based on desired semantics

        # `git status --porcelain` output is empty if clean.
        success, porcelain_output, stderr = await self._run_git_command(["status", "--porcelain"])
        if not success:
            logger.warning(f"Failed to get working directory status: {stderr}")
            return False # Treat failure to get status as potentially unclean or problematic

        is_clean = not bool(porcelain_output)
        logger.debug(f"Working directory clean status: {is_clean}. Porcelain output: '{porcelain_output}'")
        return is_clean

    async def fetch_remote_branch(self, branch_name: str, remote_name: str = "origin") -> bool:
        """
        Fetches updates for a specific branch from the specified remote.
        Uses the configured fetch_timeout.

        Args:
            branch_name (str): The name of the branch to fetch (e.g., "main", "dev").
            remote_name (str): The name of the remote (default: "origin").

        Returns:
            bool: True if fetch was successful, False on error or timeout.
        """
        if not await self.is_repository():
            return False
        logger.info(f"Attempting to fetch '{branch_name}' from remote '{remote_name}' with timeout {self.fetch_timeout}s...")
        success, stdout, stderr = await self._run_git_command(
            ["fetch", remote_name, branch_name],
            timeout=self.fetch_timeout
        )
        if success:
            logger.info(f"Fetch for '{remote_name}/{branch_name}' completed. Stdout: {stdout}, Stderr: {stderr}")
            return True
        else:
            # Timeout is already logged by _run_git_command's TimeoutExpired exception
            if "Command timed out" not in stderr: # Avoid double logging timeout message
                 logger.warning(f"Fetch for '{remote_name}/{branch_name}' failed. Stderr: {stderr}")
            return False

    async def get_remote_tracking_branch_hash(self, branch_name: str, remote_name: str = "origin") -> Optional[str]:
        """
        Gets the commit hash of the remote-tracking branch (e.g., origin/main).
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

    async def compare_head_with_remote_tracking(self, branch_name: str, remote_name: str = "origin") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Compares HEAD with its remote-tracking branch after ensuring local remote refs are updated.

        Args:
            branch_name (str): The name of the local branch.
            remote_name (str): The name of the remote.

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]:
                (status_string, local_hash, remote_hash)
            Status can be: "synced", "ahead", "behind", "diverged", "no_upstream", "fetch_failed", "error"
        """
        if not await self.is_repository():
            return "error", None, None

        # Attempt to fetch first to get the latest state of the remote branch
        # This is important for an accurate comparison.
        if not await self.fetch_remote_branch(branch_name, remote_name):
            logger.warning(f"Fetch failed for {remote_name}/{branch_name}. Comparison might be against stale data or fail.")
            # Depending on policy, we might still try to compare against the local cache of remote.
            # For now, let's indicate fetch failure.
            # If we want to proceed with stale data, we'd skip this return.
            # return "fetch_failed", await self.get_head_commit_hash(), None # Or get stale remote hash

        local_hash = await self.get_head_commit_hash()
        remote_hash = await self.get_remote_tracking_branch_hash(branch_name, remote_name)

        if not local_hash:
            return "error", None, remote_hash # Error getting local hash

        if not remote_hash:
            # Check if an upstream is configured at all for the local branch
            # `git rev-parse --abbrev-ref @{u}` or `git for-each-ref --format='%(upstream:short)' refs/heads/<branch_name>`
            success_upstream_ref, upstream_full_ref, _ = await self._run_git_command(
                ["rev-parse", "--symbolic-full-name", f"{branch_name}@{{upstream}}"]
            )
            if not success_upstream_ref or not upstream_full_ref:
                 logger.info(f"Branch '{branch_name}' does not seem to have a configured upstream or remote '{remote_name}/{branch_name}' not found after fetch.")
                 return "no_upstream", local_hash, None
            return "error", local_hash, None # Upstream exists but couldn't get its hash

        if local_hash == remote_hash:
            return "synced", local_hash, remote_hash

        # Use git merge-base --is-ancestor <commit1> <commit2>
        # Returns 0 if commit1 is an ancestor of commit2, 1 otherwise.
        is_local_ancestor_of_remote, _, _ = await self._run_git_command(["merge-base", "--is-ancestor", local_hash, remote_hash])
        if is_local_ancestor_of_remote: # Local is older
            return "behind", local_hash, remote_hash

        is_remote_ancestor_of_local, _, _ = await self._run_git_command(["merge-base", "--is-ancestor", remote_hash, local_hash])
        if is_remote_ancestor_of_local: # Local is newer
            return "ahead", local_hash, remote_hash

        return "diverged", local_hash, remote_hash

    # --- Placeholder for Future GPG Signature Verification ---
    async def verify_commit_signature(self, commit_hash: str) -> Tuple[bool, str]:
        """
        (Future) Verifies the GPG signature of a commit.
        Requires GPG setup and trusted keys.
        Returns (is_trusted_signature_bool, status_message_str)
        """
        logger.warning("GPG commit signature verification is not yet implemented.")
        # Example: success, output, stderr = await self._run_git_command(["verify-commit", "--raw", commit_hash])
        # Parse output for GPG status (GOODSIG, BADSIG, etc.) and trust level.
        return False, "Not implemented"

    async def verify_tag_signature(self, tag_name: str) -> Tuple[bool, str]:
        """
        (Future) Verifies the GPG signature of a tag.
        Requires GPG setup and trusted keys.
        Returns (is_trusted_signature_bool, status_message_str)
        """
        logger.warning("GPG tag signature verification is not yet implemented.")
        # Example: success, output, stderr = await self._run_git_command(["tag", "-v", tag_name])
        # Stderr often contains the gpg output.
        return False, "Not implemented"

# --- Example Usage (for testing this module directly) ---
async def _main_test():
    """Internal test function for direct execution of this module."""
    print("Testing GitContextManager...")
    # Assuming this script is run from project root or a test script that sets cwd
    # For micro_X, SCRIPT_DIR in main.py would be the project root.
    # For this test, let's assume we are in the project root.
    project_root_for_test = "."
    try:
        # Attempt to get actual project root if possible (e.g., if .git is in parent)
        if not os.path.isdir(os.path.join(project_root_for_test, ".git")):
            if os.path.isdir(os.path.join(os.path.dirname(os.getcwd()), ".git")):
                 project_root_for_test = os.path.dirname(os.getcwd())
            else: # Fallback if .git isn't immediately obvious
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
            print(f"Is working directory clean (no changes to tracked files/untracked)? {is_clean}")
            if not is_clean:
                status_porcelain = await gcm._run_git_command(["status", "--porcelain"])
                print(f"  Porcelain status: \n{status_porcelain[1]}")


            if branch and branch != "HEAD": # Only try remote compare if on a branch
                print(f"\nComparing branch '{branch}' with remote 'origin'...")
                # fetch_success = await gcm.fetch_remote_branch(branch) # fetch is now part of compare
                # print(f"Fetch successful for comparison: {fetch_success}")

                comparison_status, local_h, remote_h = await gcm.compare_head_with_remote_tracking(branch)
                print(f"Comparison with remote for '{branch}': {comparison_status}")
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

