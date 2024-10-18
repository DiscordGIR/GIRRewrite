import asyncio
import discord

from typing import Union
from data_mongo.model import Case, Guild
from data_mongo.services.guild_service import guild_service
from data_mongo.services.user_service import user_service
from utils.context import GIRContext
from utils.mod.mod_logs import prepare_ban_log, prepare_kick_log

from utils.config import cfg


def add_kick_case(target_member: discord.Member, mod: discord.Member, reason: str, db_guild):
    """Adds kick case to user

    Parameters
    ----------
    target_member : discord.Member
        "Member who was kicked"
    mod : discord.Member
        "Member that kicked"
    reason : str
        "Reason member was kicked"
    db_guild
        "Guild DB"

    """
    # prepare case for DB
    case = Case(
        _id=db_guild.case_id,
        _type="KICK",
        mod_id=mod.id,
        mod_tag=str(mod),
        reason=reason,
    )

    # increment max case ID for next case
    guild_service.inc_caseid()
    # add new case to DB
    user_service.add_case(target_member.id, case)

    return prepare_kick_log(mod, target_member, case)


async def notify_user(target_member, text, log):
    """Notifies a specified user about something

    Parameters
    ----------
    user : discord.Member
        "User to notify"
    text : str
        "Text to send"
    log : discord.Embed
        "Embed to send"
    """
    try:
        await target_member.send(text, embed=log)
    except Exception:
        return False
    return True


async def notify_user_warn(ctx: GIRContext, target_member: discord.Member, mod: discord.Member, db_user, db_guild, cur_points: int, log):
    """Notifies a specified user about a warn

    Parameters
    ----------
    ctx : GIRContext
        "Bot context"
    target_member : discord.Member
        "User to notify"
    mod : discord.Member
        "User that warned"
    db_user
        "User DB"
    db_guild
        "Guild DB"
    cur_points : int
        "Number of points the user currently has"
    log : discord.Embed
        "Embed to send"
    """
    log_kickban = None
    dmed = True

    if cur_points >= 600:
        # automatically ban user if more than 600 points

        if cfg.ban_appeal_url is None:
            dmed = await notify_user(target_member, f"You were banned from {ctx.guild.name} for reaching 600 or more points.", log)
        else:
            dmed = await notify_user(target_member, f"You were banned from {ctx.guild.name} for reaching 600 or more points.\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>", log)

        log_kickban = await add_ban_case(target_member, mod, "600 or more warn points reached.", db_guild)
        await target_member.ban(reason="600 or more warn points reached.")

        if isinstance(ctx, discord.Interaction):
            ctx.client.ban_cache.ban(target_member.id)
        else:
            ctx.bot.ban_cache.ban(target_member.id)

    elif cur_points >= 400 and not db_user.was_warn_kicked and isinstance(target_member, discord.Member):
        # kick user if >= 400 points and wasn't previously kicked
        user_service.set_warn_kicked(target_member.id)

        dmed = await notify_user(target_member, f"You were kicked from {ctx.guild.name} for reaching 400 or more points. Please note that you will be banned at 600 points.", log)
        log_kickban = add_kick_case(target_member, mod, "400 or more warn points reached.", db_guild)
        await target_member.kick(reason="400 or more warn points reached.")
    else:
        if isinstance(target_member, discord.Member):
            dmed = await notify_user(target_member, f"You were warned in {ctx.guild.name}. Please note that you will be kicked at 400 points and banned at 600 points.", log)

    if log_kickban:
        await submit_public_log(ctx, target_member, log_kickban)

    return dmed


async def response_log(ctx, log):
    if isinstance(ctx, GIRContext):
        if ctx.interaction.response.is_done():
            res = await ctx.interaction.followup.send(embed=log)
            await res.delete(delay=10)
        else:
            await ctx.interaction.response.send_message(embed=log)
            ctx.bot.loop.create_task(delay_delete(ctx.interaction))
    elif isinstance(ctx, discord.Interaction):
        if ctx.response.is_done():
            res = await ctx.followup.send(embed=log)
            await res.delete(delay=10)
        else:
            await ctx.response.send_message(embed=log)
            ctx.client.loop.create_task(delay_delete(ctx))

    else:
        await ctx.send(embed=log, delete_after=10)


async def submit_public_log(ctx: GIRContext, user: Union[discord.Member, discord.User], log, dmed: bool = None):
    """Submits a public log

    Parameters
    ----------
    ctx : GIRContext
        "Bot context"
    user : discord.Member
        "User to notify"
    db_user
        "User DB"
    db_guild
        "Guild DB"
    cur_points : int
        "Number of points the user currently has"
    log : discord.Embed
        "Embed to send"
    """
    public_chan = ctx.guild.get_channel(
        cfg.channels.public_logs)
    if public_chan:
        log.remove_author()
        log.set_thumbnail(url=user.display_avatar)
        if dmed is not None:
            await public_chan.send(user.mention if not dmed else "", embed=log)
        else:
            await public_chan.send(embed=log)


async def add_ban_case(target_member: discord.Member, mod: discord.Member, reason, db_guild: Guild = None):
    """Adds ban case to user

    Parameters
    ----------
    ctx : GIRContext
        "Bot context"
    user : discord.Member
        "Member who was banned"
    reason : str
        "Reason member was banned"
    db_guild
        "Guild DB"

    """
    # prepare the case to store in DB
    case = Case(
        _id=db_guild.case_id,
        _type="BAN",
        mod_id=mod.id,
        mod_tag=str(mod),
        punishment="PERMANENT",
        reason=reason,
    )

    # increment DB's max case ID for next case
    guild_service.inc_caseid()
    # add case to db
    user_service.add_case(target_member.id, case)
    # prepare log embed to send to #public-mod-logs, user and context
    return prepare_ban_log(mod, target_member, case)

async def delay_delete(ctx: discord.Interaction):
    await asyncio.sleep(10)
    await ctx.delete_original_response()
