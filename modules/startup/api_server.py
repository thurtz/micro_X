import asyncio
import os
import json
import logging
import modules.shell_engine

logger = logging.getLogger(__name__)

API_SOCKET_PATH = "/tmp/microx_api.sock"

async def api_server_handler(reader, writer, input_lock, shell_engine: modules.shell_engine.ShellEngine):
    """Handles incoming API requests."""
    data = await reader.read(4096)
    message = data.decode()
    addr = writer.get_extra_info('peername')
    logger.info(f"API server received: {message!r} from {addr!r}")

    try:
        await input_lock.acquire()
        request = json.loads(message)
        response = {}

        if request.get("type") == "get_input":
            prompt = request.get("prompt", "")
            logger.info(f"API: Handling get_input with prompt: '{prompt}'")
            
            if shell_engine:
                user_input = await shell_engine.get_user_input_from_api(prompt)
                response = {"status": "ok", "value": user_input}
            else:
                logger.error("API server cannot handle get_input: shell_engine is not available.")
                response = {"status": "error", "error": "Shell engine not initialized"}

        else:
            response = {"status": "error", "error": "Invalid request type"}

    except json.JSONDecodeError:
        logger.error("API server received invalid JSON.")
        response = {"status": "error", "error": "Invalid JSON format"}
    except Exception as e:
        logger.error(f"API server error: {e}", exc_info=True)
        response = {"status": "error", "error": str(e)}
    finally:
        if input_lock.locked():
            input_lock.release()

    writer.write(json.dumps(response).encode('utf-8'))
    await writer.drain()

    logger.info("API server closing client socket")
    writer.close()
    await writer.wait_closed()

async def start_api_server(input_lock, shell_engine_provider):
    """
    Starts the micro_X API server.
    shell_engine_provider is a callable that returns the current shell_engine instance.
    """
    # Set the environment variable for scripts to find the socket
    os.environ["MICROX_API_SOCKET"] = API_SOCKET_PATH
    
    # Clean up old socket file if it exists
    if os.path.exists(API_SOCKET_PATH):
        os.remove(API_SOCKET_PATH)
        logger.info(f"Removed stale API socket file: {API_SOCKET_PATH}")

    # We need a wrapper to pass the dependencies to the handler
    async def handler_wrapper(reader, writer):
        # We fetch the shell_engine instance dynamically because it might not be initialized when start_api_server is called
        shell_engine = shell_engine_provider()
        await api_server_handler(reader, writer, input_lock, shell_engine)

    server = await asyncio.start_unix_server(handler_wrapper, path=API_SOCKET_PATH)

    addr = server.sockets[0].getsockname()
    logger.info(f'API server listening on {addr}')

    async with server:
        await server.serve_forever()
