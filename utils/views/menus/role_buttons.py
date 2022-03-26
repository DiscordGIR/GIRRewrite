import discord

import re
from itertools import takewhile

def derive_label(string):
    enders = {
        "AppleEventNews": " ",
        "SubredditNews": " ",
        "CommunityEvents": " ",
        "CommunityEvents": " ",
        "Giveaway": "Notifications",
        "OtherUpdates": " "
    }

    if string == "iPadOS":
        return "iPadOS Updates"

    starter = str("".join(list(takewhile(lambda x: x.islower(), string))))

    middle = " ".join(re.findall(
        r'[A-Z0-9](?:[a-z0-9]+|[A-Z0-9]*(?=[A-Z0-9]|$))', string))
    return f"{starter}{middle} {enders.get(string) or 'Updates'}"


class ReactionRoleButton(discord.ui.Button):
    def __init__(self, role: discord.Role, emoji: discord.Emoji):
        super().__init__(label=derive_label(role.name), style=discord.ButtonStyle.primary, emoji=emoji, custom_id=str(role.id))

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        role = interaction.guild.get_role(int(self.custom_id))
        if role is None:
            return

        await interaction.response.defer(ephemeral=True)
        if role not in user.roles:
            await user.add_roles(role)
            await interaction.followup.send(f"{self.emoji} You have been given the {role.mention} role", ephemeral=True)
        else:
            await user.remove_roles(role)
            await interaction.followup.send(f"{self.emoji} You have removed the {role.mention} role", ephemeral=True)
