import re
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from utils import (GIRContext, cfg, get_ios_cfw, transform_context,
                   transform_groups)
from utils.framework import (DeviceTransformer, VersionOnDevice,
                             always_whisper,
                             ensure_invokee_role_lower_than_bot, whisper)
from utils.views import (Confirm, device_autocomplete,
                         ios_on_device_autocomplete)
from utils.views.autocompleters import jailbreakable_device_autocomplete


class Devices(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.devices_test = re.compile(r'^.+ \[.+\,.+\]$')
        self.devices_remove_re = re.compile(r'\[.+\,.+\]$')

    device = app_commands.Group(
        name="device", description="Interact with tags", guild_ids=[cfg.guild_id])

    @ensure_invokee_role_lower_than_bot()
    @device.command(description="Add device to nickname")
    @app_commands.describe(device="Name of your device")
    @app_commands.autocomplete(device=jailbreakable_device_autocomplete)
    @app_commands.describe(version="Device OS version")
    @app_commands.autocomplete(version=ios_on_device_autocomplete)
    @transform_context
    @always_whisper
    async def add(self, ctx: GIRContext, device: DeviceTransformer, version: VersionOnDevice) -> None:
        new_nick = ctx.author.display_name
        # check if user already has a device in their nick
        if re.match(self.devices_test, ctx.author.display_name):
            # they already have a device set
            view = Confirm(ctx, true_response="Alright, we'll swap your device!",
                           false_response="Cancelled adding device to your name.")
            await ctx.respond('You already have a device in your nickname. Would you like to replace it?', view=view, ephemeral=True)
            # Wait for the View to stop listening for input...
            await view.wait()
            change_name = view.value

            if change_name:
                # user wants to remove existing device, let's do that
                new_nick = re.sub(self.devices_remove_re, "",
                                  ctx.author.display_name).strip()
                if len(new_nick) > 32:
                    raise commands.BadArgument("Nickname too long")
            else:
                return

        response = await get_ios_cfw()

        # change the user's nickname!
        firmware = version.get("version")
        firmware = re.sub(r' beta (\d+)', r'b\1', firmware)
        device_id = device.get("devices")[0]
        detailed_device = [ d for d in response.get("device") if d.get('key') == device_id ][0]
        name = detailed_device["soc"]
        new_nick = f"{new_nick} [{name}, {firmware}]"

        if len(new_nick) > 32:
            raise commands.BadArgument(
                f"Discord's nickname character limit is 32. `{discord.utils.escape_markdown(new_nick)}` is too long.")

        await ctx.author.edit(nick=new_nick)
        await ctx.send_success(f"Changed your nickname to `{discord.utils.escape_markdown(new_nick)}`!")

    @ensure_invokee_role_lower_than_bot()
    @device.command(description="Remove device from nickname")
    @transform_context
    @always_whisper
    async def remove(self, ctx: GIRContext) -> None:
        if not re.match(self.devices_test, ctx.author.display_name):
            raise commands.BadArgument("You don't have a device nickname set!")

        new_nick = re.sub(self.devices_remove_re, "",
                          ctx.author.display_name).strip()
        if len(new_nick) > 32:
            raise commands.BadArgument("Nickname too long")

        await ctx.author.edit(nick=new_nick)
        await ctx.send_success("Removed device from your nickname!")


async def setup(bot):
    await bot.add_cog(Devices(bot))
