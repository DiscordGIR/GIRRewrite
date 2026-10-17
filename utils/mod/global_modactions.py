from datetime import timedelta
from typing import Union

import discord
import humanize
from data.model import Case
from data.services import guild_service, user_service
from discord.utils import escape_markdown
from utils import cfg, logger

from .mod_logs import prepare_mute_log, prepare_unmute_log, prepare_warn_log
from .modactions_helpers import (execute_ban, notify_user, notify_user_warn, response_log,
                                 submit_public_log)


async def mute(ctx, target_member: discord.Member, mod: discord.Member, dur_seconds=None, reason="No reason."):
    """Mutes a member

    Parameters
    ----------
    ctx : GIRContext
        "Bot context"
    member : discord.Member
        "Member to mute"
    dur_seconds : int
        "Mute duration in settings"
    reason : str
        "Reason for mute"

    """

    now = discord.utils.utcnow()

    if dur_seconds is not None:
        time = now + timedelta(seconds=dur_seconds)
        if time > now + timedelta(days=14):
            time = now + timedelta(days=14)
    else:
        time = now + timedelta(days=14)

    case = Case(
        _id=guild_service.allocate_case_id(),
        _type="MUTE",
        date=now,
        mod_id=mod.id,
        mod_tag=str(mod),
        reason=reason,
    )

    case.until = time
    case.punishment = humanize.naturaldelta(
        time - now, minimum_unit="seconds")
    await target_member.timeout(time, reason=reason)
    user_service.add_case(target_member.id, case)
    try:
        bot = ctx.client if isinstance(ctx, discord.Interaction) else ctx.bot
        bot.tasks.schedule_untimeout(target_member.id, time)
    except Exception:
        # Discord expires the timeout itself; losing the optional expiry log
        # must not erase the successful punishment's audit record.
        logger.exception("Could not schedule timeout expiry for %s", target_member.id)

    log = prepare_mute_log(mod, target_member, case)
    await response_log(ctx, log)

    log.remove_author()
    log.set_thumbnail(url=target_member.display_avatar)
    dmed = await notify_user(target_member, f"You have been muted in {ctx.guild.name}", log)
    await submit_public_log(ctx, target_member, log, dmed)
    return time


async def dismiss_report_timeout(ctx, member_id, expected_until, reason):
    """Only remove the specific timeout that this report successfully applied."""
    if expected_until is None:
        return
    try:
        member = await ctx.guild.fetch_member(member_id)
    except discord.NotFound:
        return
    current = member.timed_out_until
    if current is None or current <= discord.utils.utcnow():
        return
    # Discord serializes timestamps to milliseconds.
    if abs((current - expected_until).total_seconds()) > 0.001:
        raise ValueError("This member has a different timeout; review it before dismissing.")
    await unmute(ctx, member, mod=ctx.user, reason=reason)


async def unmute(ctx, target_member: discord.Member, mod: discord.Member, reason: str = "No reason.") -> None:
    """Unmutes a user (mod only)

    Example usage
    --------------
    /unmute member:<member> reason:<reason>

    Parameters
    ----------
    user : discord.Member
        "Member to unmute"
    reason : str, optional
        "Reason for unmute, by default 'No reason.'"

    """

    await target_member.edit(timed_out_until=None)

    try:
        if isinstance(ctx, discord.Interaction):
            ctx.client.tasks.cancel_unmute(target_member.id)
        else:
            ctx.tasks.cancel_unmute(target_member.id)
    except Exception as e:
        pass

    case = Case(
        _id=guild_service.allocate_case_id(),
        _type="UNMUTE",
        mod_id=mod.id,
        mod_tag=str(mod),
        reason=reason,
    )

    user_service.add_case(target_member.id, case)

    log = prepare_unmute_log(mod, target_member, case)
    await response_log(ctx, log)

    dmed = await notify_user(target_member, f"You have been unmuted in {ctx.guild.name}", log)
    await submit_public_log(ctx, target_member, log, dmed)


async def ban(ctx, target_member: Union[discord.Member, discord.User], mod: discord.Member, reason="No reason."):
    bot = ctx.client if isinstance(ctx, discord.Interaction) else ctx.bot
    dm_text = None
    if not isinstance(target_member, discord.User):
        dm_text = f"You have been banned from {ctx.guild.name}"
        if cfg.ban_appeal_url is not None:
            dm_text += f"\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>"
    log = await execute_ban(bot, ctx.guild, target_member, mod, reason, dm_text=dm_text)
    await response_log(ctx, log)
    await submit_public_log(ctx, target_member, log)


async def warn(ctx, target_member: discord.Member, mod: discord.Member, points, reason):

    reason = escape_markdown(reason)

    # prepare the case object for database
    case = Case(
        _id=guild_service.allocate_case_id(),
        _type="WARN",
        mod_id=mod.id,
        mod_tag=str(mod),
        reason=reason,
        punishment=str(points)
    )

    # add new case to DB
    user_service.add_case(target_member.id, case)
    # add warnpoints to the user in DB
    user_service.inc_points(target_member.id, points)

    # fetch latest document about user from DB
    db_user = user_service.get_user(target_member.id)
    cur_points = db_user.warn_points

    # prepare log embed, send to #public-mod-logs, user, channel where invoked
    log = prepare_warn_log(mod, target_member, case)
    log.add_field(name="Current points", value=cur_points, inline=True)

    # also send response in channel where command was called
    dmed = await notify_user_warn(ctx, target_member, mod, db_user, cur_points, log)
    await response_log(ctx, log)
    await submit_public_log(ctx, target_member, log, dmed)

