import asyncio
import re

import discord

from data.model import Case
from data.services import guild_service, user_service
from utils import cfg, logger
from utils.mod.mod_logs import prepare_unban_log


def count_votes(moderators, upvotes, downvotes, abstentions, approve):
    eligible = set(moderators) - set(abstentions)
    supporters = (set(upvotes) - set(downvotes) if approve
                  else set(downvotes) - set(upvotes)) & eligible
    return len(supporters), len(eligible) // 2 + 1


class AppealActions:
    """Route applicant-specific button IDs, including after bot restarts."""

    def __init__(self, bot):
        self.bot = bot
        self.locks = {}

    @staticmethod
    def create_view(user_id, *, disabled=False):
        view = discord.ui.View(timeout=None)
        for action, label, style in (
            ("approve", "Unban", discord.ButtonStyle.success),
            ("deny", "Deny appeal", discord.ButtonStyle.danger),
        ):
            view.add_item(discord.ui.Button(
                label=label, style=style, disabled=disabled,
                custom_id=f"unban_appeal:{action}:{user_id}"))
        return view

    async def handle_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id", "")
        match = re.fullmatch(r"unban_appeal:(approve|deny):([1-9][0-9]{0,19})", custom_id)
        if match is None:
            return
        await self.resolve(interaction, int(match[2]), approve=match[1] == "approve")

    async def resolve(self, interaction, user_id, approve):
        guild = interaction.guild
        if guild is None or guild.id != cfg.ban_appeal_guild_id:
            await interaction.response.send_message("This is not an appeal vote.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.locks.setdefault(interaction.message.id, asyncio.Lock()):
            try:
                await self._resolve(interaction, user_id, approve)
            except Exception:
                logger.exception("Failed to resolve appeal vote %s", interaction.message.id)
                await interaction.followup.send(
                    "The appeal action failed. Check the vote message and bot logs before retrying.",
                    ephemeral=True)

    async def _resolve(self, interaction, user_id, approve):
        guild = interaction.guild
        # Fetch members so permission checks and the denominator reflect current roles.
        members = [member async for member in guild.fetch_members(limit=None)]
        moderators = {member.id for member in members if not member.bot and
                      any(role.id == cfg.ban_appeal_mod_role for role in member.roles)}
        if interaction.user.id not in moderators:
            await interaction.followup.send("Only moderators can resolve appeals.", ephemeral=True)
            return
        message = await interaction.channel.fetch_message(interaction.message.id)
        if message.author.id != self.bot.user.id or not message.embeds:
            await interaction.followup.send("This is not an appeal vote.", ephemeral=True)
            return
        embed = message.embeds[0].copy()
        custom_id = f"unban_appeal:{'approve' if approve else 'deny'}:{user_id}"
        if not any(
            getattr(component, "custom_id", None) == custom_id
            for row in message.components for component in row.children
        ):
            await interaction.followup.send("This is not an appeal vote.", ephemeral=True)
            return
        if embed.title:
            await interaction.followup.send(
                "This appeal has already been resolved or is being processed. Check the recorded outcome.",
                ephemeral=True)
            return
        votes = {emoji: set() for emoji in ("🔺", "🔻", "❌")}
        for reaction in message.reactions:
            if str(reaction.emoji) in votes:
                votes[str(reaction.emoji)] = {user.id async for user in reaction.users(limit=None)}
        support, required = count_votes(moderators, votes["🔺"], votes["🔻"], votes["❌"], approve)
        override = interaction.user.id == cfg.aaron_id
        if not override and support < required:
            await interaction.followup.send(
                f"Majority hasn't been reached yet: {support} supporting vote(s); {required} required.",
                ephemeral=True)
            return
        user = await self.bot.fetch_user(user_id)
        main_guild = self.bot.get_guild(cfg.guild_id)
        if approve and main_guild is None:
            await interaction.followup.send("The main server is unavailable. Please try again later.", ephemeral=True)
            return
        # Persist the claim before side effects. Even a restart must not repeat an action.
        disabled = self.create_view(user_id, disabled=True)
        embed.title = "Appeal processing"
        embed.description = f"{'Unban' if approve else 'Denial'} requested by {interaction.user.mention}."
        await message.edit(embed=embed, view=disabled)
        reason = f"Ban appeal approved by {interaction.user} ({interaction.user.id})"
        if approve:
            try:
                await main_guild.unban(discord.Object(id=user_id), reason=reason)
            except discord.NotFound:
                # Already unbanned: complete the appeal without a duplicate UNBAN case.
                self.bot.ban_cache.unban(user_id)
            except discord.HTTPException:
                embed.title = None
                embed.description = "Unban failed. Resolve the bot's permissions or Discord error, then retry."
                await message.edit(embed=embed, view=self.create_view(user_id))
                raise
            else:
                self.bot.ban_cache.unban(user_id)
                try:
                    db_guild = guild_service.get_guild()
                    case = Case(_id=db_guild.case_id, _type="UNBAN", mod_id=interaction.user.id,
                                mod_tag=str(interaction.user), reason=reason)
                    guild_service.inc_caseid()
                    user_service.add_case(user_id, case)
                    await interaction.channel.send(embed=prepare_unban_log(interaction.user, user, case))
                except Exception:
                    logger.exception("Appeal unban succeeded but case/log failed for %s", user_id)
                    await interaction.followup.send(
                        "The unban succeeded, but recording its case or log failed. "
                        "Please check the moderation history and bot logs and repair the record manually.",
                        ephemeral=True)
        outcome = "approved" if approve else "denied"
        embed.title = f"Appeal {outcome}"
        embed.description = (f"{interaction.user.mention} {outcome} this appeal. "
                             f"Votes: {support}/{required} required."
                             + (" Aaron used the owner override." if override and support < required else ""))
        await message.edit(embed=embed, view=disabled)
        dm = ("Your ban appeal has been approved and you have been unbanned. "
              "You can rejoin the server: https://discord.gg/jb" if approve else
              "Your ban appeal has been denied. Your ban remains in place.")
        try:
            await user.send(dm)
        except discord.HTTPException:
            await interaction.channel.send(
                f"Could not DM <@{user_id}>; their DMs may be closed. They have been left in the appeal server. "
                "Please manually send the following message, then remove them after delivery:\n\n" + dm,
                allowed_mentions=discord.AllowedMentions.none())
        else:
            try:
                await guild.kick(discord.Object(id=user_id), reason=f"Ban appeal {outcome}; DM delivered")
            except discord.NotFound:
                pass
            except discord.HTTPException:
                await interaction.channel.send(
                    f"The outcome DM was delivered to <@{user_id}>, but removal failed. Please remove them manually.",
                    allowed_mentions=discord.AllowedMentions.none())
        await interaction.followup.send(f"Appeal {outcome}. See the thread for delivery details.", ephemeral=True)
