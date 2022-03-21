from typing import Dict
import discord
from discord import app_commands

from utils.views import get_ios_cfw, transform_groups

class DeviceTransformer(app_commands.Transformer):
    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> Dict:
        response = await get_ios_cfw()
        device_groups = response.get("group")

        transformed_groups = transform_groups(device_groups)
        devices = [group for group in transformed_groups if group.get(
            'name').lower() == value.lower() or value.lower() in [x.lower() for x in group.get('devices')]]

        if not devices:
            raise app_commands.TransformerError("No device found with that name.")

        return devices[0]

class VersionOnDeviceTransformer(app_commands.Transformer):
    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> Dict:
        device = interaction.namespace["device"]
        if device is None:
            raise app_commands.TransformerError("No device found with that name.")

        response = await get_ios_cfw()
        board = device.get("devices")[0]
        ios = response.get("ios")

        ios = [i for _, i in ios.items()]
        version = value.replace("iOS ", "")
        firmware = [v for v in ios if board in v.get(
            'devices') and version == v.get('version') or version.lower() == v.get("uniqueBuild").lower()]

        if not firmware:
            raise app_commands.TransformerError("No firmware found with that version.")

        return firmware[0]