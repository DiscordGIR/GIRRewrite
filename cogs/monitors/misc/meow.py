import random

import discord
from data.services import guild_service
from discord.ext import commands
from utils import cfg


class Meow(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meow_messages = [
          'meow',
          'moew',
          'mow',
          'MEOWWWWWWWWWWWWWWWW',
          'meowwwwwww',
          'MOEEW!!!!!!!!!!!!!!!!!!!!!!',
          'MEOOOOWZERS'
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
        if message.channel.id != guild_service.get_guild().channel_general:
            return

        # randomly meow in #general sometimes
        # 1 in 500 channce of meowing
        if random.randint(1, 500) == 1:
            await message.channel.send(random.choice(self.meow_messages))


async def setup(bot):
    await bot.add_cog(Meow(bot))
