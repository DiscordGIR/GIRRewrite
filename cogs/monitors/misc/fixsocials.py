import asyncio
import re
from aiocache import cached
import aiohttp

import discord
from data.services import guild_service
from discord.ext import commands
from utils import cfg


class FixSocials(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # regex for tiktok urls
        self.tiktok_pattern = re.compile(r"https:\/\/(www.)?((vm|vt).tiktok.com\/[A-Za-z0-9]+|tiktok.com\/@[\w.]+\/video\/[\d]+\/?|tiktok.com\/t\/[a-zA-Z0-9]+\/)")

        # regex for instagram urls
        self.instagram_pattern = re.compile(r"(https:\/\/(www.)?instagram\.com\/(?:p|reel)\/([^/?#&]+))\/")


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

        message_content = message.content.strip("<>")
        if tiktok_match := self.tiktok_pattern.search(message_content):
            link = tiktok_match.group(0)
            await self.fix_tiktok(message, link) 
        elif instagram_match := self.instagram_pattern.search(message_content):
            link = instagram_match.group(0)
            await self.fix_instagram(message, link)

    @cached(ttl=3600)
    async def get_tiktok_redirect(self, link: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(link, allow_redirects=False) as response:
                if response.status != 301:
                    return
            
                redirected_url = str(response).split("Location': \'")[1].split("\'")[0]
        
        redirected_url = redirected_url.replace('www.tiktok.com', 'vxtiktok.com')
        if (tracking_id_index := redirected_url.index('?')) is not None:
            # remove everything after the question mark (tracking ID)
            redirected_url = redirected_url[:tracking_id_index]

        return redirected_url

    async def fix_tiktok(self, message: discord.Message, link: str):
        redirected_url = await self.get_tiktok_redirect(link)
        if redirected_url is None:
            return

        await message.reply(f"I hate tiktok but here you go {redirected_url}", mention_author=False)
        await asyncio.sleep(0.5)
        await message.edit(suppress=True)

    async def fix_instagram(self, message: discord.Message, link: str):
        link = link.replace("www.", "")
        link = link.replace("instagram.com", "ddinstagram.com")

        # get video id from link
        await message.reply(f"I hate instagram but here you go {link}", mention_author=False)
        await asyncio.sleep(0.5)
        await message.edit(suppress=True)


async def setup(bot):
    await bot.add_cog(FixSocials(bot))
