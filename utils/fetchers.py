import json
from aiocache import cached
import aiohttp


@cached(ttl=3600)
async def get_ios_cfw():
    """Gets all apps on ios.cfw.guide

    Returns
    -------
    dict
        "ios, jailbreaks, devices"
    """

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.appledb.dev/main.json") as resp:
            if resp.status == 200:
                data = await resp.json()

    return data
