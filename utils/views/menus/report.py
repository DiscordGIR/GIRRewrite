import asyncio
from typing import Union

import discord
import pytimeparse
from data.services import user_service
from data.services.guild_service import guild_service
from discord import ui
from utils import GIRContext, cfg
from utils.framework import gatekeeper
from utils.mod import ban, mute, unmute
from utils.views.modals.prompt import GenericDescriptionModal

from .report_action import ModAction, ReportActionReason


async def report(bot: discord.Client, message: discord.Message, word: str, invite=None):
    """Deals with a report

    Parameters
    ----------
    bot : discord.Client
        "Bot object"
    message : discord.Message
        "Filtered message"
    word : str
        "Filtered word"
    invite : bool
        "Was the filtered word an invite?"

    """
    db_guild = await guild_service.get_roles_and_channels()
    channel = message.guild.get_channel(db_guild.channel_reports)

    ping_string = await prepare_ping_string(db_guild, message)
    view = ReportActions(target_member=message.author)

    if invite:
        embed = await prepare_embed(message, word, title="Invite filter")
        await channel.send(f"{ping_string}\nMessage contained invite: {invite}", embed=embed, view=view)
    else:
        embed = await prepare_embed(message, word)
        await channel.send(ping_string, embed=embed, view=view)


async def manual_report(mod: discord.Member, target: Union[discord.Message, discord.Member] = None):
    """Deals with a report

    Parameters
    ----------
    bot : discord.Client
        "Bot object"
    message : discord.Message
        "Filtered message"
    mod : discord.Member
        "The moderator that started this report

    """
    db_guild = await guild_service.get_channels()
    channel = target.guild.get_channel(db_guild.channel_reports)

    ping_string = f"{mod.mention} reported a member"
    if isinstance(target, discord.Message):
        view = ReportActions(target.author)
    else:
        view = ReportActions(target)

    embed = await prepare_embed(target, title="A moderator reported a member")
    await channel.send(ping_string, embed=embed, view=view)


async def report_raid_phrase(bot: discord.Client, message: discord.Message, domain: str):
    """Deals with a report

    Parameters
    ----------
    bot : discord.Client
        "Bot object"
    message : discord.Message
        "Filtered message"
    word : str
        "Filtered word"
    invite : bool
        "Was the filtered word an invite?"

    """
    db_guild = await guild_service.get_roles_and_channels()
    channel = message.guild.get_channel(db_guild.channel_reports)

    ping_string = await prepare_ping_string(db_guild, message)
    view = RaidPhraseReportActions(message.author, domain)

    embed = await prepare_embed(
        message, domain, title=f"Possible new raid phrase detected\n{domain}")
    await channel.send(ping_string, embed=embed, view=view)


async def report_spam(bot, msg, user, title):
    db_guild = await guild_service.get_roles_and_channels()
    channel = msg.guild.get_channel(db_guild.channel_reports)
    ping_string = await prepare_ping_string(db_guild, msg)

    view = SpamReportActions(user)
    embed = await prepare_embed(msg, title=title)

    await channel.send(ping_string, embed=embed, view=view)


async def report_raid(user, msg=None):
    embed = discord.Embed()
    embed.title = "Possible raid occurring"
    embed.description = "The raid filter has been triggered 5 or more times in the past 10 seconds. I am automatically locking all the channels. Use `/unfreeze` when you're done."
    embed.color = discord.Color.red()
    embed.set_thumbnail(url=user.display_avatar)
    embed.add_field(name="Member", value=f"{user} ({user.mention})")
    if msg is not None:
        embed.add_field(name="Message", value=msg.content, inline=False)

    db_guild = await guild_service.get_roles_and_channels()
    reports_channel = user.guild.get_channel(db_guild.channel_reports)
    await reports_channel.send(f"<@&{db_guild.role_moderator}>", embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))


async def prepare_ping_string(db_guild, message):
    """Prepares modping string

    Parameters
    ----------
    db_guild
        "Guild DB"
    message : discord.Message
        "Message object"

    """
    ping_string = ""
    if cfg.dev:
        return ping_string

    role = message.guild.get_role(db_guild.role_moderator)
    for member in role.members:
        offline_ping = (await user_service.get_user(member.id)).offline_report_ping
        if member.status == discord.Status.online or offline_ping:
            ping_string += f"{member.mention} "

    return ping_string


async def prepare_embed(target: Union[discord.Message, discord.Member], word: str = None, title="Word filter"):
    """Prepares embed

    Parameters
    ----------
    message : discord.Message
        "Message object"
    word : str
        "Filtered word"
    title : str
        "Embed title"

    """
    if isinstance(target, discord.Message):
        member = target.author
    else:
        member = target

    user_info = await user_service.get_user(member.id)
    rd = user_service.rundown(member.id)
    rd_text = ""
    for r in rd:
        if r._type == "WARN":
            r.punishment += " points"
        rd_text += f"**{r._type}** - {r.punishment} - {r.reason} - {discord.utils.format_dt(r.date, style='R')}\n"

    embed = discord.Embed(title=title)
    embed.color = discord.Color.red()

    embed.set_thumbnail(url=member.display_avatar)
    embed.add_field(name="Member", value=f"{member} ({member.mention})")
    if isinstance(target, discord.Message):
        embed.add_field(name="Channel", value=target.channel.mention)

        if len(target.content) > 400:
            target.content = target.content[0:400] + "..."

    if word is not None:
        embed.add_field(name="Message", value=discord.utils.escape_markdown(
            target.content) + f"\n\n[Link to message]({target.jump_url}) | Filtered word: **{word}**", inline=False)
    else:
        if isinstance(target, discord.Message):
            embed.add_field(name="Message", value=discord.utils.escape_markdown(
                target.content) + f"\n\n[Link to message]({target.jump_url})", inline=False)
    embed.add_field(
        name="Join date", value=f"{discord.utils.format_dt(member.joined_at, style='F')} ({discord.utils.format_dt(member.joined_at, style='R')})", inline=True)
    embed.add_field(name="Created",
                    value=f"{discord.utils.format_dt(member.created_at, style='F')} ({discord.utils.format_dt(member.created_at, style='R')})", inline=True)

    embed.add_field(name="Warn points",
                    value=user_info.warn_points, inline=True)

    reversed_roles = member.roles
    reversed_roles.reverse()

    roles = ""
    for role in reversed_roles[0:4]:
        if role != member.guild.default_role:
            roles += role.mention + " "
    roles = roles.strip() + "..."

    embed.add_field(
        name="Roles", value=roles if roles else "None", inline=False)

    if len(rd) > 0:
        embed.add_field(name=f"{len(rd)} most recent cases",
                        value=rd_text, inline=True)
    else:
        embed.add_field(name=f"Recent cases",
                        value="This user has no cases.", inline=True)
    return embed


class ReportActions(ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=None)
        self.target_member = target_member

    async def interaction_check(self, interaction: discord.Interaction):
        if not gatekeeper.has(self.target_member.guild, interaction.user, 5):
            return False
        return True

    @ui.button(emoji="✅", label="Dismiss", style=discord.ButtonStyle.primary)
    async def dismiss(self, interaction: discord.Interaction, _: ui.Button):
        await interaction.message.delete()
        self.stop()

    @ui.button(emoji="⚠️", label="Warn", style=discord.ButtonStyle.primary)
    async def warn(self, interaction: discord.Interaction, _: ui.Button):
        view = ReportActionReason(
            target_member=self.target_member, mod=interaction.user, mod_action=ModAction.WARN)
        await interaction.response.send_message(embed=discord.Embed(description=f"{interaction.user.mention}, choose a warn reason for {self.target_member.mention}.", color=discord.Color.blurple()), view=view)
        await view.wait()
        if view.success:
            await interaction.message.delete()
            self.stop()
        else:
            await interaction.delete_original_message()

    @ui.button(emoji="❌", label="Ban", style=discord.ButtonStyle.primary)
    async def ban(self, interaction: discord.Interaction, _: ui.Button):
        view = ReportActionReason(
            target_member=self.target_member, mod=interaction.user, mod_action=ModAction.BAN)
        await interaction.response.send_message(embed=discord.Embed(description=f"{interaction.user.mention}, choose a ban reason for {self.target_member.mention}.", color=discord.Color.blurple()), view=view)
        await view.wait()
        if view.success:
            await interaction.message.delete()
        else:
            await interaction.delete_original_message()
        self.stop()

    @ui.button(emoji="🆔", label="Post ID", style=discord.ButtonStyle.primary)
    async def id(self, interaction: discord.Interaction, _: ui.Button):
        await interaction.response.send_message(self.target_member.id)
        await asyncio.sleep(10)
        await interaction.delete_original_message()

    @ui.button(emoji="🧹", label="Clean up", style=discord.ButtonStyle.primary)
    async def purge(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.channel.purge(limit=100)
        self.stop()

    @ui.button(emoji="🔎", label="Claim report", style=discord.ButtonStyle.primary)
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        report_embed = interaction.message.embeds[0]
        if "(claimed)" in report_embed.title:
            ctx = GIRContext(interaction)
            await ctx.send_error(f"{interaction.user.mention}, this report has already been claimed.", whisper=True)
            return

        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = f"{interaction.user.mention} is looking into {self.target_member.mention}'s report!"
        await interaction.response.send_message(embed=embed)
        report_embed.color = discord.Color.orange()

        report_embed.title = f"{report_embed.title} (claimed)"
        await interaction.message.edit(embed=report_embed)

        await asyncio.sleep(10)
        await interaction.delete_original_message()


class RaidPhraseReportActions(ui.View):
    def __init__(self, author: discord.Member, domain: str):
        super().__init__(timeout=None)
        self.target_member = author
        self.domain = domain
        
    async def interaction_check(self, interaction: discord.Interaction):
        if not gatekeeper.has(self.target_member.guild, interaction.user, 5):
            return False
        return True

    @ui.button(emoji="✅", label="Dismiss", style=discord.ButtonStyle.primary)
    async def dismiss(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await unmute(interaction, self.target_member, mod=interaction.user, reason="Reviewed by a moderator.")
        except Exception:
            ctx = GIRContext(interaction)
            await ctx.send_warning("I wasn't able to unmute them.", delete_after=5)
        finally:
            await interaction.message.delete()
            self.stop()
        
    @ui.button(emoji="💀", label="Ban and add raidphrase", style=discord.ButtonStyle.primary)
    async def ban(self, interaction: discord.Interaction, button: ui.Button):
        ctx = GIRContext(interaction)
        try:
            await ban(interaction, self.target_member, mod=interaction.user, reason="Raid phrase detected")
            self.ctx.bot.ban_cache.ban(self.target_member.id)
        except Exception:
            await ctx.send_warning("I wasn't able to ban them.", delete_after=5)

        done = await guild_service.add_raid_phrase(self.domain)
        if done:
            await ctx.send_success(f"{self.domain} was added to the raid phrase list.", delete_after=5)
        else:
            await ctx.send_warning(f"{self.domain} was already in the raid phrase list.", delete_after=5)

        await interaction.message.delete()
        self.stop()


class SpamReportActions(ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=None)
        self.target_member = author

    async def interaction_check(self, interaction: discord.Interaction):
        if not gatekeeper.has(self.target_member.guild, interaction.user, 5):
            return False
        return True

    @ui.button(emoji="✅", label="Dismiss", style=discord.ButtonStyle.primary)
    async def dismiss(self, interaction: discord.Interaction, _: ui.Button):
        try:
            await unmute(interaction, self.target_member, interaction.guild.me, reason="Reviewed by a moderator.")
        except Exception:
            ctx = GIRContext(interaction)
            await ctx.send_warning("I wasn't able to unmute them.", delete_after=5)
        finally:
            await interaction.message.delete()
            self.stop()
        
    @ui.button(emoji="💀", label="Ban", style=discord.ButtonStyle.primary)
    async def ban(self, interaction: discord.Interaction, _: ui.Button):
        try:
            await ban(interaction, self.target_member, mod=interaction.user, reason="Spam detected")
        except Exception:
            ctx = GIRContext(interaction)
            await ctx.send_warning("I wasn't able to ban them.")
        finally:
            await interaction.message.delete()
            self.stop()
        
    @ui.button(emoji="⚠️", label="Temporary mute", style=discord.ButtonStyle.primary)
    async def mute(self, interaction: discord.Interaction, button: ui.Button):
        ctx = GIRContext(interaction)
        view = GenericDescriptionModal(ctx, interaction.user, title=f"Mute duration for {self.target_member}", label="How long should they be muted for?", placeholder="i.e 1h, 1d, ...")
        await interaction.response.send_modal(view)
        await view.wait()
        if view.value is not None:
            try:
                duration = pytimeparse.parse(view.value)
            except ValueError:
                await ctx.send_warning("I couldn't parse that duration.")

            await self.target_member.edit(timed_out_until=None)
            ctx.bot.tasks.cancel_unmute(self.target_member.id)
            await mute(ctx, self.target_member, mod=interaction.user, dur_seconds=duration, reason="A moderator has reviewed your spam report.")
            await interaction.message.delete()
            self.stop()
