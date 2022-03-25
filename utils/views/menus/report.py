import asyncio
from enum import Enum

import discord
import pytimeparse
from data.services.guild_service import guild_service
from discord import ui
from discord.ext.commands import Context
from utils import BlooContext
from utils.framework import gatekeeper
from utils.mod import ban, mute, unmute, warn
from .report_action import ReportActionReason, ModAction

class ReportActions(ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=None)
        self.target_member = target_member

    async def interaction_check(self, interaction: discord.Interaction):
        if not gatekeeper.has(self.target_member.guild, interaction.user, 5):
            return False
        return True

    @ui.button(emoji="✅", label="Dismiss", style=discord.ButtonStyle.primary)
    async def dismiss(self, _: ui.Button, interaction: discord.Interaction):
        await interaction.message.delete()
        self.stop()

    @ui.button(emoji="⚠️", label="Warn", style=discord.ButtonStyle.primary)
    async def warn(self, _: ui.Button, interaction: discord.Interaction):
        view = ReportActionReason(target_member=self.target_member, mod=interaction.user, mod_action=ModAction.WARN)
        await interaction.response.send_message(embed=discord.Embed(description=f"{interaction.user.mention}, choose a warn reason for {self.target_member.mention}.", color=discord.Color.blurple()), view=view)
        await view.wait()
        if view.success:
            await interaction.message.delete()
        else:
            await interaction.delete_original_message()
        self.stop()

    @ui.button(emoji="❌", label="Ban", style=discord.ButtonStyle.primary)
    async def ban(self, _: ui.Button, interaction: discord.Interaction):
        view = ReportActionReason(target_member=self.target_member, mod=interaction.user, mod_action=ModAction.BAN)
        await interaction.response.send_message(embed=discord.Embed(description=f"{interaction.user.mention}, choose a ban reason for {self.target_member.mention}.", color=discord.Color.blurple()), view=view)
        await view.wait()
        if view.success:
            await interaction.message.delete()
        else:
            await interaction.delete_original_message()
        self.stop()

    @ui.button(emoji="🆔", label="Post ID", style=discord.ButtonStyle.primary)
    async def id(self, _: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(self.target_member.id)
        await asyncio.sleep(10)
        await interaction.delete_original_message()

    @ui.button(emoji="🧹", label="Clean up", style=discord.ButtonStyle.primary)
    async def purge(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.channel.purge(limit=100)
        self.stop()

    @ui.button(emoji="🔎", label="Claim report", style=discord.ButtonStyle.primary)
    async def claim(self, button: ui.Button, interaction: discord.Interaction):
        report_embed = interaction.message.embeds[0]
        if "(claimed)" in report_embed.title:
            ctx = BlooContext(interaction)
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