"""Music discovery and cross-service link commands."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils import cfg, logger
from utils.runtime_paths import runtime_data_file


SONG_LINK_API = "https://api.song.link/v1-alpha.1/links"
ITUNES_SEARCH_API = "https://itunes.apple.com/search"
COMMUNITY_FILE = Path(os.environ.get("GIR_COMMUNITY_FILE", runtime_data_file("community.json")))
SUPPORTED_LINK = re.compile(
    r"https?://(?:open\.spotify\.com|spotify\.link|music\.apple\.com|youtu\.be|(?:www\.)?youtube\.com|tidal\.com|deezer\.com|soundcloud\.com)/\S+",
    re.IGNORECASE,
)
PLATFORMS = (
    ("spotify", "Spotify"), ("appleMusic", "Apple Music"), ("youtube", "YouTube"),
    ("youtubeMusic", "YouTube Music"), ("tidal", "TIDAL"), ("deezer", "Deezer"),
    ("amazonMusic", "Amazon Music"), ("soundcloud", "SoundCloud"),
)

def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return fallback


def _music_settings() -> dict:
    defaults = {
        "enabled": True, "autoConvertLinks": True, "monitoredChannelIDs": [],
    }
    current = _read_json(COMMUNITY_FILE, {}).get("music", {})
    defaults.update(current if isinstance(current, dict) else {})
    return defaults


def _clean(value: object, limit: int = 250) -> str:
    return discord.utils.escape_markdown(str(value or "Unknown")[:limit])


class MusicSuite(commands.Cog):
    music = app_commands.Group(
        name="music", description="Find songs and open them in your preferred music service",
        guild_ids=[cfg.guild_id],
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None
        self._cooldown = commands.CooldownMapping.from_cooldown(4, 30.0, commands.BucketType.user)

    async def cog_load(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12), headers={"User-Agent": "GIR-Music/1.0"})

    async def cog_unload(self):
        if self._session:
            await self._session.close()

    async def _json(self, url: str, *, params: dict | None = None) -> dict:
        assert self._session is not None
        async with self._session.get(url, params=params) as response:
            if response.status == 429:
                raise RuntimeError("The music service is busy. Try again in a moment.")
            response.raise_for_status()
            return await response.json(content_type=None)

    async def _song_links(self, url: str) -> dict:
        if not _music_settings().get("enabled", True):
            raise RuntimeError("Music tools are turned off for this server.")
        return await self._json(SONG_LINK_API, params={"url": url})

    async def _search_song(self, query: str) -> str | None:
        data = await self._json(ITUNES_SEARCH_API, params={"term": query, "entity": "song", "limit": "1"})
        rows = data.get("results") or []
        return rows[0].get("trackViewUrl") if rows else None

    @staticmethod
    def _song_embed(data: dict) -> tuple[discord.Embed, discord.ui.View]:
        entities = data.get("entitiesByUniqueId") or {}
        entity = entities.get(data.get("entityUniqueId")) or next(iter(entities.values()), {})
        title = _clean(entity.get("title"), 180)
        artist = _clean(entity.get("artistName"), 180)
        embed = discord.Embed(title=title, description=f"by **{artist}**", color=0x79D956)
        thumbnail = entity.get("thumbnailUrl")
        if thumbnail and str(thumbnail).startswith("https://"):
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text="Choose a service to listen")
        view = discord.ui.View(timeout=180)
        links = data.get("linksByPlatform") or {}
        for index, (key, label) in enumerate(PLATFORMS):
            url = (links.get(key) or {}).get("url")
            if url:
                view.add_item(discord.ui.Button(
                    label=label, url=url, style=discord.ButtonStyle.link, row=index // 5))
        return embed, view

    async def _send_song(self, destination, url: str, *, ephemeral: bool = False):
        try:
            data = await self._song_links(url)
            embed, view = self._song_embed(data)
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError) as error:
            logger.warning("Music link lookup failed: %s", error)
            if isinstance(destination, discord.Interaction):
                await destination.followup.send("I could not match that song across services right now.", ephemeral=True)
            return
        if isinstance(destination, discord.Interaction):
            await destination.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        else:
            await destination.reply(embed=embed, view=view, mention_author=False)

    @music.command(name="link", description="Turn a song link into buttons for other music services")
    async def music_link(self, interaction: discord.Interaction, url: str):
        if not SUPPORTED_LINK.search(url):
            await interaction.response.send_message("Paste a Spotify, Apple Music, YouTube, TIDAL, Deezer, or SoundCloud song link.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._send_song(interaction, url)

    @music.command(name="search", description="Find a song and get links for popular music services")
    async def music_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        if not _music_settings().get("enabled", True):
            await interaction.followup.send("Music tools are turned off for this server.", ephemeral=True)
            return
        try:
            url = await self._search_song(query[:200])
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError):
            url = None
        if not url:
            await interaction.followup.send("I could not find a song for that search.", ephemeral=True)
            return
        await self._send_song(interaction, url)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        settings = _music_settings()
        if not settings.get("enabled", True) or not message.guild or message.author.bot or message.guild.id != cfg.guild_id:
            return
        channels = {int(item) for item in settings.get("monitoredChannelIDs", []) if str(item).isdigit()}
        if channels and message.channel.id not in channels:
            return
        bucket = self._cooldown.get_bucket(message)
        if bucket.update_rate_limit(message.created_at.timestamp()):
            return
        content = message.content.strip()
        match = SUPPORTED_LINK.search(content)
        if match and settings.get("autoConvertLinks", True):
            await self._send_song(message, match.group(0))


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicSuite(bot))
