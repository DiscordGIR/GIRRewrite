import discord
from discord import ui
from utils.context import GIRContext


class Confirm(ui.View):
    def __init__(self, ctx: GIRContext, true_response = None, false_response = None):
        super().__init__(timeout=20)
        self.ctx = ctx
        self.value = None
        self.true_response = true_response
        self.false_response = false_response

    async def on_timeout(self) -> None:
        await self.ctx.send_warning("Timed out.")
        return await super().on_timeout()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @ui.button(label='Yes', style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _: ui.Button):
        self.ctx.interaction = interaction
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @ui.button(label='No', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, _: ui.Button):
        self.ctx.interaction = interaction
        if self.false_response is not None:
            await self.ctx.send_warning(description=self.false_response)
        self.value = False
        self.stop()
