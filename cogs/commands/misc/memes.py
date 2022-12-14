import random
import re
from datetime import datetime
from io import BytesIO

import aiohttp
import discord
from data.model import Tag
from data.services import guild_service
from discord import app_commands
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping
from utils import GIRContext, cfg, format_number, transform_context
from utils.framework import (ImageAttachment, MessageTextBucket,
                            find_triggered_filters,
                             find_triggered_raid_phrases, gatekeeper,
                             memed_and_up, mempro_and_up, mod_and_up, whisper)
from utils.views import GenericDescriptionModal, Menu, memes_autocomplete


def format_meme_page(_, entries, current_page, all_pages):
    embed = discord.Embed(
        title=f'All memes', color=discord.Color.blurple())
    for meme in entries:
        desc = f"Added by: {meme.added_by_tag}\nUsed {format_number(meme.use_count)} {'time' if meme.use_count == 1 else 'times'}"
        if meme.image.read() is not None:
            desc += "\nHas image attachment"
        embed.add_field(name=meme.name, value=desc)
    embed.set_footer(
        text=f"Page {current_page} of {len(all_pages)}")
    return embed


class Memes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meme_cooldown = CooldownMapping.from_cooldown(
            1, 5, MessageTextBucket.custom)
        self.res_cooldown = CooldownMapping.from_cooldown(
            1, 25, MessageTextBucket.custom)
        self.memegen_cooldown = CooldownMapping.from_cooldown(
            1, 45, MessageTextBucket.custom)
        self.meme_phrases = ["{user}, have a look at this funny meme! LOL!", "Hey, {user}. Have a look at this knee-slapper!",
                             "{user}, look at this meme! Just don't show Aaron.", "{user} 😂😂😂😂😭😭😭😭"]
        self.snipe_cache = {}

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Display a meme.")
    @app_commands.autocomplete(name=memes_autocomplete)
    @app_commands.describe(user_to_mention="user to mention in the response")
    @transform_context
    async def meme(self, ctx: GIRContext, name: str, user_to_mention: discord.Member = None):
        name = name.lower()
        meme = guild_service.get_meme(name)

        if meme is None:
            raise commands.BadArgument("That meme does not exist.")

        # run cooldown so meme can't be spammed
        bucket = self.meme_cooldown.get_bucket(meme.name)
        current = datetime.now().timestamp()
        # ratelimit only if the invoker is not a moderator
        if bucket.update_rate_limit(current) and not (gatekeeper.has(ctx.guild, ctx.author, 5) or ctx.guild.get_role((await guild_service.get_roles()).role_sub_mod) in ctx.author.roles):
            raise commands.BadArgument("That meme is on cooldown.")

        # if the Meme has an image, add it to the embed
        file = meme.image.read()
        if file is not None:
            file = discord.File(BytesIO(
                file), filename="image.gif" if meme.image.content_type == "image/gif" else "image.png")

        if user_to_mention is not None:
            title = random.choice(self.meme_phrases).format(
                user=user_to_mention.mention)
        else:
            title = None

        await ctx.respond(content=title, embed=await self.prepare_meme_embed(meme), file=file or discord.utils.MISSING)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="List all memes")
    @transform_context
    @whisper
    async def memelist(self, ctx: GIRContext):
        memes = sorted((await guild_service.get_guild()).memes,
                       key=lambda meme: meme.name)

        if len(memes) == 0:
            raise commands.BadArgument("There are no memes defined.")

        menu = Menu(ctx, memes, per_page=12,
                    page_formatter=format_meme_page, whisper=ctx.whisper)
        await menu.start()

    memes = app_commands.Group(
        name="memes", description="Interact with memes", guild_ids=[cfg.guild_id])

    @mod_and_up()
    @memes.command(description="Add a new meme")
    @app_commands.describe(name="Name of the meme")
    @app_commands.describe(image="Image to show in embed")
    @transform_context
    async def add(self, ctx: GIRContext, name: str, image: ImageAttachment = None) -> None:
        if not name.isalnum():
            raise commands.BadArgument("Meme name must be alphanumeric.")

        if len(name.split()) > 1:
            raise commands.BadArgument(
                "Meme names can't be longer than 1 word.")

        if (guild_service.get_meme(name.lower())) is not None:
            raise commands.BadArgument("Meme with that name already exists.")

        # prompt the user for common issue body
        modal = GenericDescriptionModal(
            ctx, author=ctx.author, title=f"New meme — {name}")
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        description = modal.value
        if not description:
            await ctx.send_warning("Cancelled adding meme.")
            return

        # prepare meme data for database
        meme = Tag()
        meme.name = name.lower()
        meme.content = description
        meme.added_by_id = ctx.author.id
        meme.added_by_tag = str(ctx.author)

        # did the user want to attach an image to this meme?
        if image is not None:
            _type = image.content_type
            if image.size > 8_000_000:
                raise commands.BadArgument("That image is too big!")
            image = await image.read()
            # save image bytes
            meme.image.put(image, content_type=_type)

        # store meme in database
        guild_service.add_meme(meme)

        _file = meme.image.read()
        if _file is not None:
            _file = discord.File(BytesIO(
                _file), filename="image.gif" if meme.image.content_type == "image/gif" else "image.png")

        await ctx.respond(f"Added new meme!", file=_file or discord.utils.MISSING, embed=await self.prepare_meme_embed(meme))

    @mod_and_up()
    @memes.command(description="Edit an existing meme")
    @app_commands.describe(name="Name of the meme")
    @app_commands.autocomplete(name=memes_autocomplete)
    @app_commands.describe(image="Image to show in embed")
    @transform_context
    async def edit(self, ctx: GIRContext, name: str, image: ImageAttachment = None) -> None:
        if len(name.split()) > 1:
            raise commands.BadArgument(
                "Meme names can't be longer than 1 word.")

        name = name.lower()
        meme = guild_service.get_meme(name)

        if meme is None:
            raise commands.BadArgument("That meme does not exist.")

        # prompt the user for common issue body
        modal = GenericDescriptionModal(
            ctx, author=ctx.author, title=f"New meme — {name}", prefill=meme.content)
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        description = modal.value
        if not description:
            await ctx.send_warning("Cancelled adding meme.")
            return

        meme.content = description

        if image is not None:
            _type = image.content_type
            if image.size > 8_000_000:
                raise commands.BadArgument("That image is too big!")
            image = await image.read()

            # save image bytes
            if meme.image is not None:
                meme.image.replace(image, content_type=_type)
            else:
                meme.image.put(image, content_type=_type)
        else:
            meme.image.delete()

        if not guild_service.edit_meme(meme):
            raise commands.BadArgument("An error occurred editing that meme.")

        _file = meme.image.read()
        if _file is not None:
            _file = discord.File(BytesIO(
                _file), filename="image.gif" if meme.image.content_type == "image/gif" else "image.png")

        await ctx.respond(f"Meme edited!", file=_file or discord.utils.MISSING, embed=await self.prepare_meme_embed(meme))

    @mod_and_up()
    @memes.command(description="Delete a meme")
    @app_commands.describe(name="Name of the meme")
    @app_commands.autocomplete(name=memes_autocomplete)
    @transform_context
    async def delete(self, ctx: GIRContext, name: str):
        name = name.lower()

        meme = guild_service.get_meme(name)
        if meme is None:
            raise commands.BadArgument("That meme does not exist.")

        if meme.image is not None:
            meme.image.delete()

        guild_service.remove_meme(name)
        await ctx.send_warning(f"Deleted meme `{meme.name}`.", delete_after=5)

    async def prepare_meme_embed(self, meme):
        """Given a meme object, prepare the appropriate embed for it

        Parameters
        ----------
        meme : Meme
            Meme object from database

        Returns
        -------
        discord.Embed
            The embed we want to send
        """
        embed = discord.Embed(title=meme.name)
        embed.description = meme.content
        embed.timestamp = meme.added_date
        embed.color = discord.Color.blue()

        if meme.image.read() is not None:
            embed.set_image(url="attachment://image.gif" if meme.image.content_type ==
                            "image/gif" else "attachment://image.png")
        embed.set_footer(
            text=f"Added by {meme.added_by_tag} | Used {meme.use_count} {'time' if meme.use_count == 1 else 'times'}")
        return embed

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="8ball", description="Ask a question and the bot will answer with Magic!")
    @app_commands.describe(question="Question to ask")
    @transform_context
    @whisper
    async def _8ball(self, ctx: GIRContext, question: str) -> None:
        responses = ["As I see it, yes.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
                     "Don’t count on it.", "It is certain.", "It is decidedly so.", "Most likely.", "My reply is no.", "My sources say no.",
                     "Outlook not so good.", "Outlook good.", "Reply hazy, try again.", "Signs point to yes.", "Very doubtful.", "Without a doubt.",
                     "Yes.", "Yes – definitely.", "You may rely on it."]

        response = random.choice(responses)
        embed = discord.Embed(color=discord.Color.blurple())
        embed.add_field(name="Question", value=discord.utils.escape_markdown(
            question), inline=False)
        embed.add_field(name="Answer", value=response, inline=False)
        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @mempro_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Classify an image with Magic!")
    @app_commands.describe(image="Image to classify")
    @transform_context
    async def neuralnet(self, ctx: GIRContext, image: ImageAttachment) -> None:
        if cfg.resnext_token is None:
            raise commands.BadArgument("ResNext token is not set up!")

        db_guild = await guild_service.get_channels()
        is_mod = gatekeeper.has(ctx.guild, ctx.author, 5)
        if ctx.channel.id not in [db_guild.channel_general, db_guild.channel_botspam] and not is_mod:
            raise commands.BadArgument(f"This command can't be used here.")

        if not is_mod:
            bucket = self.res_cooldown.get_bucket(ctx.guild.name)
            current = datetime.now().timestamp()
            # ratelimit only if the invoker is not a moderator
            if bucket.update_rate_limit(current):
                raise commands.BadArgument("That command is on cooldown.")

        if image.size > 8_000_000:
            raise commands.BadArgument(
                "That image is too large to be processed.")

        await ctx.defer(ephemeral=False)

        contents_before = await image.read()
        contents = BytesIO(contents_before)
        async with aiohttp.ClientSession(headers={"token": cfg.resnext_token}) as client:
            form = aiohttp.FormData()
            form.add_field(
                "file", contents, content_type=image.content_type)
            async with client.post('https://resnext.slim.rocks/', data=form) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    embed = discord.Embed()
                    confidence = j.get('confidence')
                    confidence_percent = f"{confidence*100:.1f}%"
                    embed.description = f"image prediction: {j.get('classification')}\nconfidence: {confidence_percent}"
                    embed.set_footer(
                        text=f"Requested by {ctx.author} • /neuralnet • Processed in {j.get('process_time')}s")
                    embed.set_image(url="attachment://image.png")

                    if confidence < 0.25:
                        embed.color = discord.Color.red()
                    elif confidence < 0.5:
                        embed.color = discord.Color.yellow()
                    elif confidence < 0.75:
                        embed.color = discord.Color.orange()
                    else:
                        embed.color = discord.Color.green()

                    await ctx.respond(embed=embed, file=discord.File(BytesIO(contents_before), filename="image.png"))
                else:
                    raise commands.BadArgument(
                        "An error occurred classifying that image.")

    memegen = app_commands.Group(name="memegen", description="Generate memes", guild_ids=[
        cfg.guild_id])

    @memed_and_up()
    @memegen.command(description="Meme generator")
    @app_commands.describe(top_text="Text to show on top")
    @app_commands.describe(bottom_text="Text to show on bottom")
    @app_commands.describe(image="Image to use as base")
    @transform_context
    async def regular(self, ctx: GIRContext, top_text: str, bottom_text: str, image: ImageAttachment) -> None:
        if cfg.resnext_token is None:
            raise commands.BadArgument("ResNext token is not set up!")

        # ensure text is english characters only with regex
        if not re.match(r'^[\x20-\x7E]*$', top_text):
            raise commands.BadArgument("Top text can't have weird characters.")
        if not re.match(r'^[\x20-\x7E]*$', bottom_text):
            raise commands.BadArgument(
                "Bottom text can't have weird characters.")

        db_guild = await guild_service.get_channels()
        is_mod = gatekeeper.has(ctx.guild, ctx.author, 5)
        if ctx.channel.id not in [db_guild.channel_general, db_guild.channel_botspam] and not is_mod:
            raise commands.BadArgument(f"This command can't be used here.")

        if not is_mod:
            bucket = self.memegen_cooldown.get_bucket(ctx.guild.name)
            current = datetime.now().timestamp()
            # ratelimit only if the invoker is not a moderator
            if bucket.update_rate_limit(current):
                raise commands.BadArgument("That command is on cooldown.")

        if image.size > 8_000_000:
            raise commands.BadArgument(
                "That image is too large to be processed.")

        await ctx.defer(ephemeral=False)
        contents_before = await image.read()
        contents = BytesIO(contents_before)
        async with aiohttp.ClientSession(headers={"token": cfg.resnext_token}) as client:
            form = aiohttp.FormData()
            form.add_field(
                "file", contents, content_type=image.content_type)
            async with client.post(f'https://resnext.slim.rocks/meme?top_text={top_text}&bottom_text={bottom_text}', data=form) as resp:
                if resp.status == 200:
                    resp = await resp.read()
                    embed = discord.Embed()
                    embed.set_footer(
                        text=f"Requested by {ctx.author} • /memegen regular")
                    embed.set_image(url="attachment://image.png")
                    embed.color = discord.Color.random()

                    await ctx.respond(embed=embed, file=discord.File(BytesIO(resp), filename="image.png"))
                else:
                    raise commands.BadArgument(
                        "An error occurred generating that meme.")

    @memed_and_up()
    @memegen.command(description="Motivational poster)")
    @app_commands.describe(top_text="Text to show on top")
    @app_commands.describe(bottom_text="Text to show on bottom")
    @app_commands.describe(image="Image to use as base")
    @transform_context
    async def motivate(self, ctx: GIRContext, top_text: str, bottom_text: str, image: ImageAttachment) -> None:
        if cfg.resnext_token is None:
            raise commands.BadArgument("ResNext token is not set up!")

        # ensure text is english characters only with regex
        if not re.match(r'^[\x20-\x7E]*$', top_text):
            raise commands.BadArgument("Top text can't have weird characters.")
        if not re.match(r'^[\x20-\x7E]*$', bottom_text):
            raise commands.BadArgument(
                "Bottom text can't have weird characters.")

        db_guild = await guild_service.get_channels()
        is_mod = gatekeeper.has(ctx.guild, ctx.author, 5)
        if ctx.channel.id not in [db_guild.channel_general, db_guild.channel_botspam] and not is_mod:
            raise commands.BadArgument(f"This command can't be used here.")

        if not is_mod:
            bucket = self.memegen_cooldown.get_bucket(ctx.guild.name)
            current = datetime.now().timestamp()
            # ratelimit only if the invoker is not a moderator
            if bucket.update_rate_limit(current):
                raise commands.BadArgument("That command is on cooldown.")

        if image.size > 8_000_000:
            raise commands.BadArgument(
                "That image is too large to be processed.")

        await ctx.defer(ephemeral=False)
        contents_before = await image.read()
        contents = BytesIO(contents_before)
        async with aiohttp.ClientSession(headers={"token": cfg.resnext_token}) as client:
            form = aiohttp.FormData()
            form.add_field(
                "file", contents, content_type=image.content_type)
            async with client.post(f'https://resnext.slim.rocks/demotivational-meme?top_text={top_text}&bottom_text={bottom_text}', data=form) as resp:
                if resp.status == 200:
                    resp = await resp.read()
                    embed = discord.Embed()
                    embed.set_footer(
                        text=f"Requested by {ctx.author} • /memegen motivate")
                    embed.set_image(url="attachment://image.png")
                    embed.color = discord.Color.random()

                    await ctx.respond(embed=embed, file=discord.File(BytesIO(resp), filename="image.png"))
                else:
                    raise commands.BadArgument(
                        "An error occurred generating that meme.")

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Post edited or deleted message")
    @transform_context
    @whisper
    async def snipe(self, ctx: GIRContext):
        last_message: discord.Message = self.snipe_cache.get(ctx.channel.id)
        if last_message is None:
            raise commands.BadArgument("Nothing found in this channel.")

        content_added = False
        embed = discord.Embed(color=discord.Color.random())
        embed.set_author(name=f"{last_message.author.display_name} {'edited' if last_message.edited_at == True else 'deleted'} a message", icon_url=last_message.author.display_avatar.url)
        if last_message.content:
            embed.description = last_message.content[:2000] + "..." if len(last_message.content) > 2000 else last_message.content
            content_added = True

        if last_message.attachments:
            first_attachment = last_message.attachments[0]
            if first_attachment.content_type.startswith("image/"):
                embed.set_image(url=first_attachment.url)
                content_added = True

        if not content_added:
            raise commands.BadArgument("No suitable message content to send (text or image).")

        embed.timestamp = last_message.created_at
        embed.set_footer(text=f"Message ID: {last_message.id}")

        await ctx.respond(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return
        if message.channel.type != discord.ChannelType.text:
            return

        self.snipe_cache[message.channel.id] = message

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild is None:
            return
        if before.guild.id != cfg.guild_id:
            return
        if before.author.bot:
            return
        if before.channel.type != discord.ChannelType.text:
            return

        before._edited_timestamp = True
        self.snipe_cache[before.channel.id] = before



async def setup(bot):
    await bot.add_cog(Memes(bot))
