# --- API DOCUMENTATION for modules/ollama_manager.py ---
#
# **Purpose:** Manages the `ollama serve` process lifecycle, including starting,
# stopping, and checking the status of the Ollama service, typically within a
# managed tmux session.
#
# **Public Functions:**
#
# async def ensure_ollama_service(main_config: dict, append_output_callback: callable) -> bool:
#     """
#     Ensures the Ollama service is available, performing an automatic startup if needed.
#
#     This is the main entry point for the startup sequence in main.py. It checks if
#     the server is running; if not, and if auto-start is enabled, it attempts
#     to launch 'ollama serve' in a tmux session and waits for it to become responsive.
#
#     Args:
#         main_config (dict): The main application configuration object.
#         append_output_callback (callable): Reference to UIManager.append_output.
#
#     Returns:
#         bool: True if the service is ready, False otherwise.
#     """
#
# async def explicit_start_ollama_service(main_config: dict, append_output_callback: callable) -> bool:
#     """Handles the '/ollama start' command to explicitly start the service."""
#
# async def explicit_stop_ollama_service(main_config: dict, append_output_callback: callable) -> bool:
#     """Handles the '/ollama stop' command to explicitly stop the managed service."""
#
# async def explicit_restart_ollama_service(main_config: dict, append_output_callback: callable) -> bool:
#     """Handles the '/ollama restart' command."""
#
# async def get_ollama_status_info(main_config: dict, append_output_callback: callable):
#     """Handles the '/ollama status' command, printing status info to the UI."""
#
# async def is_ollama_server_running() -> bool:
#     """
#     Checks if the Ollama server is running and responsive via an API call.
#
#     Returns:
#         bool: True if the server is responsive, False otherwise.
#     """
#
# **Key Global Constants/Variables:**
#   (None intended for direct external use)
#
# --- END API DOCUMENTATION ---

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

TMUX_OLLAMA_SESSION_NAME = "micro_x_ollama_daemon" # Standardized session name

# --- Module-level state (initialized by ensure_ollama_service or other public functions) ---
_ollama_exe_path_cached = None
_append_output_func_cached = None
_config_cached = None
_is_initialized = False # Flag to ensure config and callback are set

def _initialize_manager_if_needed(main_config=None, append_output_callback=None):
    """Ensures the manager has its necessary shared resources."""
    global _is_initialized, _config_cached, _append_output_func_cached
    if _is_initialized:
        return
    if main_config:
        _config_cached = main_config
    if append_output_callback:
        _append_output_func_cached = append_output_callback
    
    if _config_cached and _append_output_func_cached:
        _is_initialized = True
        logger.debug("Ollama Manager initialized with config and append_output.")
    else:
        logger.error("Ollama Manager cannot be fully initialized: main_config or append_output_callback missing.")


async def _find_ollama_executable() -> str | None:
    """
    Finds the Ollama executable path using configuration or shutil.which.
    Caches the result for subsequent calls within the same micro_X session.
    """
    global _ollama_exe_path_cached
    if _ollama_exe_path_cached: # Return cached path if already found
        return _ollama_exe_path_cached

    if not _is_initialized:
        logger.error("Cannot find Ollama executable: Manager not initialized with config.")
        return None

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
        _append_output_func_cached("   Please ensure Ollama is installed and accessible, or configure its path.", style_class='error')
    return None

async def is_ollama_server_running() -> bool:
    """
    Checks if the Ollama server is running and responsive by trying to list models.
    """
    if not _is_initialized: # Required for logging/feedback via _append_output_func_cached
        logger.warning("Cannot check Ollama server status: Manager not initialized.")
        # Allow check to proceed if possible, but feedback might be missing.
    
    # No need to check _ollama_exe_path_cached here, as ollama.list() doesn't depend on it directly.
    # However, a responsive server implies ollama is installed and working.
    try:
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

async def _is_tmux_session_running(session_name: str) -> bool:
    """Checks if a tmux session with the given name is running."""
    if not shutil.which("tmux"):
        logger.warning("tmux not found, cannot check session status.")
        return False
    try:
        process = await asyncio.to_thread(
            subprocess.run, ["tmux", "has-session", "-t", session_name],
            capture_output=True, text=True, check=False # check=False, we evaluate returncode
        )
        return process.returncode == 0
    except Exception as e:
        logger.error(f"Error checking tmux session '{session_name}': {e}", exc_info=True)
        return False


async def _launch_ollama_serve_in_tmux() -> bool:
    """
    Launches 'ollama serve' in a detached tmux session.
    Returns True if the command was issued successfully, False otherwise.
    """
    if not _is_initialized or not _ollama_exe_path_cached:
        logger.error("Cannot launch 'ollama serve': Manager not initialized or Ollama executable path unknown.")
        if _append_output_func_cached:
             _append_output_func_cached("❌ Internal error: Ollama manager not ready to launch server.", style_class='error')
        return False

    if not shutil.which("tmux"):
        logger.error("tmux not found. Cannot start 'ollama serve' in a tmux window.")
        if _append_output_func_cached:
            _append_output_func_cached("❌ tmux not found. Cannot automatically start 'ollama serve'.", style_class='error')
            _append_output_func_cached("   Please install tmux or start 'ollama serve' manually.", style_class='error')
        return False

    if await _is_tmux_session_running(TMUX_OLLAMA_SESSION_NAME):
        logger.info(f"tmux session '{TMUX_OLLAMA_SESSION_NAME}' for 'ollama serve' already exists.")
        if _append_output_func_cached:
             _append_output_func_cached(f"ℹ️ A tmux session named '{TMUX_OLLAMA_SESSION_NAME}' already exists.", style_class='info')
             _append_output_func_cached(f"   Assuming 'ollama serve' is managed within it or use '/ollama restart'.", style_class='info')
        return True # Indicate we didn't fail to launch, but it might not be responsive yet.

    launch_cmd = ["tmux", "new-session", "-d", "-s", TMUX_OLLAMA_SESSION_NAME, f"{_ollama_exe_path_cached} serve"]
    try:
        logger.info(f"Launching 'ollama serve' in tmux session '{TMUX_OLLAMA_SESSION_NAME}': {' '.join(launch_cmd)}")
        await asyncio.to_thread(subprocess.run, launch_cmd, check=True)
        logger.info("'ollama serve' command issued successfully via tmux.")
        if _append_output_func_cached:
            _append_output_func_cached(f"⚙️ Starting 'ollama serve' in a new tmux session ('{TMUX_OLLAMA_SESSION_NAME}')...", style_class='info')
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch 'ollama serve' via tmux: {e.stderr or e}", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached(f"❌ Failed to start 'ollama serve' via tmux: {e.stderr or e}", style_class='error')
        return False
    except Exception as e: # Catch-all for other errors like FileNotFoundError for tmux if check failed
        logger.error(f"Unexpected error launching 'ollama serve' via tmux: {e}", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached(f"❌ Unexpected error starting 'ollama serve': {e}", style_class='error')
        return False

async def _wait_for_server_readiness() -> bool:
    """Waits for the Ollama server to become responsive after a potential start."""
    if not _is_initialized: return False
    service_config = _config_cached.get(OLLAMA_SERVICE_CONFIG_SECTION, {})
    check_retries = service_config.get(OLLAMA_SERVER_CHECK_RETRIES_KEY, 5)
    check_interval = service_config.get(OLLAMA_SERVER_CHECK_INTERVAL_KEY, 2)

    if _append_output_func_cached:
        _append_output_func_cached(f"   Waiting up to {check_retries * check_interval}s for Ollama server to become responsive...", style_class='info')
    for i in range(check_retries):
        await asyncio.sleep(check_interval)
        if _append_output_func_cached:
            _append_output_func_cached(f"   Checking server status (attempt {i+1}/{check_retries})...", style_class='ai-thinking-detail')
        if await is_ollama_server_running():
            if _append_output_func_cached:
                _append_output_func_cached("✅ Ollama server is now responsive.", style_class='success')
            return True
        logger.debug(f"Ollama server not yet responsive (attempt {i+1}/{check_retries}).")
    
    logger.error(f"Ollama server did not become responsive after {check_retries * check_interval} seconds.")
    if _append_output_func_cached:
        _append_output_func_cached("❌ Ollama server did not become responsive in time.", style_class='error')
        _append_output_func_cached(f"   Try checking the '{TMUX_OLLAMA_SESSION_NAME}' tmux session or 'ollama serve' logs.", style_class='error')
    return False

async def ensure_ollama_service(main_config: dict, append_output_callback) -> bool:
    """
    Ensures the Ollama service is available (automatic startup check).
    """
    _initialize_manager_if_needed(main_config, append_output_callback)

    logger.info("Ensuring Ollama service availability (automatic check)...")
    if _append_output_func_cached:
        _append_output_func_cached("🔍 Checking Ollama service status (automatic startup)...", style_class='info')

    if not await _find_ollama_executable():
        return False

    if await is_ollama_server_running():
        if _append_output_func_cached:
            _append_output_func_cached("✅ Ollama server is already running and responsive.", style_class='success')
        return True

    if _append_output_func_cached:
        _append_output_func_cached("ℹ️ Ollama server is not currently responsive.", style_class='info')

    service_config = _config_cached.get(OLLAMA_SERVICE_CONFIG_SECTION, {})
    auto_start = service_config.get(AUTO_START_OLLAMA_KEY, True)

    if not auto_start:
        if _append_output_func_cached:
            _append_output_func_cached("   Auto-start for 'ollama serve' is disabled in configuration.", style_class='info')
            _append_output_func_cached("   Please start 'ollama serve' manually or use '/ollama start'.", style_class='warning')
        return False

    if not await _launch_ollama_serve_in_tmux():
        if _append_output_func_cached: # _launch_ollama_serve_in_tmux handles its own error messages
            _append_output_func_cached("   Failed to initiate 'ollama serve'. AI features may not work.", style_class='error')
        return False

    return await _wait_for_server_readiness()


async def explicit_start_ollama_service(main_config: dict, append_output_callback) -> bool:
    """Explicitly tries to start the Ollama service if not already running."""
    _initialize_manager_if_needed(main_config, append_output_callback)
    if _append_output_func_cached:
        _append_output_func_cached("⚙️ Received command: /ollama start", style_class='info')

    if not await _find_ollama_executable():
        return False

    if await is_ollama_server_running():
        if _append_output_func_cached:
            _append_output_func_cached("✅ Ollama server is already running and responsive.", style_class='success')
        return True
    
    if _append_output_func_cached:
         _append_output_func_cached("ℹ️ Ollama server not responsive. Attempting to start...", style_class='info')

    if not await _launch_ollama_serve_in_tmux():
        return False # Error message handled by _launch_ollama_serve_in_tmux

    return await _wait_for_server_readiness()


async def explicit_stop_ollama_service(main_config: dict, append_output_callback) -> bool:
    """Explicitly tries to stop the managed Ollama service."""
    _initialize_manager_if_needed(main_config, append_output_callback)
    stopped_managed_session = False
    if _append_output_func_cached:
        _append_output_func_cached("⚙️ Received command: /ollama stop", style_class='info')

    if not shutil.which("tmux"):
        logger.error("tmux not found. Cannot stop managed 'ollama serve' session.")
        if _append_output_func_cached:
            _append_output_func_cached("❌ tmux not found. Cannot manage Ollama session.", style_class='error')
        return False # Cannot determine status or stop without tmux

    if not await _is_tmux_session_running(TMUX_OLLAMA_SESSION_NAME):
        if _append_output_func_cached:
            _append_output_func_cached(f"ℹ️ No managed Ollama tmux session ('{TMUX_OLLAMA_SESSION_NAME}') found to stop.", style_class='info')
        # If no managed session, check if an external server is running
        if await is_ollama_server_running():
            if _append_output_func_cached:
                _append_output_func_cached("   However, an Ollama server is currently responsive (possibly started externally).", style_class='warning')
            return True # No managed session to stop, but server is up (externally)
        else:
            if _append_output_func_cached:
                _append_output_func_cached("   No other Ollama server appears to be running.", style_class='info')
            return True # No managed session, no other server. "Stop" is effectively true.

    kill_cmd = ["tmux", "kill-session", "-t", TMUX_OLLAMA_SESSION_NAME]
    try:
        if _append_output_func_cached:
            _append_output_func_cached(f"Attempting to stop managed Ollama session ('{TMUX_OLLAMA_SESSION_NAME}')...", style_class='info')
        await asyncio.to_thread(subprocess.run, kill_cmd, check=True, capture_output=True)
        logger.info(f"tmux session '{TMUX_OLLAMA_SESSION_NAME}' killed successfully.")
        if _append_output_func_cached:
            _append_output_func_cached(f"✅ Managed Ollama tmux session ('{TMUX_OLLAMA_SESSION_NAME}') stopped.", style_class='success')
        stopped_managed_session = True
        
        # Wait a moment for the server to actually shut down
        await asyncio.sleep(2) 

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to kill tmux session '{TMUX_OLLAMA_SESSION_NAME}': {e.stderr or e}", exc_info=True)
        if _append_output_func_cached:
            _append_output_func_cached(f"❌ Failed to stop tmux session '{TMUX_OLLAMA_SESSION_NAME}': {e.stderr or e}", style_class='error')
        return False # Failed to stop the session

    # After attempting to stop, check overall server responsiveness
    if await is_ollama_server_running():
        if _append_output_func_cached:
            _append_output_func_cached(f"⚠️ Managed Ollama session '{TMUX_OLLAMA_SESSION_NAME}' was targeted for stopping, but an Ollama server is still responsive.", style_class='warning')
            _append_output_func_cached(f"   This might be an externally managed Ollama instance.", style_class='warning')
    else:
        if _append_output_func_cached and stopped_managed_session: # Only confirm if we actually stopped it
             _append_output_func_cached("   Ollama server is no longer responsive.", style_class='info')
    
    return True # True because the action to stop the *managed* session was completed or it wasn't running.


async def explicit_restart_ollama_service(main_config: dict, append_output_callback) -> bool:
    """Explicitly tries to restart the managed Ollama service."""
    _initialize_manager_if_needed(main_config, append_output_callback)
    if _append_output_func_cached:
        _append_output_func_cached("⚙️ Received command: /ollama restart", style_class='info')
        _append_output_func_cached("   Attempting to stop the managed Ollama service first...", style_class='info')

    stop_success = await explicit_stop_ollama_service(main_config, append_output_callback)
    
    if not stop_success: # If stopping failed in a way that prevents restart
        if _append_output_func_cached:
            _append_output_func_cached("❌ Restart aborted because stopping the service failed critically.", style_class='error')
        return False

    # Even if stop_success is true but an external server was detected, we still proceed to try and start "our" managed one.
    if _append_output_func_cached:
        _append_output_func_cached("   Now attempting to start the Ollama service...", style_class='info')
    
    # Brief pause before restarting
    await asyncio.sleep(1) 

    return await explicit_start_ollama_service(main_config, append_output_callback)

async def get_ollama_status_info(main_config: dict, append_output_callback):
    """Gets and appends the status of the Ollama service and managed session."""
    _initialize_manager_if_needed(main_config, append_output_callback)
    if not _append_output_func_cached: return

    _append_output_func_cached("📊 Ollama Service Status:", style_class='info-header')

    exe_path = await _find_ollama_executable()
    if exe_path:
        _append_output_func_cached(f"  Ollama Executable: Found at '{exe_path}'", style_class='info')
    else:
        _append_output_func_cached("  Ollama Executable: Not found.", style_class='error')
        # No point checking further if executable isn't found for managed session
        return

    if await is_ollama_server_running():
        _append_output_func_cached("  Ollama Server API: Responsive ✅", style_class='success')
    else:
        _append_output_func_cached("  Ollama Server API: Not responsive ❌", style_class='error')

    if await _is_tmux_session_running(TMUX_OLLAMA_SESSION_NAME):
        _append_output_func_cached(f"  Managed Tmux Session ('{TMUX_OLLAMA_SESSION_NAME}'): Running ✅", style_class='success')
    else:
        _append_output_func_cached(f"  Managed Tmux Session ('{TMUX_OLLAMA_SESSION_NAME}'): Not running ❌", style_class='info')

    service_config = _config_cached.get(OLLAMA_SERVICE_CONFIG_SECTION, {})
    auto_start = service_config.get(AUTO_START_OLLAMA_KEY, True)
    _append_output_func_cached(f"  Automatic Startup on micro_X launch: {'Enabled' if auto_start else 'Disabled'}", style_class='info')

