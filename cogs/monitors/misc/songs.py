import json
import random
import re

import aiohttp
import discord
from data.services import guild_service
from discord.ext import commands
from utils import cfg
from utils.framework import find_triggered_filters

platforms = {
    "spotify": {
        "name": "Spotify",
        "emote": "<:Music_Spotify:958786315883794532>"
    },
    "appleMusic": {
        "name": "Apple Music",
        "emote": "<:Music_AppleMusic:958786213337264169>"
    },
    "youtube": {
        "name": "YouTube",
        "emote": "<:Music_YouTube:958786388457840700>"
    },
}


class Songs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # self.spotify_pattern = re.compile(r"[\bhttps://open.\b]spotify[\b.com\b]*[/:]*track[/:]*[A-Za-z0-9]+")
        # self.am_pattern = re.compile(r"[\bhttps://music.\b]apple[\b.com\b]*[/:][[a-zA-Z][a-zA-Z]]?[:/]album[/:][a-zA-Z\d%\(\)-]+[/:][\d]{1,10}")
        self.pattern = re.compile(r"https:\/\/(open.spotify.com\/track\/[A-Za-z0-9]+|music.apple.com\/[a-zA-Z][a-zA-Z]?\/album\/[a-zA-Z\d%\(\)-]+/[\d]{1,10}\?i=[\d]{1,15})")
        self.song_phrases = [
            "I Like listening to {artist} too!\n Here's \"{title}\"...",
            "You listen to {artist} too? They're my favorite!\nHere's \"{title}\"..."
        ]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if cfg.aaron_id is None or cfg.aaron_role is None:
            return
        if not message.guild:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return
        if message.channel.id != (await guild_service.get_guild()).channel_general:
            return

        match = self.pattern.search(message.content.strip("<>"))
        if match:
            link = match.group(0)
            await self.generate_view(message, link)
            return

    async def generate_view(self, message: discord.Message, link: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.song.link/v1-alpha.1/links?url={link}') as resp:
                if resp.status != 200:
                    return None

                res = await resp.text()
                res = json.loads(res)

        spotify_data = res.get('linksByPlatform').get('spotify')
        unique_id = spotify_data.get(
            'entityUniqueId') if spotify_data is not None else res.get('entityUniqueId')
        title = res.get('entitiesByUniqueId').get(unique_id)

        if title is not None:
            title = random.choice(self.song_phrases).format(
                artist=title.get('artistName'), title=title.get('title'))
            title = discord.utils.escape_markdown(title)
            title = discord.utils.escape_mentions(title)

        triggered_words = await find_triggered_filters(
            title, message.author)

        if triggered_words:
            title = "<:fr:959135064657109012>"

        view = discord.ui.View()
        for platform, body in platforms.items():
            platform_links = res.get('linksByPlatform').get(platform)
            if platform_links is not None:
                view.add_item(discord.ui.Button(style=discord.ButtonStyle.link,
                            emoji=body["emote"], url=platform_links.get('url')))

        await message.reply(content=title, view=view, mention_author=False)


async def setup(bot):
    await bot.add_cog(Songs(bot))
