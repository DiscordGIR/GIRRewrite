"""Server-aware engagement and moderation tools."""
from __future__ import annotations

import hashlib
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils import cfg, logger



QUESTIONS = (
    "What small thing made your day better?", "What game deserves a remake?", "What is your perfect weekend?",
    "Which skill would you learn instantly?", "What song never gets old?", "What is your favorite comfort food?",
)
WOULD_YOU_RATHER = (
    "Would you rather explore space or the deepest ocean?", "Would you rather have unlimited travel or unlimited food?",
    "Would you rather always be ten minutes early or never wait in line?", "Would you rather relive one day or skip one bad day?",
)
COMPLIMENTS = ("brings great energy", "makes this server more fun", "has excellent taste", "is someone people can count on")


class ServerSuite(commands.Cog):
    engage = app_commands.Group(name="engage", description="Games and friendly community activities", guild_ids=[cfg.guild_id])
    modtools = app_commands.Group(name="modtools", description="Extra tools for moderators", guild_ids=[cfg.guild_id],
                                  default_permissions=discord.Permissions(manage_messages=True))

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @engage.command(name="eightball", description="Ask GIR a yes-or-no question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answer = random.choice(("Yes.", "Probably.", "Signs point to yes.", "Ask again later.", "Probably not.", "No."))
        await interaction.response.send_message(f"🎱 **{question[:300]}**\n{answer}")

    @engage.command(name="question", description="Post a conversation starter")
    async def question(self, interaction: discord.Interaction):
        await interaction.response.send_message("💬 " + random.choice(QUESTIONS))

    @engage.command(name="would-you-rather", description="Post a would-you-rather question")
    async def would_you_rather(self, interaction: discord.Interaction):
        await interaction.response.send_message("🤔 " + random.choice(WOULD_YOU_RATHER))

    @engage.command(name="compliment", description="Send a friendly compliment")
    async def compliment(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"✨ {member.mention} {random.choice(COMPLIMENTS)}.")

    @engage.command(name="highfive", description="Give someone a high five")
    async def highfive(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"🙌 {interaction.user.mention} high-fived {member.mention}!")

    @engage.command(name="hug", description="Send someone a friendly hug")
    async def hug(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"🫂 {interaction.user.mention} sent {member.mention} a hug.")

    @engage.command(name="match", description="Calculate a repeatable friendship score")
    async def match(self, interaction: discord.Interaction, first: discord.Member, second: discord.Member):
        pair = ":".join(map(str, sorted((first.id, second.id)))).encode()
        score = int(hashlib.sha256(pair).hexdigest()[:8], 16) % 101
        await interaction.response.send_message(f"💚 {first.mention} + {second.mention}: **{score}%** match")

    @engage.command(name="decide", description="Choose fairly from a list separated by commas")
    async def decide(self, interaction: discord.Interaction, choices: str):
        items = [item.strip() for item in choices.split(",") if item.strip()]
        if len(items) < 2:
            await interaction.response.send_message("Give me at least two choices separated by commas.", ephemeral=True); return
        await interaction.response.send_message(f"🎯 GIR chooses **{random.choice(items)}**")

    @engage.command(name="random-member", description="Choose a random non-bot member")
    async def random_member(self, interaction: discord.Interaction):
        choices = [member for member in interaction.guild.members if not member.bot]
        if not choices:
            await interaction.response.send_message("I could not find an eligible member.", ephemeral=True); return
        await interaction.response.send_message(f"🎉 {random.choice(choices).mention} was chosen!")

    @modtools.command(name="role-add", description="Give a manageable role to a member")
    async def role_add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role or role.is_default() or role.managed:
            await interaction.response.send_message("GIR cannot manage that role. Move GIR above it or choose another role.", ephemeral=True); return
        await member.add_roles(role, reason=f"Added by {interaction.user}")
        await interaction.response.send_message(f"Added {role.mention} to {member.mention}.", ephemeral=True)

    @modtools.command(name="role-remove", description="Remove a manageable role from a member")
    async def role_remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role or role.is_default() or role.managed:
            await interaction.response.send_message("GIR cannot manage that role. Move GIR above it or choose another role.", ephemeral=True); return
        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(f"Removed {role.mention} from {member.mention}.", ephemeral=True)

    @modtools.command(name="permissions", description="Explain what GIR can do to a member")
    async def permissions(self, interaction: discord.Interaction, member: discord.Member):
        manageable = member != interaction.guild.owner and member.top_role < interaction.guild.me.top_role
        await interaction.response.send_message(
            f"**{member.display_name}**\nTop role: {member.top_role.mention}\n"
            f"GIR can moderate this member: **{'Yes' if manageable else 'No'}**\n"
            f"Administrator: **{'Yes' if member.guild_permissions.administrator else 'No'}**", ephemeral=True)

    @modtools.command(name="clear-reactions", description="Remove every reaction from a message")
    async def clear_reactions(self, interaction: discord.Interaction, message_id: str):
        if not message_id.isdigit():
            await interaction.response.send_message("Enter a numeric message ID.", ephemeral=True); return
        try:
            message = await interaction.channel.fetch_message(int(message_id)); await message.clear_reactions()
        except discord.HTTPException:
            await interaction.response.send_message("I could not find that message or clear its reactions.", ephemeral=True); return
        await interaction.response.send_message("Reactions cleared.", ephemeral=True)

    @modtools.command(name="role-members", description="List members who have a role")
    async def role_members(self, interaction: discord.Interaction, role: discord.Role):
        names = [member.mention for member in role.members]
        text = " ".join(names[:80]) or "No cached members have this role."
        if len(names) > 80:
            text += f"\n…and {len(names) - 80} more."
        await interaction.response.send_message(f"**{role.name} · {len(names)} members**\n{text}"[:2000], ephemeral=True)

    @modtools.command(name="channel-info", description="Show a channel's IDs, topic, and rate limit")
    async def channel_info(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(
            f"**#{channel.name}**\nID: `{channel.id}`\nCategory: {channel.category.name if channel.category else 'None'}\n"
            f"Slow mode: {channel.slowmode_delay} seconds\nTopic: {channel.topic or 'None'}", ephemeral=True)

    @modtools.command(name="bots", description="List bot accounts currently in the server cache")
    async def bots(self, interaction: discord.Interaction):
        bots = [member for member in interaction.guild.members if member.bot]
        text = "\n".join(f"• {member} · `{member.id}`" for member in bots[:50]) or "No bots found."
        await interaction.response.send_message(f"**Bots · {len(bots)}**\n{text}"[:2000], ephemeral=True)


async def setup(bot):
    await bot.add_cog(ServerSuite(bot))
