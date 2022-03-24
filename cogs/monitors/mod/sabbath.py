from datetime import timezone
import discord
from discord.ext import commands

from data.services import guild_service
from utils import cfg, logger
from utils.framework import gatekeeper

class Sabbath(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_cooldown = commands.CooldownMapping.from_cooldown(
            1, 300.0, commands.BucketType.member)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return

        # check if message pings aaron or owner role:
        if not (cfg.aaron_id in message.raw_mentions or cfg.aaron_role in message.raw_role_mentions):
            return

        if not guild_service.get_guild().sabbath_mode:
            return

        if gatekeeper.has(message.guild, message.author, 5):
            return

        current = message.created_at.replace(tzinfo=timezone.utc).timestamp()
        bucket = self.spam_cooldown.get_bucket(message)
        if bucket.update_rate_limit(current):
            return

        await message.channel.send(f"<@{cfg.aaron_id}> is away on Sabbath, he will get back to you as soon as possible!", allowed_mentions=discord.AllowedMentions(users=False))


async def setup(bot):
    if cfg.aaron_id is None or cfg.aaron_role is None:
        logger.warn(
            "Aaron's ID or role not set, disabling the Sabbath cog! If you want this, refer to README.md.")
        return

    await bot.add_cog(Sabbath(bot))
