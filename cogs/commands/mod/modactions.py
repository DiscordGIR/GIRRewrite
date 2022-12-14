from datetime import datetime, timedelta, timezone

import discord
import humanize
from apscheduler.jobstores.base import ConflictingIdError
from data.model import Case
from data.services import guild_service, user_service
from discord import app_commands
from discord.ext import commands
from discord.utils import escape_markdown, escape_mentions
from utils import GIRContext, cfg, transform_context
from utils.framework import mod_and_up, ModsAndAboveMemberOrUser, Duration, ModsAndAboveMember, UserOnly
from utils.mod import (add_ban_case, add_kick_case, notify_user,
                       prepare_editreason_log, prepare_liftwarn_log,
                       prepare_mute_log, prepare_removepoints_log,
                       prepare_unban_log, prepare_unmute_log,
                       submit_public_log, warn)
from utils.views import warn_autocomplete
from utils.views.confirm import SecondStaffConfirm


class ModActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="warn a user")
    @app_commands.describe(user="User to warn")
    @app_commands.describe(points="Points to warn the user with")
    @app_commands.describe(reason="Reason for warning")
    @transform_context
    async def warn(self, ctx: GIRContext, user: ModsAndAboveMemberOrUser, points: app_commands.Range[int, 1, 600], reason: str):
        if points < 1:  # can't warn for negative/0 points
            raise commands.BadArgument(message="Points can't be lower than 1.")

        await ctx.defer(ephemeral=False)
        await warn(ctx, target_member=user, mod=ctx.author, points=points, reason=reason)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Kick a user")
    @app_commands.describe(member="User to kick")
    @app_commands.describe(reason="Reason for kicking")
    @transform_context
    async def kick(self, ctx: GIRContext, member: ModsAndAboveMember, reason: str) -> None:
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        log = await add_kick_case(target_member=member, mod=ctx.author, reason=reason)
        await notify_user(member, f"You were kicked from {ctx.guild.name}", log)

        await ctx.defer(ephemeral=False)
        await member.kick(reason=reason)

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, member, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Kick a user")
    @app_commands.describe(member="User to kick")
    @transform_context
    async def roblox(self, ctx: GIRContext, member: ModsAndAboveMember) -> None:
        reason = "This Discord server is for iOS jailbreaking, not Roblox. Please join https://discord.gg/jailbreak instead, thank you!"

        log = await add_kick_case(target_member=member, mod=ctx.author, reason=reason)
        await notify_user(member, f"You were kicked from {ctx.guild.name}", log)

        await ctx.defer(ephemeral=False)
        await member.kick(reason=reason)

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, member, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Mute a user")
    @app_commands.describe(member="User to mute")
    @app_commands.describe(duration="Duration of the mute (i.e 10m, 1h, 1d...)")
    @app_commands.describe(reason="Reason for muting")
    @transform_context
    async def mute(self, ctx: GIRContext, member: ModsAndAboveMember, duration: Duration, reason: str = "No reason.") -> None:
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        now = datetime.now(tz=timezone.utc)
        delta = duration

        if delta is None:
            raise commands.BadArgument("Please input a valid duration!")

        if member.is_timed_out():
            raise commands.BadArgument("This user is already muted.")

        await ctx.defer(ephemeral=False)
        time = now + timedelta(seconds=delta)
        if time > now + timedelta(days=14):
            raise commands.BadArgument("Mutes can't be longer than 14 days!")

        case = Case(
            _id=await guild_service.get_new_case_id(),
            _type="MUTE",
            date=now,
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )

        case.until = time
        case.punishment = humanize.naturaldelta(
            time - now, minimum_unit="seconds")

        try:
            await member.timeout(time, reason=reason)
            ctx.tasks.schedule_untimeout(member.id, time)
        except ConflictingIdError:
            raise commands.BadArgument(
                "The database thinks this user is already muted.")

        await guild_service.inc_case_id()
        user_service.add_case(member.id, case)

        log = prepare_mute_log(ctx.author, member, case)
        await ctx.respond_or_edit(embed=log, delete_after=10)

        log.remove_author()
        log.set_thumbnail(url=member.display_avatar)

        dmed = await notify_user(member, f"You have been muted in {ctx.guild.name}", log)
        await submit_public_log(ctx, member, log, dmed)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Unmute a user")
    @app_commands.describe(member="User to unmute")
    @app_commands.describe(reason="Reason for unmuting")
    @transform_context
    async def unmute(self, ctx: GIRContext, member: ModsAndAboveMember, reason: str) -> None:
        if not member.is_timed_out():
            raise commands.BadArgument("This user is not muted.")

        await ctx.defer(ephemeral=False)
        await member.edit(timed_out_until=None)

        try:
            ctx.tasks.cancel_unmute(member.id)
        except Exception:
            pass

        case = Case(
            _id=await guild_service.get_new_case_id(),
            _type="UNMUTE",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )
        await guild_service.inc_case_id()
        user_service.add_case(member.id, case)

        log = prepare_unmute_log(ctx.author, member, case)

        await ctx.respond_or_edit(embed=log, delete_after=10)

        dmed = await notify_user(member, f"You have been unmuted in {ctx.guild.name}", log)
        await submit_public_log(ctx, member, log, dmed)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Ban a user")
    @app_commands.describe(user="User to ban")
    @app_commands.describe(reason="Reason for banning")
    @transform_context
    async def ban(self, ctx: GIRContext, user: ModsAndAboveMemberOrUser, reason: str):
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        member_is_external = isinstance(user, discord.User)

        # if the ID given is of a user who isn't in the guild, try to fetch the profile
        if member_is_external:
            if self.bot.ban_cache.is_banned(user.id):
                raise commands.BadArgument("That user is already banned!")

        await ctx.defer(ephemeral=False)
        self.bot.ban_cache.ban(user.id)
        log = await add_ban_case(user, ctx.author, reason)

        if not member_is_external:
            if cfg.ban_appeal_url is None:
                await notify_user(user, f"You have been banned from {ctx.guild.name}", log)
            else:
                await notify_user(user, f"You have been banned from {ctx.guild.name}\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>", log)

            await user.ban(reason=reason)
        else:
            # hackban for user not currently in guild
            await ctx.guild.ban(discord.Object(id=user.id))

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, user, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Ban a user anonymously")
    @app_commands.describe(user="User to ban")
    @app_commands.describe(reason="Reason for banning")
    @transform_context
    async def staffban(self, ctx: GIRContext, user: ModsAndAboveMemberOrUser, reason: str):
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        member_is_external = isinstance(user, discord.User)

        # if the ID given is of a user who isn't in the guild, try to fetch the profile
        if member_is_external:
            if self.bot.ban_cache.is_banned(user.id):
                raise commands.BadArgument("That user is already banned!")

        confirm_embed = discord.Embed(description=f"{ctx.author.mention} wants to staff ban {user.mention} with reason `{reason}`. Another Moderator needs to click Yes to submit this ban.\n\nClicking Yes means this was discussed amongst the staff team and will hide the banning Moderator. This should not be used often.", color=discord.Color.blurple())
        view = SecondStaffConfirm(ctx, ctx.author)
        await ctx.respond_or_edit(view=view, embed=confirm_embed)
        await view.wait()

        if not view.value:
            await ctx.send_warning(f"Cancelled staff banning {user.mention}.")
            return

        self.bot.ban_cache.ban(user.id)
        log = await add_ban_case(user, ctx.author, reason)

        log.set_field_at(1, name="Mod", value=f"{ctx.guild.name} Staff")

        if not member_is_external:
            if cfg.ban_appeal_url is None:
                await notify_user(user, f"You have been banned from {ctx.guild.name}", log)
            else:
                await notify_user(user, f"You have been banned from {ctx.guild.name}\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>", log)
            await user.ban(reason=reason)
        else:
            # hackban for user not currently in guild
            await ctx.guild.ban(discord.Object(id=user.id))

        await ctx.interaction.message.delete()
        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, user, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Unban a user")
    @app_commands.describe(user="User to unban")
    @app_commands.describe(reason="Reason for unbanning")
    @transform_context
    async def unban(self, ctx: GIRContext, user: UserOnly, reason: str) -> None:
        if ctx.guild.get_member(user.id) is not None:
            raise commands.BadArgument(
                "You can't unban someone already in the server!")

        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        if not self.bot.ban_cache.is_banned(user.id):
            raise commands.BadArgument("That user isn't banned!")

        await ctx.defer(ephemeral=False)
        try:
            await ctx.guild.unban(discord.Object(id=user.id), reason=reason)
        except discord.NotFound:
            raise commands.BadArgument(f"{user} is not banned.")

        self.bot.ban_cache.unban(user.id)

        case = Case(
            _id=await guild_service.get_new_case_id(),
            _type="UNBAN",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )
        await guild_service.inc_case_id()
        user_service.add_case(user.id, case)

        log = prepare_unban_log(ctx.author, user, case)
        await ctx.respond_or_edit(embed=log, delete_after=10)

        await submit_public_log(ctx, user, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Purge channel messages")
    @app_commands.describe(amount="Number of messages to purge")
    @transform_context
    async def purge(self, ctx: GIRContext, amount: app_commands.Range[int, 1, 100]) -> None:
        if amount <= 0:
            raise commands.BadArgument(
                "Number of messages to purge must be greater than 0")
        elif amount >= 100:
            amount = 100

        msgs = [message async for message in ctx.channel.history(limit=amount)]
        await ctx.channel.purge(limit=amount)
        await ctx.send_success(f'Purged {len(msgs)} messages.', delete_after=10)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Marks a warn and lifted and removes points")
    @app_commands.describe(member="Member to lift warn of")
    @app_commands.describe(case_id="Case ID of the warn to lift")
    @app_commands.autocomplete(case_id=warn_autocomplete)
    @app_commands.describe(reason="Reason for lifting the warn")
    @transform_context
    async def liftwarn(self, ctx: GIRContext, member: ModsAndAboveMember, case_id: str, reason: str) -> None:
        cases = user_service.get_cases(member.id)
        case = cases.cases.filter(_id=case_id).first()

        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        # sanity checks
        if case is None:
            raise commands.BadArgument(
                message=f"{member} has no case with ID {case_id}")
        elif case._type != "WARN":
            raise commands.BadArgument(
                message=f"{member}'s case with ID {case_id} is not a warn case.")
        elif case.lifted:
            raise commands.BadArgument(
                message=f"Case with ID {case_id} already lifted.")

        u = user_service.get_user(id=member.id)
        if u.warn_points - int(case.punishment) < 0:
            raise commands.BadArgument(
                message=f"Can't lift Case #{case_id} because it would make {member.mention}'s points negative.")

        # passed sanity checks, so update the case in DB
        case.lifted = True
        case.lifted_reason = reason
        case.lifted_by_tag = str(ctx.author)
        case.lifted_by_id = ctx.author.id
        case.lifted_date = datetime.now()
        cases.save()

        # remove the warn points from the user in DB
        user_service.inc_points(member.id, -1 * int(case.punishment))
        dmed = True
        # prepare log embed, send to #public-mod-logs, user, channel where invoked
        log = prepare_liftwarn_log(ctx.author, member, case)
        dmed = await notify_user(member, f"Your warn has been lifted in {ctx.guild}.", log)

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, member, log, dmed)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Edit case reason")
    @app_commands.describe(member="Member to edit case of")
    @app_commands.describe(case_id="Case ID of the case to edit")
    @app_commands.autocomplete(case_id=warn_autocomplete)
    @app_commands.describe(new_reason="New reason for the case")
    @transform_context
    async def editreason(self, ctx: GIRContext, member: ModsAndAboveMemberOrUser, case_id: str, new_reason: str) -> None:
        # retrieve user's case with given ID
        cases = user_service.get_cases(member.id)
        case = cases.cases.filter(_id=case_id).first()

        new_reason = escape_markdown(new_reason)
        new_reason = escape_mentions(new_reason)

        # sanity checks
        if case is None:
            raise commands.BadArgument(
                message=f"{member} has no case with ID {case_id}")

        old_reason = case.reason
        case.reason = new_reason
        case.date = datetime.now()
        cases.save()

        dmed = True
        log = prepare_editreason_log(ctx.author, member, case, old_reason)

        dmed = await notify_user(member, f"Your case was updated in {ctx.guild.name}.", log)

        public_chan = ctx.guild.get_channel(
            (await guild_service.get_channels()).channel_public)

        found = False
        async for message in public_chan.history(limit=200):
            if message.author.id != ctx.me.id:
                continue
            if len(message.embeds) == 0:
                continue
            embed = message.embeds[0]

            if embed.footer.text is None:
                continue
            if len(embed.footer.text.split(" ")) < 2:
                continue

            if f"#{case_id}" == embed.footer.text.split(" ")[1]:
                for i, field in enumerate(embed.fields):
                    if field.name == "Reason":
                        embed.set_field_at(
                            i, name="Reason", value=new_reason)
                        await message.edit(embed=embed)
                        found = True
        if found:
            await ctx.respond_or_edit(f"We updated the case and edited the embed in {public_chan.mention}.", embed=log, delete_after=10)
        else:
            await ctx.respond_or_edit(f"We updated the case but weren't able to find a corresponding message in {public_chan.mention}!", embed=log, delete_after=10)
            log.remove_author()
            log.set_thumbnail(url=member.display_avatar)
            await public_chan.send(member.mention if not dmed else "", embed=log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Edit case reason")
    @app_commands.describe(member="Member to remove points from")
    @app_commands.describe(points="Amount of points to remove")
    @app_commands.describe(reason="Reason for removing points")
    @transform_context
    async def removepoints(self, ctx: GIRContext, member: ModsAndAboveMember, points: app_commands.Range[int, 1, 600], reason: str) -> None:
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        if points < 1:
            raise commands.BadArgument("Points can't be lower than 1.")

        u = user_service.get_user(id=member.id)
        if u.warn_points - points < 0:
            raise commands.BadArgument(
                message=f"Can't remove {points} points because it would make {member.mention}'s points negative.")

        # passed sanity checks, so update the case in DB
        # remove the warn points from the user in DB
        user_service.inc_points(member.id, -1 * points)

        case = Case(
            _id=await guild_service.get_new_case_id(),
            _type="REMOVEPOINTS",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            punishment=str(points),
            reason=reason,
        )

        # increment DB's max case ID for next case
        await guild_service.inc_case_id()
        # add case to db
        user_service.add_case(member.id, case)

        # prepare log embed, send to #public-mod-logs, user, channel where invoked
        log = prepare_removepoints_log(ctx.author, member, case)
        dmed = await notify_user(member, f"Your points were removed in {ctx.guild.name}.", log)

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, member, log, dmed)


async def setup(bot):
    await bot.add_cog(ModActions(bot))
