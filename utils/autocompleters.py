from typing import List
import discord
from discord import app_commands
from discord.ext.commands import Command

async def command_list_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    commands: List[Command] = interaction.client.commands
    return [ app_commands.Choice(name=command.name, value=command.name) for command in commands if current.lower() in command.name.lower() ]