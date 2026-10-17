"""Moderator controls for image antiraid reports."""

import asyncio
import io

import discord
from utils import cfg, logger
from utils.framework import check_invokee, gatekeeper
from utils.mod import ban


class AntiRaidReportActions(discord.ui.View):
    def __init__(self, target_member):
        super().__init__(timeout=None)
        self.target_member = target_member
        self.lock = asyncio.Lock()
        self.resolved = False

    async def interaction_check(self, interaction):
        if interaction.guild is None or not gatekeeper.has(interaction.guild, interaction.user, 5):
            await interaction.response.send_message("Not allowed", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban_member(self, interaction, button):
        await interaction.response.defer()
        async with self.lock:
            if self.resolved:
                return
            try:
                # GIR's helper records the case, notifies the user, updates the
                # ban cache and sends the normal public moderation log.
                target = interaction.guild.get_member(self.target_member.id)
                if target is None:
                    target = await interaction.client.fetch_user(self.target_member.id)
                await check_invokee(interaction, target)
                await ban(interaction, target, mod=interaction.user, reason="compromised account")
            except Exception:
                logger.exception("Failed to ban member from antiraid report")
                await interaction.followup.send("I wasn't able to complete the ban. The report is still available.", ephemeral=True)
                return
            self.resolved = True
            await interaction.message.delete()
            self.stop()

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction, button):
        await interaction.response.defer()
        async with self.lock:
            if self.resolved:
                return
            await interaction.message.delete()
            self.resolved = True
            self.stop()


async def report_antiraid(message, *, title, trigger, reason, actions, evidence=()):
    channel = message.guild.get_channel(cfg.channels.reports)
    if channel is None:
        return False

    # Discord.py's initial member chunk and presence events maintain this cache.
    # Avoid requesting every guild member again for each individual report.
    role = message.guild.get_role(cfg.roles.moderator)
    online = [member for member in role.members if member.status == discord.Status.online] if role else []
    ping = " ".join(member.mention for member in online) or f"<@&{cfg.roles.moderator}>"
    embed = discord.Embed(title=title, color=discord.Color.red(), timestamp=discord.utils.utcnow())
    for name, value in (
        ("User", f"{message.author.mention} ({message.author.id})"),
        ("Channel", message.channel.mention), ("Trigger", trigger), ("Details", reason),
    ):
        embed.add_field(name=name, value=value[:1024], inline=False)
    embed.add_field(name="Action", value=actions, inline=False)
    embeds = [embed]
    files = []
    for i, (filename, buffer) in enumerate(evidence):
        files.append(discord.File(io.BytesIO(buffer), filename=filename))
        if i:
            embeds.append(discord.Embed(url="https://discord.com"))
        if len(evidence) > 1:
            embeds[i].url = "https://discord.com"
        embeds[i].set_image(url=f"attachment://{filename}")
    await channel.send(
        ping, embeds=embeds, files=files, view=AntiRaidReportActions(message.author),
        allowed_mentions=discord.AllowedMentions(
            everyone=False, users=online, roles=[discord.Object(cfg.roles.moderator)], replied_user=False
        ),
    )
    return True
