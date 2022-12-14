import asyncio
import re

import aiohttp
import discord
from data.services import guild_service
from discord.ext import commands
from utils import GIROldContext, PromptData, cfg
from utils.framework import gatekeeper


class BoosterEmojis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not payload.member:
            return
        if not payload.member.guild:
            return
        if payload.member.bot:
            return
        channel = payload.member.guild.get_channel(payload.channel_id)
        try:
            msg = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        if not msg.guild.id == cfg.guild_id:
            return
        if payload.channel_id != (await guild_service.get_channels()).channel_booster_emoji:
            return
        if not str(payload.emoji) in ['✅', '❌']:
            return
        if not gatekeeper.has(payload.member.guild, payload.member, 5):
            await msg.remove_reaction(payload.emoji, payload.member)
            return

        if str(payload.emoji) == '❌':
            await msg.delete()
            return

        try:
            _bytes, name = await self.get_bytes(msg)
        except commands.BadArgument as e:
            await msg.channel.send(e, delete_after=5)
            await msg.delete(delay=5)
            return

        if _bytes is None:
            await msg.remove_reaction(payload.emoji, payload.member)
            return

        if name is None:
            prompt = PromptData(
                value_name="name",
                description="Enter name for emoji (alphanumeric and underscores).",
                convertor=str
            )
            try:
                msg.author = payload.member
                ctx = await self.bot.get_context(msg, cls=GIROldContext)
                name = await ctx.prompt(prompt)
                while True:
                    if len(name) > 2 and len(name) < 20 and re.match(r"^[a-zA-Z0-9_]*$", name):
                        break
                    prompt.reprompt = True
                    name = await ctx.prompt(prompt)

            except asyncio.TimeoutError:
                await msg.remove_reaction(payload.emoji, payload.member)

        if name is not None:
            emoji = await channel.guild.create_custom_emoji(image=_bytes, name=name)
            await msg.delete()
        else:
            return

        try:
            await payload.member.send(emoji)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return
        if msg.author.bot:
            return

        db_guild = await guild_service.get_channels()
        if not msg.guild.id == cfg.guild_id:
            return
        if not msg.channel.id == db_guild.channel_booster_emoji:
            return

        try:
            _bytes, _ = await self.get_bytes(msg)
        except commands.BadArgument as e:
            await msg.reply(e, delete_after=5)
            await msg.delete(delay=5)
            return
        try:
            await self.add_reactions(good=_bytes is not None, msg=msg)
        except discord.errors.NotFound:
            pass

    async def get_bytes(self, msg):
        custom_emojis = re.findall(r'<:\d+>|<:.+?:\d+>', msg.content)
        if len(custom_emojis) == 1:
            name = custom_emojis[0].split(':')[1]
        custom_emojis = [int(e.split(':')[2].replace('>', ''))
                         for e in custom_emojis]
        custom_emojis = [
            f"https://cdn.discordapp.com/emojis/{e}.png?v=1" for e in custom_emojis]

        custom_emojis_gif = re.findall(r'<a:.+:\d+>|<:.+?:\d+>', msg.content)
        if len(custom_emojis_gif) == 1:
            name = custom_emojis_gif[0].split(':')[1]
        custom_emojis_gif = [int(e.split(':')[2].replace('>', ''))
                             for e in custom_emojis_gif]
        custom_emojis_gif = [
            f"https://cdn.discordapp.com/emojis/{e}.gif?v=1" for e in custom_emojis_gif]
        pattern = re.compile(
            r"(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*))")
        link = pattern.search(msg.content)
        if (link):
            if link.group(0):
                link = link.group(0)

        if len(custom_emojis) > 1 or len(custom_emojis_gif) > 1 or len(msg.attachments) > 1:
            return None, None
        elif len(custom_emojis) == 1:
            emoji = custom_emojis[0]
            return await self.do_content_parsing(emoji), name
        elif len(custom_emojis_gif) == 1:
            emoji = custom_emojis_gif[0]
            return await self.do_content_parsing(emoji), name
        elif len(msg.attachments) == 1:
            url = msg.attachments[0].url
            return await self.do_content_parsing(url), None
        elif link:
            return await self.do_content_parsing(link), None
        else:
            return None, None

    async def add_reactions(self, good: bool, msg: discord.Message):
        if good:
            await msg.add_reaction('✅')
            await msg.add_reaction('❌')
        else:
            await msg.add_reaction('❓')

    async def do_content_parsing(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                if resp.status != 200:
                    return None
                elif resp.headers["CONTENT-TYPE"] not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
                    return None
                elif int(resp.headers['CONTENT-LENGTH']) > 257000:
                    raise commands.BadArgument(
                        f"Image was too big ({int(resp.headers['CONTENT-LENGTH'])/1000}KB)")
                else:
                    async with session.get(url) as resp2:
                        if resp2.status != 200:
                            return None

                        return await resp2.read()


async def setup(bot):
    await bot.add_cog(BoosterEmojis(bot))
