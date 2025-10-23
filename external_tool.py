import httpx
import asyncio

async def main():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8123/context")
        if response.status_code == 200:
            context = response.json()
            print("Current Directory:", context.get("current_directory"))
            print("Command History:", context.get("command_history"))
            print("Git Status:", context.get("git_status"))
        else:
            print(f"Error: {response.status_code}")
    except httpx.RequestError as e:
        print(f"Error connecting to MCP server: {e}")

if __name__ == "__main__":
    asyncio.run(main())
