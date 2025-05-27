#!/usr/bin/env python

import os
import sys
import subprocess
import logging
import argparse # Using argparse for cleaner argument handling

# --- Module-specific logger ---
logger = logging.getLogger(__name__)

def install_requirements(
    project_root: str,
    append_output_func,
    install_dev: bool = False,
    install_runtime: bool = True
):
    """
    Installs Python dependencies for the micro_X project.

    Args:
        project_root (str): The absolute path to the micro_X project root.
        append_output_func (callable): Function to append output to the UI.
                                       If None (e.g., direct script run), prints to console.
        install_dev (bool): True to install development dependencies (from requirements-dev.txt).
        install_runtime (bool): True to install runtime dependencies (from requirements.txt).
    """
    # Use a local print function if append_output_func is not provided
    _print = append_output_func if callable(append_output_func) else \
             lambda msg, style_class='INFO': print(f"[{style_class.upper()}] {msg}")

    _print("⚙️ Initiating dependency installation...", style_class='info')
    logger.info(f"install_requirements utility started. Project root: {project_root}")

    # Determine virtual environment's pip executable
    venv_dir = os.path.join(project_root, ".venv")
    pip_executable = os.path.join(venv_dir, "bin", "pip") # Default for Linux/macOS venv

    if sys.platform == "win32": # Handles cases like Git Bash on Windows, or actual Windows if venv structure differs
        pip_executable_win_scripts = os.path.join(venv_dir, "Scripts", "pip.exe")
        pip_executable_win_bin = os.path.join(venv_dir, "bin", "pip.exe") # Some venvs on Win might use bin
        if os.path.exists(pip_executable_win_scripts):
            pip_executable = pip_executable_win_scripts
        elif os.path.exists(pip_executable_win_bin):
             pip_executable = pip_executable_win_bin
        # else, it will use the default Linux/macOS path which will likely fail if on true Windows without WSL venv pathing

    if not os.path.exists(pip_executable):
        msg = f"❌ Error: pip executable not found at '{pip_executable}'. " \
              "Ensure virtual environment is created (e.g., via './setup.sh') and active, " \
              "or that this script is run from an environment where the venv's pip is accessible."
        _print(msg, style_class='error')
        logger.error(msg)
        return False

    success = True

    # Install runtime requirements
    if install_runtime:
        runtime_reqs_path = os.path.join(project_root, "requirements.txt")
        if os.path.exists(runtime_reqs_path):
            _print(f"Installing runtime dependencies from '{os.path.basename(runtime_reqs_path)}'...", style_class='info')
            logger.info(f"Running: {pip_executable} install -r {runtime_reqs_path}")
            try:
                process = subprocess.run(
                    [pip_executable, "install", "-r", runtime_reqs_path],
                    capture_output=True,
                    text=True,
                    check=False, # We check returncode manually
                    cwd=project_root # Run pip from project root
                )
                _print(f"Output:\n{process.stdout.strip()}", style_class='info')
                if process.returncode != 0:
                    _print(f"❌ Runtime installation failed:\n{process.stderr.strip()}", style_class='error')
                    logger.error(f"Runtime installation failed. Stderr: {process.stderr.strip()}")
                    success = False
                else:
                    _print("✅ Runtime dependencies installed successfully.", style_class='success')
                    logger.info("Runtime dependencies installed.")
            except Exception as e:
                _print(f"❌ Error running pip for runtime dependencies: {e}", style_class='error')
                logger.exception(f"Error running pip for runtime dependencies: {e}")
                success = False
        else:
            _print(f"⚠️ Warning: '{os.path.basename(runtime_reqs_path)}' not found. Skipping runtime installation.", style_class='warning')
            logger.warning(f"requirements.txt not found at {runtime_reqs_path}")
            success = False # Consider this a partial failure if runtime reqs are expected

    # Install development requirements
    if install_dev:
        dev_reqs_path = os.path.join(project_root, "requirements-dev.txt")
        if os.path.exists(dev_reqs_path):
            _print(f"Installing development dependencies from '{os.path.basename(dev_reqs_path)}'...", style_class='info')
            logger.info(f"Running: {pip_executable} install -r {dev_reqs_path}")
            try:
                process = subprocess.run(
                    [pip_executable, "install", "-r", dev_reqs_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=project_root # Run pip from project root
                )
                _print(f"Output:\n{process.stdout.strip()}", style_class='info')
                if process.returncode != 0:
                    _print(f"❌ Development installation failed:\n{process.stderr.strip()}", style_class='error')
                    logger.error(f"Development installation failed. Stderr: {process.stderr.strip()}")
                    success = False
                else:
                    _print("✅ Development dependencies installed successfully.", style_class='success')
                    logger.info("Development dependencies installed.")
            except Exception as e:
                _print(f"❌ Error running pip for development dependencies: {e}", style_class='error')
                logger.exception(f"Error running pip for development dependencies: {e}")
                success = False
        else:
            _print(f"⚠️ Warning: '{os.path.basename(dev_reqs_path)}' not found. Skipping development installation.", style_class='warning')
            logger.warning(f"requirements-dev.txt not found at {dev_reqs_path}")
            # Not necessarily a failure if dev reqs are optional and file is missing.
            # Set success = False if dev install was explicitly requested and file missing.

    if success:
        _print("✨ Dependency installation process completed.", style_class='success')
    else:
        _print("❌ Dependency installation process encountered errors.", style_class='error')

    return success

if __name__ == "__main__":
    # This block is for direct execution and won't use micro_X's UI manager
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    parser = argparse.ArgumentParser(
        description="Install Python dependencies for the micro_X project. "
                    "This script expects to be run from the project's 'utils' directory "
                    "or have the project root correctly determined.",
        epilog="Typically run via '/utils install_requirements [options]' from within micro_X, "
               "or directly for development setup."
    )
    parser.add_argument(
        "--runtime", action="store_true",
        help="Install runtime dependencies from requirements.txt (default if no other type specified)."
    )
    parser.add_argument(
        "--dev", action="store_true",
        help="Install development dependencies from requirements-dev.txt."
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Install both runtime and development dependencies."
    )
    
    args = parser.parse_args()

    # Determine project root if run directly from utils/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_guess = os.path.dirname(script_dir) # Assumes utils is directly under project root

    if not os.path.exists(os.path.join(project_root_guess, "main.py")):
        # Try one level up if main.py isn't in parent (e.g. if script is in root)
        if os.path.exists(os.path.join(script_dir, "main.py")):
            project_root_guess = script_dir
        else:
            print("Error: Could not reliably determine project root. Ensure 'main.py' is present.")
            print(f"Attempted project root: {project_root_guess}")
            sys.exit(1)

    # Default to runtime if no specific flags are given
    install_runtime_flag = args.runtime or (not args.dev and not args.all)
    install_dev_flag = args.dev or args.all
    
    print(f"Attempting to install requirements from project root: {project_root_guess}")
    print(f"Runtime: {install_runtime_flag}, Dev: {install_dev_flag}")
    
    # For direct execution, append_output_func is None, so it will print to console.
    install_requirements(project_root_guess, None, install_dev_flag, install_runtime_flag)
