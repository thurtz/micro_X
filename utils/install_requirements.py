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
        install_dev (bool): True to install development dependencies (from requirements-dev.txt).
        install_runtime (bool): True to install runtime dependencies (from requirements.txt).
    """
    append_output_func("⚙️ Initiating dependency installation...", style_class='info')
    logger.info(f"install_requirements utility started. Project root: {project_root}")

    # Determine virtual environment's pip executable
    venv_dir = os.path.join(project_root, ".venv")
    pip_executable = os.path.join(venv_dir, "bin", "pip")

    if sys.platform == "win32": # For WSL cases which might trigger win32 sys.platform sometimes
        pip_executable = os.path.join(venv_dir, "Scripts", "pip.exe")

    if not os.path.exists(pip_executable):
        msg = f"❌ Error: pip executable not found at '{pip_executable}'. " \
              "Ensure virtual environment is created (`./setup.sh`) and active."
        append_output_func(msg, style_class='error')
        logger.error(msg)
        return False

    success = True

    # Install runtime requirements
    if install_runtime:
        runtime_reqs_path = os.path.join(project_root, "requirements.txt")
        if os.path.exists(runtime_reqs_path):
            append_output_func(f"Installing runtime dependencies from '{os.path.basename(runtime_reqs_path)}'...", style_class='info')
            logger.info(f"Running: {pip_executable} install -r {runtime_reqs_path}")
            try:
                process = subprocess.run(
                    [pip_executable, "install", "-r", runtime_reqs_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=project_root # Run pip from project root
                )
                append_output_func(f"Output:\n{process.stdout.strip()}", style_class='info')
                if process.returncode != 0:
                    append_output_func(f"❌ Runtime installation failed:\n{process.stderr.strip()}", style_class='error')
                    logger.error(f"Runtime installation failed. Stderr: {process.stderr.strip()}")
                    success = False
                else:
                    append_output_func("✅ Runtime dependencies installed successfully.", style_class='success')
                    logger.info("Runtime dependencies installed.")
            except Exception as e:
                append_output_func(f"❌ Error running pip for runtime dependencies: {e}", style_class='error')
                logger.exception(f"Error running pip for runtime dependencies: {e}")
                success = False
        else:
            append_output_func(f"⚠️ Warning: '{os.path.basename(runtime_reqs_path)}' not found. Skipping runtime installation.", style_class='warning')
            logger.warning(f"requirements.txt not found at {runtime_reqs_path}")
            success = False # Consider this a partial failure if runtime reqs are expected

    # Install development requirements
    if install_dev:
        dev_reqs_path = os.path.join(project_root, "requirements-dev.txt")
        if os.path.exists(dev_reqs_path):
            append_output_func(f"Installing development dependencies from '{os.path.basename(dev_reqs_path)}'...", style_class='info')
            logger.info(f"Running: {pip_executable} install -r {dev_reqs_path}")
            try:
                process = subprocess.run(
                    [pip_executable, "install", "-r", dev_reqs_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=project_root # Run pip from project root
                )
                append_output_func(f"Output:\n{process.stdout.strip()}", style_class='info')
                if process.returncode != 0:
                    append_output_func(f"❌ Development installation failed:\n{process.stderr.strip()}", style_class='error')
                    logger.error(f"Development installation failed. Stderr: {process.stderr.strip()}")
                    success = False
                else:
                    append_output_func("✅ Development dependencies installed successfully.", style_class='success')
                    logger.info("Development dependencies installed.")
            except Exception as e:
                append_output_func(f"❌ Error running pip for development dependencies: {e}", style_class='error')
                logger.exception(f"Error running pip for development dependencies: {e}")
                success = False
        else:
            append_output_func(f"⚠️ Warning: '{os.path.basename(dev_reqs_path)}' not found. Skipping development installation.", style_class='warning')
            logger.warning(f"requirements-dev.txt not found at {dev_reqs_path}")

    if success:
        append_output_func("✨ Dependency installation process completed.", style_class='success')
    else:
        append_output_func("❌ Dependency installation process encountered errors.", style_class='error')

    return success

if __name__ == "__main__":
    # This block is for direct execution and won't use micro_X's UI manager
    # It demonstrates how it could be called.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Mock append_output_func for direct testing
    def mock_append_output(message, style_class='default'):
        print(f"[{style_class.upper()}] {message}")

    parser = argparse.ArgumentParser(description="Install micro_X requirements.")
    parser.add_argument("--runtime", action="store_true", help="Install runtime dependencies (default if no other option specified).")
    parser.add_argument("--dev", action="store_true", help="Install development dependencies.")
    parser.add_argument("--all", action="store_true", help="Install both runtime and development dependencies.")
    
    args = parser.parse_args()

    # Determine project root if run directly from utils/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_guess = os.path.dirname(script_dir) # Assumes utils is directly under project root

    if not os.path.exists(os.path.join(project_root_guess, "main.py")):
        print("Error: Could not determine project root. Run this script from the 'utils' directory within micro_X project.")
        sys.exit(1)

    install_runtime_flag = args.runtime or (not args.dev and not args.all) # Default to runtime if no args provided
    install_dev_flag = args.dev or args.all

    # Ensure if --runtime and --dev are explicitly passed, it overrides --all behavior
    if args.runtime and args.dev:
        install_runtime_flag = True
        install_dev_flag = True
        
    print(f"Attempting to install requirements from project root: {project_root_guess}")
    install_requirements(project_root_guess, mock_append_output, install_dev_flag, install_runtime_flag)