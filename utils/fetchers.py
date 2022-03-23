import aiohttp
from aiocache import cached

client_session = None


@cached(ttl=3600)
async def get_ios_cfw():
    """Gets all apps on ios.cfw.guide

    Returns
    -------
    dict
        "ios, jailbreaks, devices"
    """

    async with client_session.get("https://api.appledb.dev/main.json") as resp:
        if resp.status == 200:
            data = await resp.json()

    return data


@cached(ttl=3600)
async def get_ipsw_firmware_info(version: str):
    """Gets all apps on ios.cfw.guide

    Returns
    -------
    dict
        "ios, jailbreaks, devices"
    """

    async with client_session.get(f"https://api.ipsw.me/v4/ipsw/{version}") as resp:
        if resp.status == 200:
            data = await resp.json()
            return data

        return []


@cached(ttl=600)
async def get_dstatus_components():
    async with client_session.get("https://discordstatus.com/api/v2/components.json") as resp:
        if resp.status == 200:
            components = await resp.json()
            return components


@cached(ttl=600)
async def get_dstatus_incidents():
    async with client_session.get("https://discordstatus.com/api/v2/incidents.json") as resp:
        if resp.status == 200:
            incidents = await resp.json()
            return incidents


async def init_client_session():
    global client_session
    client_session = aiohttp.ClientSession()
