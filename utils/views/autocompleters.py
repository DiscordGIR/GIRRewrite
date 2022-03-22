from itertools import groupby
from typing import List

import aiohttp
import discord
from aiocache import cached
from data.services import guild_service
from discord import app_commands
from discord.ext.commands import Command


def sort_versions(version):
    version = f'{version.get("osStr")} {version.get("version")}'
    v = version.split(' ')
    v[0] = list(map(int, v[1].split('.')))
    return v


def transform_groups(groups):
    final_groups = []
    groups = [g for _, g in groups.items()]
    for group in groups:
        if group.get("subgroup") is not None:
            for subgroup in group.get("subgroup"):
                subgroup["order"] = group.get("order")
                final_groups.append(subgroup)
        else:
            final_groups.append(group)

    return final_groups


@cached(ttl=3600)
async def get_ios_cfw():
    """Gets all apps on ios.cfw.guide

    Returns
    -------
    dict
        "ios, jailbreaks, devices"
    """

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.appledb.dev/main.json") as resp:
            if resp.status == 200:
                data = await resp.json()

    return data


async def command_list_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    commands: List[Command] = interaction.client.commands
    return [app_commands.Choice(name=command.name, value=command.name) for command in commands if current.lower() in command.name.lower()]


async def tags_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    tags = [tag.name.lower() for tag in guild_service.get_guild().tags]
    tags.sort()
    return [app_commands.Choice(name=tag, value=tag) for tag in tags if current.lower() in tag.lower()][:25]


async def ios_on_device_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    cfw = await get_ios_cfw()
    if cfw is None:
        return []

    ios = cfw.get("ios")
    ios = [i for _, i in ios.items()]
    devices = cfw.get("group")
    transformed_devices = transform_groups(devices)
    selected_device = interaction.namespace["device"]

    if selected_device is None:
        return []
    matching_devices = [
        d for d in transformed_devices if selected_device.lower() == d.get('name').lower() or any(selected_device.lower() == x.lower() for x in d.get("devices"))]

    if not matching_devices:
        return []

    matching_device = matching_devices[0].get("devices")[0]
    matching_ios = [version for version in ios if matching_device in version.get(
        'devices') and current.lower() in version.get('version').lower()]

    matching_ios.sort(key=sort_versions, reverse=True)

    return [app_commands.Choice(name=f'{version.get("osStr")} {version.get("version")}', value=version.get("uniqueBuild") or version.get("build")) for version in matching_ios][:25]


async def device_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    res = await get_ios_cfw()
    if res is None:
        return []

    all_devices = res.get("group")
    transformed_devices = transform_groups(all_devices)
    devices = [d for d in transformed_devices if (any(current.lower() in x.lower(
    ) for x in d.get('devices')) or current.lower() in d.get('name').lower())]

    devices.sort(key=lambda x: x.get('type') or "zzz")
    devices_groups = groupby(devices, lambda x: x.get('type'))

    devices = []
    for _, group in devices_groups:
        group = list(group)
        group.sort(key=lambda x: x.get('order'), reverse=True)
        devices.extend(group)

        if len(devices) >= 25:
            break

    return [app_commands.Choice(name=device.get('name'), value=device.get("devices")[0] if device.get("devices") else device.get("name")) for device in devices][:25]

async def issue_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    issue_titles = [issue for issue in interaction.client.issue_cache.cache]
    issue_titles.sort(key=lambda issue: issue.lower())
    print(issue_titles)
    return [app_commands.Choice(name=issue_title, value=issue_title) for issue_title in issue_titles if current.lower() in issue_title.lower()][:25]
