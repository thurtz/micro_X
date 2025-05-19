#!/usr/bin/env python

import asyncio
import shutil
import subprocess
import logging
import ollama # Main Ollama library
import time

# --- Module-specific logger ---
logger = logging.getLogger(__name__)

# --- Configuration Keys (to be accessed from the main config object) ---
OLLAMA_SERVICE_CONFIG_SECTION = "ollama_service"
OLLAMA_EXECUTABLE_PATH_KEY = "executable_path"
AUTO_START_OLLAMA_KEY = "auto_start_serve"
OLLAMA_STARTUP_WAIT_KEY = "startup_wait_seconds" # Total time to wait for server after launch
OLLAMA_SERVER_CHECK_RETRIES_KEY = "server_check_retries" # Number of checks within the wait period
OLLAMA_SERVER_CHECK_INTERVAL_KEY = "server_check_interval_seconds" # Interval between checks

# --- Module-level state (initialized by ensure_ollama_service) ---
_ollama_exe_path_cached = None
_append_output_func_cached = None
_config_cached = None

async def _find_ollama_executable() -> str | None:
    """
    Finds the Ollama executable path using configuration or shutil.which.
    Caches the result for subsequent calls within the same micro_X session.
    """
    global _ollama_exe_path_cached
    if _ollama_exe_path_cached:
        return _ollama_exe_path_cached

    configured_path = _config_cached.get(OLLAMA_SERVICE_CONFIG_SECTION, {}).get(OLLAMA_EXECUTABLE_PATH_KEY)
    if configured_path and shutil.which(configured_path):
        logger.info(f"Ollama executable found via configured path: {configured_path}")
        _ollama_exe_path_cached = configured_path
        return configured_path
    elif configured_path:
        logger.warning(f"Configured Ollama path '{configured_path}' not found or not executable.")

    found_path = shutil.which("ollama")
    if found_path:
        logger.info(f"Ollama executable found in PATH: {found_path}")
        _ollama_exe_path_cached = found_path
        return found_path

    logger.error("Ollama executable not found in PATH or via configuration.")
    if _append_output_func_cached:
        _append_output_func_cached("❌ Ollama executable ('ollama') not found in your system PATH.", style_class='error')
        _append_output_func_cached("   Please ensure Ollama is installed and accessible.", style_class='error')
    return None

async def is_ollama_server_running() -> bool:
    """
    Checks if the Ollama server is running and responsive by trying to list models.
    """
    if not _ollama_exe_path_cached: # Should have been found by ensure_ollama_service
        logger.warning("Cannot check Ollama server status: executable path unknown.")
        return False
    try:
        # Attempt a lightweight API call to check responsiveness
        # ollama.list() is synchronous, so run it in a thread
        await asyncio.to_thread(ollama.list)
        logger.info("Ollama server is running and responsive (ollama.list() successful).")
        return True
    except ollama.RequestError as e: # Typically connection errors
        logger.info(f"Ollama server appears to be down or unreachable: {e}")
        return False
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error while checking Ollama server status: {e}", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached(f"⚠️ Error checking Ollama status: {e}", style_class='warning')
        return False

async def _launch_ollama_serve_in_tmux() -> bool:
    """
    Launches 'ollama serve' in a detached tmux session.
    Returns True if the command was issued successfully, False otherwise.
    """
    if not _ollama_exe_path_cached:
        logger.error("Cannot launch 'ollama serve': Ollama executable path unknown.")
        return False

    if not shutil.which("tmux"):
        logger.error("tmux not found. Cannot start 'ollama serve' in a tmux window.")
        if _append_output_func_cached:
            _append_output_func_cached("❌ tmux not found. Cannot automatically start 'ollama serve'.", style_class='error')
            _append_output_func_cached("   Please install tmux or start 'ollama serve' manually.", style_class='error')
        return False

    tmux_session_name = "micro_x_ollama_daemon"
    # Command to check if the session exists
    check_session_cmd = ["tmux", "has-session", "-t", tmux_session_name]
    # Command to launch ollama serve in a new detached tmux session
    launch_cmd = ["tmux", "new-session", "-d", "-s", tmux_session_name, f"{_ollama_exe_path_cached} serve"]

    try:
        # Check if the tmux session already exists
        session_exists_process = await asyncio.to_thread(
            subprocess.run, check_session_cmd, capture_output=True, text=True
        )
        if session_exists_process.returncode == 0:
            logger.info(f"tmux session '{tmux_session_name}' for 'ollama serve' already exists. Assuming server is managed.")
            if _append_output_func_cached:
                 _append_output_func_cached(f"ℹ️ A tmux session named '{tmux_session_name}' already exists.", style_class='info')
                 _append_output_func_cached(f"   Assuming 'ollama serve' is running or managed within it.", style_class='info')
            # We will still proceed to check if it's responsive, but won't try to launch it again.
            return True # Indicate we didn't fail to launch, but it might not be responsive yet.

        logger.info(f"Launching 'ollama serve' in tmux session '{tmux_session_name}': {' '.join(launch_cmd)}")
        await asyncio.to_thread(subprocess.run, launch_cmd, check=True)
        logger.info("'ollama serve' command issued successfully via tmux.")
        if _append_output_func_cached:
            _append_output_func_cached(f"⚙️ Starting 'ollama serve' in a new tmux session ('{tmux_session_name}')...", style_class='info')
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch 'ollama serve' via tmux: {e.stderr or e}", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached(f"❌ Failed to start 'ollama serve' via tmux: {e.stderr or e}", style_class='error')
        return False
    except FileNotFoundError: # Should be caught by shutil.which("tmux") earlier, but as a safeguard
        logger.error("tmux not found during launch attempt.", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached("❌ tmux not found when attempting to start 'ollama serve'.", style_class='error')
        return False
    except Exception as e:
        logger.error(f"Unexpected error launching 'ollama serve' via tmux: {e}", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached(f"❌ Unexpected error starting 'ollama serve': {e}", style_class='error')
        return False

async def ensure_ollama_service(main_config: dict, append_output_callback) -> bool:
    """
    Ensures the Ollama service is available.
    Checks if 'ollama' is found, if the server is running,
    and attempts to start it via tmux if configured to do so.

    Args:
        main_config: The main application configuration dictionary.
        append_output_callback: Function to append messages to the UI.

    Returns:
        True if the Ollama service is ready for use, False otherwise.
    """
    global _config_cached, _append_output_func_cached
    _config_cached = main_config
    _append_output_func_cached = append_output_callback

    service_config = _config_cached.get(OLLAMA_SERVICE_CONFIG_SECTION, {})
    auto_start = service_config.get(AUTO_START_OLLAMA_KEY, True)
    # startup_wait_total = service_config.get(OLLAMA_STARTUP_WAIT_KEY, 10) # Total time to wait
    check_retries = service_config.get(OLLAMA_SERVER_CHECK_RETRIES_KEY, 5) # Number of checks
    check_interval = service_config.get(OLLAMA_SERVER_CHECK_INTERVAL_KEY, 2) # Seconds between checks


    logger.info("Ensuring Ollama service availability...")
    _append_output_func_cached("🔍 Checking Ollama service status...", style_class='info')

    if not await _find_ollama_executable():
        # _find_ollama_executable already calls append_output on error
        return False

    if await is_ollama_server_running():
        _append_output_func_cached("✅ Ollama server is already running and responsive.", style_class='success')
        return True

    _append_output_func_cached("ℹ️ Ollama server is not currently responsive.", style_class='info')

    if not auto_start:
        _append_output_func_cached("   Auto-start for 'ollama serve' is disabled in configuration.", style_class='info')
        _append_output_func_cached("   Please start 'ollama serve' manually if AI features are needed.", style_class='warning')
        return False

    if not await _launch_ollama_serve_in_tmux():
        # _launch_ollama_serve_in_tmux calls append_output on error
        _append_output_func_cached("   Failed to initiate 'ollama serve'. AI features may not work.", style_class='error')
        return False

    # Wait and check for server readiness
    _append_output_func_cached(f"   Waiting up to {check_retries * check_interval}s for Ollama server to become responsive...", style_class='info')
    for i in range(check_retries):
        await asyncio.sleep(check_interval)
        _append_output_func_cached(f"   Checking server status (attempt {i+1}/{check_retries})...", style_class='ai-thinking-detail')
        if await is_ollama_server_running():
            _append_output_func_cached("✅ Ollama server started and is now responsive.", style_class='success')
            return True
        logger.debug(f"Ollama server not yet responsive after launch (attempt {i+1}/{check_retries}).")

    logger.error(f"Ollama server was started but did not become responsive after {check_retries * check_interval} seconds.")
    _append_output_func_cached("❌ Ollama server started but did not become responsive in time.", style_class='error')
    _append_output_func_cached("   Try checking the 'ollama_daemon' tmux session or 'ollama serve' logs.", style_class='error')
    return False