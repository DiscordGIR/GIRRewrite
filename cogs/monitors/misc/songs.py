import json
import random
import re

import aiohttp
import discord
import spotipy
from discord.ext import commands
from spotipy.oauth2 import SpotifyOAuth

from data.services import guild_service
from utils import cfg
from utils.framework import find_triggered_filters, gatekeeper
from utils.logging import logger
from datetime import timezone

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
    sp: spotipy.Spotify
    
    def __init__(self, bot):
        self.bot = bot
        self.pattern = re.compile(
            r"https:\/\/(open.spotify.com\/track\/[A-Za-z0-9]+|music.apple.com\/[a-zA-Z][a-zA-Z]?\/album\/[a-zA-Z\d%\(\)-]+/[\d]{1,10}\?i=[\d]{1,15})")
        self.song_phrases = [
            "I like listening to {artist} too!\n Here's \"{title}\"...",
            "You listen to {artist} too? They're my favorite!\nHere's \"{title}\"...",
            "Wow, \"{title}\" by {artist} is such a good tune!\nI could listen to this all day...",
            "I'm a fan of {artist} too! \n\"{title}\" is such a great song, thanks for sharing!",
            "I'm a big fan of {artist}, \nand \"{title}\" is one of my favorite songs of theirs.",
        ]
        self.spotify_cooldown = commands.CooldownMapping.from_cooldown(
            rate=4, per=3600.0, type=commands.BucketType.member)

    async def cog_load(self):
        if cfg.spotify_id is None or cfg.spotify_secret is None:
            return

        try:
            sp_oauth = SpotifyOAuth(client_id=cfg.spotify_id, client_secret=cfg.spotify_secret,
                                    redirect_uri="http://localhost:8081", scope='playlist-modify-public', open_browser=False)
            token_info = sp_oauth.get_cached_token()

            if not token_info and cfg.spotify_auth_code is None:
                auth_url = sp_oauth.get_authorize_url()
                logger.warning(f'Please go to this URL to authorize access, then set the environment variable `SPOTIFY_AUTH_CODE`: {auth_url}')
                self.sp = None
                return

            token_info = sp_oauth.get_access_token(cfg.spotify_auth_code)
            self.sp = spotipy.Spotify(auth_manager=sp_oauth)
            logger.info("Authenticated with Spotify!")
        except Exception as e:
            logger.error(f"Failed to authenticate with Spotify: {e}")
            self.sp = None

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
        if message.channel.id != guild_service.get_guild().channel_general:
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
        spotify_uri = spotify_data.get('nativeAppUriDesktop')
        unique_id = spotify_data.get(
            'entityUniqueId') if spotify_data is not None else res.get('entityUniqueId')
        title = res.get('entitiesByUniqueId').get(unique_id)

        if title is not None:
            title = random.choice(self.song_phrases).format(
                artist=title.get('artistName'), title=title.get('title'))
            title = discord.utils.escape_markdown(title)
            title = discord.utils.escape_mentions(title)

        triggered_words = find_triggered_filters(
            title, message.author)

        if triggered_words:
            title = "<:fr:959135064657109012>"

        view = discord.ui.View()
        for platform, body in platforms.items():
            platform_links = res.get('linksByPlatform').get(platform)
            if platform_links is not None:
                view.add_item(discord.ui.Button(style=discord.ButtonStyle.link,
                                                emoji=body["emote"], url=platform_links.get('url')))

        message_to_edit = await message.reply(content=title, view=view, mention_author=False)

        if not gatekeeper.has(message.guild, message.author, 3):
            return

        if spotify_uri is not None and not triggered_words:
            self.bot.loop.create_task(
                self.add_to_spotify_playlist(spotify_uri, message_to_edit))

    async def add_to_spotify_playlist(self, track_id: str, message: discord.Message):
        if self.sp is None:
            return

        playlist = self.sp.playlist_tracks(cfg.spotify_playlist_url)
        track_ids = [track['track']['id'] for track in playlist['items']]

        if track_id.split(":")[-1] in track_ids:
            return

        bucket = self.spotify_cooldown.get_bucket(message)
        current = message.created_at.replace(tzinfo=timezone.utc).timestamp()

        if bucket.update_rate_limit(current):
            return

        try:
            self.sp.playlist_add_items(cfg.spotify_playlist_url, [track_id])
            await message.edit(embed=discord.Embed(description=f"Added to the [r/Jailbreak Spotify playlist](https://open.spotify.com/playlist/{cfg.spotify_playlist_url})!"))
        except Exception as e:
            print(e)


async def setup(bot):
    await bot.add_cog(Songs(bot))
