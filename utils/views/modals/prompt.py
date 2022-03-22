import discord

from utils import BlooContext


class GenericDescriptionModal(discord.ui.Modal):
    def __init__(self, ctx: BlooContext, author: discord.Member, title: str, label: str = "Description", placeholder: str = "Please enter a description", prefill: str = ""):
        self.ctx = ctx
        self.author = author
        self.value = None

        super().__init__(title=title)

        self.add_item(
            discord.ui.TextInput(
                label=label,
                placeholder=placeholder,
                style=discord.TextStyle.long,
                default=prefill
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return

        self.ctx.interaction = interaction
        self.value = self.children[0].value

        self.stop()
