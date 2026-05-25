import os

import aiohttp

API_URL = os.getenv("API_URL")


async def get_guild_settings(guild_id: int):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/settings/{guild_id}") as r:
            return await r.json()
