import httpx

async def main():
    async with httpx.AsyncClient() as client:
        await client.post("http://127.0.0.1:8123/context/save")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
