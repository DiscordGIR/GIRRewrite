from typing import Dict, Union

import discord
import pytimeparse
from discord import AppCommandOptionType, app_commands
from discord.ext import commands
from utils import get_ios_cfw, transform_groups
from utils.framework import PermissionsFailure


async def get_device(value):
    response = await get_ios_cfw()
    device_groups = response.get("group")

    transformed_groups = transform_groups(device_groups)
    devices = [group for group in transformed_groups if group.get(
        'name').lower() == value.lower() or value.lower() in [x.lower() for x in group.get('devices')]]

    if not devices:
        raise app_commands.TransformerError(
            "No device found with that name.")

    return devices[0]

class DeviceTransformer(app_commands.Transformer):
    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str):
        return await get_device(value)


class VersionOnDevice(app_commands.Transformer):
    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str):
        device = interaction.namespace["device"]
        if device is None:
            raise app_commands.TransformerError(
                "No device found with that name.")

        response = await get_ios_cfw()
        if isinstance(device, str):
            board = await get_device(device)
        board = board.get("devices")[0]

        ios = response.get("ios")

        ios = [i for _, i in ios.items()]
        version = value
        for os_version in ["iOS", "tvOS", "watchOS"]:
            version = version.replace(os_version + " ", "")
        firmware = [v for v in ios if board in v.get(
            'devices') and version == v.get('version') or version.lower() == v.get("uniqueBuild").lower()]
        if not firmware:
            raise app_commands.TransformerError(
                "No firmware found with that version.")

        return firmware[0]


class Duration(app_commands.Transformer):
    @classmethod
    async def transform(cls, _: discord.Interaction, value: str):
        try:
            value = pytimeparse.parse(value)
        except ValueError:
            raise app_commands.TransformerError(
                f"Could not parse {value} as a duration.")
        return value


class ModsAndAboveMember(app_commands.Transformer):
    @classmethod
    def type(cls) -> AppCommandOptionType:
        return AppCommandOptionType.user

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> discord.Member:
        await app_commands.transformers.MemberTransformer.transform(interaction, value)
        await check_invokee(interaction, value)

        return value


class ModsAndAboveMemberOrUser(app_commands.Transformer):
    @classmethod
    def type(cls) -> AppCommandOptionType:
        return AppCommandOptionType.user

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> Union[discord.Member, discord.User]:
        await check_invokee(interaction, value)

        return value


class UserOnly(app_commands.Transformer):
    @classmethod
    def type(cls) -> AppCommandOptionType:
        return AppCommandOptionType.user

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> discord.User:
        if isinstance(value, discord.Member):
            raise PermissionsFailure(
                "You can't call this command on guild members!")

        return value


async def check_invokee(interaction: discord.Interaction, user: discord.Member):
    if isinstance(user, discord.Member):
        if user.id == interaction.user.id:
            raise PermissionsFailure("You can't call that on yourself.")

        if user.id == interaction.client.user.id:
            raise PermissionsFailure("You can't call that on me :(")

        if user:
            if user.top_role >= interaction.user.top_role:
                raise PermissionsFailure(
                    message=f"{user.mention}'s top role is the same or higher than yours!")


class ImageAttachment(app_commands.Transformer):
    @classmethod
    def type(cls) -> AppCommandOptionType:
        return AppCommandOptionType.attachment

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> discord.Attachment:
        if value is None:
            return

        image = await app_commands.transformers.passthrough_transformer(AppCommandOptionType.attachment).transform(interaction, value)
        _type = image.content_type
        if _type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            raise app_commands.TransformerError("Attached file was not an image.")

        return image
