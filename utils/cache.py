import asyncio
from re import S

import discord
from data.services import guild_service
from utils.fetchers import fetch_scam_urls

from .config import cfg 
from .logging import logger


class BanCache:
    def __init__(self, bot):
        self.bot = bot
        self.cache = set()

    async def fetch_ban_cache(self):
        guild = self.bot.get_guild(cfg.guild_id)
        the_list = [ban async for ban in guild.bans(limit=None)]
        self.cache = {entry.user.id for entry in the_list}

    def is_banned(self, user_id):
        return user_id in self.cache

    def ban(self, user_id):
        self.cache.add(user_id)

    def unban(self, user_id):
        self.cache.discard(user_id)


class IssueCache():
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}

    def __contains__(self, item):
        if item in self.cache:
            return True

    async def fetch_issue_cache(self):
        guild: discord.TextChannel = self.bot.get_guild(cfg.guild_id)
        if not guild:
            return

        channel = guild.get_channel(
            guild_service.get_guild().channel_common_issues)
        if channel is None:
            logger.warn("#rules-and-info channel not found! The /issue command will not work! Make sure to set `channel_common_issues` in the database if you want it.")
            return

        async for message in channel.history(limit=None, oldest_first=True):
            if message.author.id != self.bot.user.id:
                continue

            if not message.embeds:
                continue

            embed = message.embeds[0]
            if not embed.footer.text:
                continue

            if embed.footer.text.startswith("Submitted by"):
                self.cache[f"{embed.title}"] = message
            else:
                continue

class RuleCache():
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}

    async def fetch_rule_cache(self):
        guild: discord.TextChannel = self.bot.get_guild(cfg.guild_id)
        if not guild:
            return

        channel = guild.get_channel(
            guild_service.get_guild().channel_rules)
        if channel is None:
            logger.warn("#rules-and-info channel not found! The /rule command will not work! Make sure to set `channel_rules` in the database if you want it.")
            return

        async for message in channel.history(limit=None, oldest_first=True):
            if not message.embeds:
                continue
            
            for embed in message.embeds:
                self.cache[f"{embed.title}"] = embed

class ScamCache:
    def __init__(self):
        self.scam_jb_urls = []
        self.scam_unlock_urls = []

    async def fetch_scam_cache(self):
        obj = await fetch_scam_urls()
        scam_jb_urls = obj.get("scamjburls")
        if scam_jb_urls is not None:
            self.scam_jb_urls = scam_jb_urls
        
        scam_unlock_urls = obj.get("scamideviceunlockurls")
        if scam_unlock_urls is not None:
            self.scam_unlock_urls = scam_unlock_urls

scam_cache = ScamCache()