import asyncio
import json
import urllib
from contextlib import asynccontextmanager

import aiohttp
from aiocache import cached

client_session = None
_last_ios_cfw = None


@cached(ttl=3600)
async def get_ios_cfw():
    """Gets all apps on ios.cfw.guide

    Returns
    -------
    dict
        "ios, jailbreaks, devices"
    """

    global _last_ios_cfw
    try:
        async with client_session.get("https://api.appledb.dev/main.json") as resp:
            resp.raise_for_status()
            data = await resp.json()
            if not isinstance(data, dict) or not all(key in data for key in ("ios", "group", "device")):
                raise ValueError("AppleDB returned an invalid catalog")
            _last_ios_cfw = data
            return data
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        if _last_ios_cfw is not None:
            return _last_ios_cfw
        raise


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


async def canister_search_package(query):
    """Search for a tweak in Canister's catalogue

    Parameters
    ----------
    query : str
        "Query to search for"

    Returns
    -------
    list
        "List of packages that Canister found matching the query"

    """
    ignored_repos = ["zodttd", "modmyi"]
    async with client_session.get(f'https://api.canister.me/v2/jailbreak/package/search?q={urllib.parse.quote(query)}') as resp:
        if resp.status == 200:
            response = json.loads(await resp.text())
            packages = response.get('data')
            packages = [package for package in packages if package['repository']['slug'] not in ignored_repos]
            return packages
        else:
            return None


async def canister_search_repo(query):
    """Search for a repo in Canister's catalogue

    Parameters
    ----------
    query : str
        "Query to search for"

    Returns
    -------
    list
        "List of repos that Canister found matching the query"

    """

    async with client_session.get(f'https://api.canister.me/v2/jailbreak/repository/search?q={urllib.parse.quote(query)}') as resp:
        if resp.status == 200:
            response = json.loads(await resp.text())
            return response.get('data')
        else:
            return None


@cached(ttl=3600)
async def canister_fetch_repos():
    async with client_session.get('https://api.canister.me/v2/jailbreak/repository/ranking?rank=*') as resp:
        if resp.status == 200:
            response = await resp.json(content_type=None)
            return response.get("data")

        return None


@cached(ttl=3600)
async def fetch_scam_urls():
    async with client_session.get("https://raw.githubusercontent.com/SlimShadyIAm/Anti-Scam-Json-List/main/antiscam.json") as resp:
        resp.raise_for_status()
        obj = json.loads(await resp.text())
        if not isinstance(obj, dict):
            raise ValueError("Scam feed must be an object")
        for key in ("scamjburls", "scamideviceunlockurls"):
            if not isinstance(obj.get(key), list) or not all(isinstance(url, str) for url in obj[key]):
                raise ValueError(f"Scam feed has an invalid {key} list")
        return obj


async def init_client_session():
    global client_session
    if client_session is None or client_session.closed:
        client_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20, connect=5),
            connector=aiohttp.TCPConnector(limit=32, limit_per_host=8),
        )


@asynccontextmanager
async def shared_session():
    """Borrow the bot-owned pool; callers must not close it."""
    if client_session is None or client_session.closed:
        raise RuntimeError("HTTP client is not initialized")
    yield client_session


async def close_client_session():
    global client_session
    if client_session is not None:
        await client_session.close()
        client_session = None
