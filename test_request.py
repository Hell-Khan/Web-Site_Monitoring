import asyncio
import aiohttp

async def test():
    url = "https://www.gov.kz"
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, ssl=False, headers=headers) as resp:
            print(resp.status)

asyncio.run(test())
