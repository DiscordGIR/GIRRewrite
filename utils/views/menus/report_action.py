from enum import Enum

import discord
from discord import ui
from utils.context import BlooContext

from utils.mod.global_modactions import ban, warn
from utils.views.modals.prompt import GenericDescriptionModal


class ModAction(Enum):
    WARN = 1
    BAN = 2


class ReportActionReason(ui.View):
    def __init__(self, target_member: discord.Member, mod: discord.Member, mod_action: ModAction):
        super().__init__(timeout=20)
        self.target_member = target_member
        self.mod = mod
        self.mod_action = mod_action
        self.success = False

    async def interaction_check(self, interaction: discord.Interaction):
        return self.mod == interaction.user

    @ui.button(label="piracy", style=discord.ButtonStyle.primary)
    async def piracy(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "piracy")

    @ui.button(label="slurs", style=discord.ButtonStyle.primary)
    async def slurs(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "slurs")

    @ui.button(label="filter bypass", style=discord.ButtonStyle.primary)
    async def filter_bypass(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "filter bypass")

    @ui.button(label="rule 1", style=discord.ButtonStyle.primary)
    async def rule_one(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "rule 1")

    @ui.button(label="rule 5", style=discord.ButtonStyle.primary)
    async def rule_five(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "rule 5")

    @ui.button(label="ads", style=discord.ButtonStyle.primary)
    async def ads(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "ads")

    @ui.button(label="scam", style=discord.ButtonStyle.primary)
    async def scam(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "scam")

    @ui.button(label="troll", style=discord.ButtonStyle.primary)
    async def troll(self, interaction: discord.Interaction, button: ui.Button):
        await self.modaction_callback(interaction, "troll")

    @ui.button(emoji="❌", label="Cancel", style=discord.ButtonStyle.primary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.stop()

    async def modaction_callback(self, interaction: discord.Interaction, reason: str):
        if self.mod_action == ModAction.WARN:
            points = await self.prompt_for_points(reason, interaction)
            if points is not None:
                await warn(interaction, self.target_member, interaction.user, self.mod, points, reason)
        else:
            await ban(interaction, self.target_member, self.mod, reason)

        self.success = True
        await interaction.message.delete()
        self.stop()

    async def prompt_for_points(self, reason: str, interaction: discord.Interaction):
        view = PointsView(self.mod)
        await interaction.response.edit_message(embed=discord.Embed(description=f"Warning for `{reason}`. How many points, {self.mod.mention}?", color=discord.Color.blurple()), view=view)
        await view.wait()

        return view.value


class PointsView(ui.View):
    def __init__(self, mod: discord.Member):
        super().__init__(timeout=15)
        self.mod = mod
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction):
        if self.mod != interaction.user:
            return False
        return True

    # async def on_timeout(self) -> None:
    #     try:
    #         await self.points_msg.delete()
    #     except:
    #         pass

    @ui.button(label="50 points", style=discord.ButtonStyle.primary)
    async def fiddy(self, interaction: discord.Interaction, button: ui.Button):
        self.value = 50
        self.stop()

    @ui.button(label="100 points", style=discord.ButtonStyle.primary)
    async def hunnit(self, interaction: discord.Interaction, button: ui.Button):
        self.value = 100
        self.stop()

    @ui.button(label="150 points", style=discord.ButtonStyle.primary)
    async def hunnitfiddy(self, interaction: discord.Interaction, button: ui.Button):
        self.value = 150
        self.stop()

    @ui.button(label="200 points", style=discord.ButtonStyle.primary)
    async def twohunnit(self, interaction: discord.Interaction, button: ui.Button):
        self.value = 200
        self.stop()


class WarnView(ui.View):
    def __init__(self, ctx: BlooContext, member: discord.Member):
        super().__init__(timeout=30)
        self.target_member = member
        self.ctx = ctx

    async def on_timeout(self) -> None:
        await self.ctx.send_warning("Timed out.")

    async def interaction_check(self, interaction: discord.Interaction):
        return self.ctx.author == interaction.user

    @ui.button(label="piracy", style=discord.ButtonStyle.primary)
    async def piracy(self, interaction: discord.Interaction, button: ui.Button):
        await self.ctx.send_success("Okay...")
        self.ctx.interaction = interaction
        await warn(self.ctx, self.target_member, interaction.user, 50, "piracy")
        self.stop()

    @ui.button(label="slurs", style=discord.ButtonStyle.primary)
    async def slurs(self, interaction: discord.Interaction, button: ui.Button):
        await self.ctx.send_success("Okay...")
        self.ctx.interaction = interaction
        await warn(self.ctx, self.target_member, interaction.user, 50, "slurs")
        self.stop()

    @ui.button(label="filter bypass", style=discord.ButtonStyle.primary)
    async def filter_bypass(self, interaction: discord.Interaction, button: ui.Button):
        await self.ctx.send_success("Okay...")
        self.ctx.interaction = interaction
        await warn(self.ctx, self.target_member, interaction.user, 50, "filter bypass")
        self.stop()

    @ui.button(label="rule 5", style=discord.ButtonStyle.primary)
    async def rule5(self, interaction: discord.Interaction, button: ui.Button):
        await self.ctx.send_success("Okay...")
        self.ctx.interaction = interaction
        await warn(self.ctx, self.target_member, interaction.user, 50, "rule 5")
        self.stop()

    @ui.button(label="Other...", style=discord.ButtonStyle.primary)
    async def other(self, interaction: discord.Interaction, button: ui.Button):
        self.ctx.interaction = interaction
        reason = await self.prompt_reason(interaction)
        if reason and reason is not None:
            await warn(self.ctx, self.target_member, interaction.user, 50, reason)
            self.stop()

    @ui.button(emoji="❌", label="cancel", style=discord.ButtonStyle.primary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await self.ctx.send_warning("Cancelled")
        self.stop()

    async def prompt_reason(self, interaction: discord.Interaction):
        view = GenericDescriptionModal(self.ctx, interaction.user, title=f"Warn reason for {self.target_member}", label="Why should we warn them?")
        await interaction.response.send_modal(view)
        await view.wait()
        return view.value

