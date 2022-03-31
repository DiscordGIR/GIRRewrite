from io import BytesIO

import aiohttp
import discord
from data.model import Guild
from data.services import guild_service
from discord.ext import commands
from utils import cfg, logger


class Blootooth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client_session: aiohttp.ClientSession = None
        self.pending_channels = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.channel.type in [discord.ChannelType.public_thread, discord.ChannelType.private_thread]:
            return

        db_guild = guild_service.get_guild()
        # disable Blootooth if user didn't set the guild up
        if db_guild.nsa_guild_id is None or self.bot.get_guild(db_guild.nsa_guild_id) is None:
            return
        
        if message.channel.id in db_guild.logging_excluded_channels:
            return

        channel = message.channel
        blootooth_mappings = db_guild.nsa_mapping
        
        webhook_url = blootooth_mappings.get(str(channel.id))
        if channel.id not in self.pending_channels and webhook_url is None:
            self.pending_channels.add(channel.id)
            webhook_url = await self.handle_new_channel(channel, db_guild)
            self.pending_channels.remove(channel.id)

        # choose one of the three webhooks randomly
        the_webhook: discord.Webhook = discord.Webhook.from_url(webhook_url, session=self.client_session)
        # send message to webhook
        message_body = await self.prepare_message_body(message)
        try:
            await the_webhook.send(**message_body, allowed_mentions=discord.AllowedMentions(users=False, everyone=False, roles=False))
        except Exception:
            pass

    async def handle_new_channel(self, channel: discord.TextChannel, db_guild: Guild):
        # we have not seen this channel yet; let's create a channel in the Blootooth server
        # and create 3 new webhooks.
        # store the webhooks in the database.
        logger.info(f"Detected new channel {channel.name} ({channel.id})")
        guild: discord.Guild = self.bot.get_guild(db_guild.nsa_guild_id)
        category = discord.utils.get(guild.categories, name=channel.category.name)
        
        if category is None:
            category = await guild.create_category(name=channel.category.name)
        blootooth_channel = await category.create_text_channel(name=channel.name)
        webhook = (await blootooth_channel.create_webhook(name=f"Webhook {blootooth_channel.name}")).url
        guild_service.set_nsa_mapping(channel.id, webhook)

        logger.info(f"Added new webhook for channel {channel.name} ({channel.id}: {webhook}")
        return webhook

    async def prepare_message_body(self, message: discord.Message):
        member = message.author
        body = {
            "username": str(member),
            "avatar_url": member.display_avatar,
            "embeds": message.embeds or discord.utils.MISSING,
            "files": [discord.File(BytesIO(await file.read()), filename=file.filename) for file in message.attachments if file.size < 8_000_000 ]
        }
        
        attachments_too_big = "".join([file.url for file in message.attachments if file.size >= 8_000_000 ])
        footer=f"{attachments_too_big}\n\n[Link to message]({message.jump_url}) | **{member.id}**"
        content = message.content
        for mention in message.raw_role_mentions:
            content = content.replace(f"<@&{mention}>", f"`@{message.guild.get_role(mention)}`")

        characters_left = 2000 - len(content) - len(footer) - 3
        if characters_left <= 0:
            content = content[:2000 - len(footer) - 3] + "..."
            
        body["content"] = f"{content}{footer}"
        return body

async def setup(bot):
    bt = Blootooth(bot)
    bt.client_session = aiohttp.ClientSession()
    await bot.add_cog(bt)
