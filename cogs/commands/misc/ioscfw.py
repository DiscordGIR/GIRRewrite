import datetime

import discord
from discord import app_commands
from discord.ext import commands
from utils import (BlooContext, cfg, get_ios_cfw, get_ipsw_firmware_info,
                   transform_context, transform_groups)
from utils.framework import whisper, whisper_in_general
from utils.framework.transformers import (DeviceTransformer,
                                          VersionOnDevice)
from utils.views import (BypassMenu, CIJMenu, bypass_autocomplete,
                         device_autocomplete, ios_beta_version_autocomplete,
                         ios_on_device_autocomplete, ios_version_autocomplete,
                         jb_autocomplete)


def format_bypass_page(ctx, entries, current_page, all_pages):
    ctx.current_bypass = entries[0]
    embed = discord.Embed(title=ctx.app.get(
        "name"), color=discord.Color.blue())
    embed.set_thumbnail(url=ctx.app.get("icon"))

    embed.description = f"You can use **{ctx.current_bypass.get('name')}**!"
    if ctx.current_bypass.get("notes") is not None:
        embed.add_field(name="Note", value=ctx.current_bypass.get('notes'))
        embed.color = discord.Color.orange()
    if ctx.current_bypass.get("version") is not None:
        embed.add_field(name="Supported versions",
                        value=f"This bypass works on versions {ctx.current_bypass.get('version')} of the app")

    embed.set_footer(
        text=f"Powered by ios.cfw.guide • Bypass {current_page} of {len(all_pages)}")
    return embed


async def format_jailbreak_page(ctx, entries, current_page, all_pages):
    jb = entries[0]
    info = jb.get('info')
    info['name'] = jb.get('name')
    ctx.jb_info = info

    color = info.get("color")
    if color is not None:
        color = int(color.replace("#", ""), 16)

    embed = discord.Embed(title="Good news, your device is jailbreakable!",
                          color=color or discord.Color.random())
    embed.description = f"{jb.get('name')} works on {ctx.device} on {ctx.version}!"

    if info is not None:
        embed.set_thumbnail(url=f"https://ios.cfw.guide{info.get('icon')}")

        embed.add_field(
            name="Version", value=info.get("latestVer"), inline=True)

        if info.get("firmwares"):
            soc = f"Works with {info.get('soc')}" if info.get(
                'soc') else ""

            firmwares = info.get("firmwares")
            if len(firmwares) > 2:
                firmwares = ", ".join(firmwares)
            else:
                firmwares = " - ".join(info.get("firmwares"))

            embed.add_field(name="Compatible with",
                            value=f'iOS {firmwares}\n{f"**{soc}**" if soc else ""}', inline=True)
        else:
            embed.add_field(name="Compatible with",
                            value="Unavailable", inline=True)

        embed.add_field(
            name="Type", value=info.get("type"), inline=False)

        if info.get('notes') is not None:
            embed.add_field(
                name="Notes", value=info.get('notes'), inline=False)

        embed.set_footer(
            text=f"Powered by https://appledb.dev • Page {current_page} of {len(all_pages)}")
    else:
        embed.description = "No info available."

    return embed


class iOSCFW(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get info about a jailbreak.")
    @app_commands.describe(name="Name of the jailbreak")
    @app_commands.autocomplete(name=jb_autocomplete)
    @app_commands.describe(user_to_mention="User to ping in response")
    @transform_context
    @whisper_in_general
    async def jailbreak(self, ctx: BlooContext, name: str, user_to_mention: discord.Member = None) -> None:
        response = await get_ios_cfw()

        jbs = [jb for _, jb in response.get(
            "jailbreak").items()]
        matching_jbs = [jb for jb in jbs if jb.get(
            "name").lower() == name.lower()]
        if not matching_jbs:
            raise commands.BadArgument("No jailbreak found with that name.")

        jb = matching_jbs[0]
        info = jb.get('info')

        color = info.get("color")
        if color is not None:
            color = int(color.replace("#", ""), 16)

        embed = discord.Embed(title=jb.get(
            'name'), color=color or discord.Color.random())
        view = discord.ui.View()

        if info is not None:
            embed.set_thumbnail(url=f"https://ios.cfw.guide{info.get('icon')}")

            embed.add_field(
                name="Version", value=info.get("latestVer"), inline=True)

            if info.get("firmwares"):
                soc = f"Works with {info.get('soc')}" if info.get(
                    'soc') else ""

                firmwares = info.get("firmwares")
                if isinstance(firmwares, list):
                    if len(firmwares) > 2:
                        firmwares = ", ".join(firmwares)
                    else:
                        firmwares = " - ".join(info.get("firmwares"))
                else:
                    firmwares = info.get("firmwares")

                embed.add_field(name="Compatible with",
                                value=f'iOS {firmwares}\n{f"**{soc}**" if soc else ""}', inline=True)
            else:
                embed.add_field(name="Compatible with",
                                value="Unavailable", inline=True)

            embed.add_field(
                name="Type", value=info.get("type"), inline=False)

            if info.get("website") is not None:
                view.add_item(discord.ui.Button(label='Website', url=info.get(
                    "website").get("url"), style=discord.ButtonStyle.url))

            if info.get('guide'):
                for guide in info.get('guide'):
                    view.add_item(discord.ui.Button(
                        label=f'{guide.get("name")} Guide', url=f"https://ios.cfw.guide{guide.get('url')}", style=discord.ButtonStyle.url))
            if info.get('notes') is not None:
                embed.add_field(
                    name="Notes", value=info.get('notes'), inline=False)

            embed.set_footer(text="Powered by https://appledb.dev")
        else:
            embed.description = "No info available."

        if user_to_mention is not None:
            title = f"Hey {user_to_mention.mention}, have a look at this!"
        else:
            title = None

        await ctx.respond_or_edit(content=title, embed=embed, ephemeral=ctx.whisper, view=view)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get info about an iOS version.")
    @app_commands.describe(version="Version to get info about")
    @app_commands.autocomplete(version=ios_version_autocomplete)
    @transform_context
    @whisper_in_general
    async def firmware(self, ctx: BlooContext, version: str) -> None:
        response = await get_ios_cfw()
        og_version = version
        for os_version in ["iOS", "tvOS", "watchOS", "audioOS"]:
            version = version.replace(os_version + " ", "")
        ios = response.get("ios")
        ios = [i for _, i in ios.items()]

        ios = [ios for ios in ios if f"{ios.get('osStr')} {ios.get('version')} ({ios.get('build')})" == og_version or ios.get(
            'uniqueBuild').lower() == version.lower() or ios.get('version').lower() == version.lower()]

        if not ios:
            raise commands.BadArgument("No firmware found with that version.")

        matching_ios = ios[0]
        embed, view = await self.do_firmware_response(ctx, matching_ios)
        await ctx.respond(embed=embed, view=view, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get info about a beta iOS version.")
    @app_commands.describe(version="Beta ersion to get info about")
    @app_commands.autocomplete(version=ios_beta_version_autocomplete)
    @transform_context
    @whisper_in_general
    async def betafirmware(self, ctx: BlooContext, version: str) -> None:
        response = await get_ios_cfw()
        og_version = version
        for os_version in ["iOS", "tvOS", "watchOS", "audioOS"]:
            version = version.replace(os_version + " ", "")
        ios = response.get("ios")
        ios = [i for _, i in ios.items()]
        ios = [ios for ios in ios if (f"{ios.get('osStr')} {ios.get('version')} ({ios.get('build')})" == og_version or ios.get(
            'uniqueBuild').lower() == version.lower() or ios.get('version').lower() == version.lower()) and ios.get('beta')]

        if not ios:
            raise commands.BadArgument("No firmware found with that version.")

        matching_ios = ios[0]
        embed, view = await self.do_firmware_response(ctx, matching_ios)
        await ctx.respond(embed=embed, view=view, ephemeral=ctx.whisper)

    async def do_firmware_response(self, ctx, matching_ios):
        embed = discord.Embed(
            title=f"{matching_ios.get('osStr')} {matching_ios.get('version')}")
        embed.add_field(name="Build number",
                        value=matching_ios.get("uniqueBuild"), inline=True)

        embed.add_field(name="Supported devices", value=len(
            matching_ios.get("devices")) or "None found", inline=True)

        release = matching_ios.get("released")
        if release is not None:
            try:
                release_date = datetime.datetime.strptime(release, "%Y-%m-%d")
                embed.add_field(
                    name="Release date", value=f"{discord.utils.format_dt(release_date, 'D')} ({discord.utils.format_dt(release_date, 'R')})", inline=False)
            except ValueError:
                embed.add_field(name="Release date",
                                value=release, inline=False)

        embed.set_footer(text="Powered by https://appledb.dev")

        view = discord.ui.View()
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="View more on AppleDB",
                      url=matching_ios.get('appledburl')))

        embed.color = discord.Color.greyple()

        if matching_ios.get("beta"):
            embed.add_field(name="Signing status",
                            value="Unknown", inline=True)
            return embed, view

        ipsw_me_firmwares = await get_ipsw_firmware_info(matching_ios.get('version'))
        if not ipsw_me_firmwares:
            embed.add_field(name="Signing status",
                            value="Unknown", inline=True)
            return embed, view

        filtered_firmwares = [firmware for firmware in ipsw_me_firmwares if firmware.get(
            'buildid').lower() == matching_ios.get('uniqueBuild').lower()]
        signed_firmwares = [
            firmware for firmware in filtered_firmwares if firmware.get('signed')]

        if not signed_firmwares:
            embed.color = discord.Color.red()
            embed.add_field(name="Signing status",
                            value="Not signed", inline=True)
        elif len(signed_firmwares) == len(filtered_firmwares):
            embed.color = discord.Color.green()
            embed.add_field(name="Signing status",
                            value="Signed for all devices!", inline=True)
        else:
            embed.color = discord.Color.yellow()
            embed.add_field(name="Signing status",
                            value="Signed for some devices!", inline=True)

        return embed, view

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get info about an Apple device.")
    @app_commands.describe(device="Name or board identifier")
    @app_commands.autocomplete(device=device_autocomplete)
    @transform_context
    @whisper_in_general
    async def deviceinfo(self, ctx: BlooContext, device: str) -> None:
        response = await get_ios_cfw()
        all_devices = response.get("group")
        transformed_devices = transform_groups(all_devices)
        devices = [d for d in transformed_devices if d.get('name').lower() == device.lower(
        ) or device.lower() in [x.lower() for x in d.get('devices')]]

        if not devices:
            raise commands.BadArgument("No device found with that name.")

        matching_device_group = devices[0]

        embed = discord.Embed(title=matching_device_group.get(
            'name'), color=discord.Color.random())

        real = response.get("device")
        models = [
            real.get(dev) for dev in real if dev in matching_device_group.get("devices")]

        model_numbers = []
        model_names = ""
        for model_number in models:
            model_numbers.extend(model_number.get("model"))
            model_names += f"{model_number.get('name')} (`{model_number.get('identifier')}`)\n"

        model_numbers.sort()

        embed.add_field(name="All brand names",
                        value=model_names, inline=False)
        embed.add_field(name="Model(s)", value='`' +
                        "`, `".join(model_numbers) + "`", inline=True)

        ios = response.get("ios")
        ios = [i for _, i in ios.items()]
        supported_firmwares = [firmware for firmware in ios if model_number.get(
            "identifier") in firmware.get("devices")]
        supported_firmwares.sort(key=lambda x: x.get("released"))

        if supported_firmwares:
            latest_firmware = supported_firmwares[-1]
            if latest_firmware:
                embed.add_field(name="Latest firmware",
                                value=f"{latest_firmware.get('version')} (`{latest_firmware.get('uniqueBuild')}`)", inline=True)

        embed.add_field(
            name="SoC", value=f"{models[0].get('soc')} chip ({models[0].get('arch')})", inline=True)

        embed.set_footer(text="Powered by https://appledb.dev")

        view = discord.ui.View()
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="View more on AppleDB",
                      url=f"https://appledb.dev/device/{matching_device_group.get('name').replace(' ', '-')}"))

        await ctx.respond(embed=embed, view=view, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Find out if you can jailbreak your device")
    @app_commands.describe(device="Name or board identifier of the device")
    @app_commands.autocomplete(device=device_autocomplete)
    @app_commands.describe(version="Version of iOS you want to jailbreak")
    @app_commands.autocomplete(version=ios_on_device_autocomplete)
    @transform_context
    @whisper
    async def canijailbreak(self, ctx: BlooContext, device: DeviceTransformer, version: VersionOnDevice) -> None:
        response = await get_ios_cfw()
        found_jbs = []
        jailbreaks = response.get("jailbreak")
        jailbreaks = [jb for _, jb in jailbreaks.items()]
        for jb in jailbreaks:
            if jb.get("compatibility") is None:
                continue

            potential_version = None
            for jb_version in jb.get("compatibility"):
                if any(d in jb_version.get("devices") for d in device.get("devices")) and version.get("uniqueBuild") in jb_version.get("firmwares"):
                    if potential_version is None:
                        potential_version = jb_version
                    elif potential_version.get("priority") is None and jb_version.get("priority") is not None:
                        potential_version = jb_version
                    elif potential_version.get("priority") is not None and jb_version.get("priority") is not None and jb_version.get("priority") < potential_version.get("priority"):
                        potential_version = jb_version

            if potential_version is not None:
                jb["compatibility"] = [potential_version]
                found_jbs.append(jb)

        if not found_jbs:
            embed = discord.Embed(
                description=f"Sorry, **{device.get('name')}** is not jailbreakable on **{version.get('osStr')} {version.get('version')}**.", color=discord.Color.red())
            await ctx.respond_or_edit(embed=embed, ephemeral=ctx.whisper)
        else:
            ctx.device = device.get("name")
            ctx.device_id = device.get("identifier")
            ctx.version = f'{version.get("osStr")} {version.get("version")}'
            ctx.build = version.get("uniqueBuild")

            if len(found_jbs) > 0:
                def sort(x):
                    if x.get("compatibility")[0].get("priority") is not None:
                        return str(x.get("compatibility")[0].get("priority"))
                    elif x.get("priority") is not None:
                        return str(x.get("priority"))
                    else:
                        return str(x.get("name"))

                found_jbs.sort(key=sort)

            menu = CIJMenu(ctx, found_jbs, per_page=1, page_formatter=format_jailbreak_page,
                           show_skip_buttons=False, whisper=ctx.whisper)
            await menu.start()

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Find out how to bypass jailbreak detection for an app")
    @app_commands.describe(app="Name of the app")
    @app_commands.autocomplete(app=bypass_autocomplete)
    @transform_context
    @whisper_in_general
    async def bypass(self, ctx: BlooContext, app: str):
        data = await get_ios_cfw()
        bypasses = data.get('bypass')
        matching_apps = [body for _, body in bypasses.items(
        ) if app.lower() in body.get("name").lower() or app.lower() in body.get("bundleId").lower()]

        if not matching_apps:
            raise commands.BadArgument(
                "The API does not recognize that app or there are no bypasses available.")

        ctx.app = matching_apps[0]
        bypasses = ctx.app.get("bypasses")
        if not bypasses or bypasses is None or bypasses == [None]:
            raise commands.BadArgument(
                f"{ctx.app.get('name')} has no bypasses.")
        menu = BypassMenu(ctx, ctx.app.get(
            "bypasses"), per_page=1, page_formatter=format_bypass_page, whisper=ctx.whisper)
        await menu.start()


async def setup(bot):
    await bot.add_cog(iOSCFW(bot))
