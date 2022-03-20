from typing import List

import discord
from discord import app_commands
from discord.ext.commands import Command

from data.services import guild_service


async def command_list_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    commands: List[Command] = interaction.client.commands
    return [app_commands.Choice(name=command.name, value=command.name) for command in commands if current.lower() in command.name.lower()]


async def tags_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    tags = [tag.name.lower() for tag in guild_service.get_guild().tags]
    tags.sort()
    return [app_commands.Choice(name=tag, value=tag) for tag in tags if current.lower() in tag.lower()][:25]

