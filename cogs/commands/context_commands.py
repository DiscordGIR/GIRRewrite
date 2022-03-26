from datetime import datetime
from io import BytesIO
import random
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping
from cogs.commands.info.tags import prepare_tag_embed
from utils import cfg, BlooContext
import discord
from data.services import guild_service
from utils.framework import MessageTextBucket, gatekeeper

support_tags = [tag.name for tag in guild_service.get_guild(
    ).tags if "support" in tag.name]

tag_cooldown = CooldownMapping.from_cooldown(
        1, 5, MessageTextBucket.custom)


async def handle_support_tag(ctx: BlooContext, member: discord.Member) -> None:
    if not support_tags:
        raise commands.BadArgument("No support tags found.")

    random_tag = random.choice(support_tags)
    tag = guild_service.get_tag(random_tag)

    if tag is None:
        raise commands.BadArgument("That tag does not exist.")

    # run cooldown so tag can't be spammed
    bucket = tag_cooldown.get_bucket(tag.name)
    current = datetime.now().timestamp()
    # ratelimit only if the invoker is not a moderator
    if bucket.update_rate_limit(current) and not (gatekeeper.has(ctx.guild, ctx.author, 5) or ctx.guild.get_role(guild_service.get_guild().role_sub_mod) in ctx.author.roles):
        raise commands.BadArgument("That tag is on cooldown.")

    # if the Tag has an image, add it to the embed
    file = tag.image.read()
    if file is not None:
        file = discord.File(BytesIO(
            file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")

    title = f"Hey {member.mention}, have a look at this!"
    await ctx.respond_or_edit(content=title, embed=prepare_tag_embed(tag), file=file or discord.utils.MISSING)


def setup_context_commands(bot: commands.Bot):
    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Support tag")
    async def support_tag_rc(interaction: discord.Interaction, user: discord.Member) -> None:
        ctx = BlooContext(interaction)
        await handle_support_tag(ctx, user)

    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Support tag")
    async def support_tag_msg(interaction: discord.Interaction, message: discord.Message) -> None:
        ctx = BlooContext(interaction)
        await handle_support_tag(ctx, message.author)
