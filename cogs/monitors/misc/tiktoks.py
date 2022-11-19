import re

import discord
from data.services import guild_service
from discord.ext import commands
from utils import cfg


class TikToks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # regex for tiktok urls
        self.pattern = re.compile(r"https:\/\/(www.)?((vm|vt).tiktok.com\/[A-Za-z0-9]+|tiktok.com\/@[\w.]+\/video\/[\d]+\/?|tiktok.com\/t\/[a-zA-Z0-9]+\/)")

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
        if not match:
            return 

        link = match.group(0)
        
        # remove host from link
        link = link.replace("www.", "")
        link = link.replace("vm.tiktok.com/", "vm.dstn.to/")
        link = link.replace("vt.tiktok.com/", "vm.dstn.to/")
        link = link.replace("tiktok.com/", "vm.dstn.to/")
        
        # get video id from link
        await message.edit(suppress=True)
        await message.reply(f"I hate tiktok but here you go {link}")

async def setup(bot):
    await bot.add_cog(TikToks(bot))
