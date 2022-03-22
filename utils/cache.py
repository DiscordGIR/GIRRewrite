import asyncio

import discord
from data.services import guild_service

from .config import cfg 
from .logging import logger


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
