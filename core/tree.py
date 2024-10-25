import discord
from discord import app_commands

from utils import GIRContext
from utils.framework import gatekeeper, find_triggered_filters


class MyTree(app_commands.CommandTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.bot:
            return False

        if gatekeeper.has(interaction.user.guild, interaction.user, 6):
            return True

        command = interaction.command

        if isinstance(interaction.command, discord.app_commands.ContextMenu):
            return True

        if command is None or interaction.type != discord.InteractionType.application_command:
            return True

        options = interaction.data.get("options")
        if options is None or not options:
            return True

        message_content = ""
        for option in options:
            if option.get("type") == 1:
                for sub_option in option.get("options"):
                    message_content += str(sub_option.get("value")) + " "
            else:
                message_content += str(option.get("value")) + " "

        triggered_words = await find_triggered_filters(
            message_content, interaction.user)

        if triggered_words:
            ctx = GIRContext(interaction)
            await ctx.send_error("Your interaction contained a filtered word. Aborting!", whisper=True)
            return

        return True
