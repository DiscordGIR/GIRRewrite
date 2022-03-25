import re
from itertools import groupby
from typing import List

import discord
from data.services import guild_service
from discord import app_commands
from discord.ext.commands import Command
from utils import get_ios_cfw, transform_groups
from utils.fetchers import canister_fetch_repos
from utils.framework.birthday import MONTH_MAPPING


def sort_versions(version):
    version = f'{version.get("osStr")} {version.get("version")}'
    v = version.split(' ')
    v[0] = list(map(int, v[1].split('.')))
    return v


async def command_list_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    commands: List[Command] = interaction.client.commands
    return [app_commands.Choice(name=command.name, value=command.name) for command in commands if current.lower() in command.name.lower()]


async def tags_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    tags = [tag.name.lower() for tag in guild_service.get_guild().tags]
    tags.sort()
    return [app_commands.Choice(name=tag, value=tag) for tag in tags if current.lower() in tag.lower()][:25]


async def memes_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    meme = [meme.name.lower() for meme in guild_service.get_guild().memes]
    meme.sort()
    return [app_commands.Choice(name=meme, value=meme) for meme in meme if current.lower() in meme.lower()][:25]


async def ios_version_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    versions = await get_ios_cfw()
    if versions is None:
        return []

    versions = versions.get("ios")
    versions = [v for _, v in versions.items()]
    versions.sort(key=lambda x: x.get("released")
                  or "1970-01-01", reverse=True)
    return [app_commands.Choice(name=f"{v['osStr']} {v['version']} ({v['build']})", value=v["uniqueBuild"]) for v in versions if (current.lower() in v['version'].lower() or current.lower() in v['build'].lower()) and not v['beta']][:25]


async def ios_beta_version_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    versions = await get_ios_cfw()
    if versions is None:
        return []

    versions = versions.get("ios")
    versions = [v for _, v in versions.items()]
    versions.sort(key=lambda x: x.get("released")
                  or "1970-01-01", reverse=True)
    return [app_commands.Choice(name=f"{v['osStr']} {v['version']} ({v['build']})", value=v["uniqueBuild"]) for v in versions if (current.lower() in v['version'].lower() or current.lower() in v['build'].lower()) and v['beta']][:25]


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


async def jb_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    apps = await get_ios_cfw()
    if apps is None:
        return []

    apps = apps.get("jailbreak")
    apps = [jb for _, jb in apps.items()]
    apps.sort(key=lambda x: x["name"].lower())
    return [app_commands.Choice(name=app["name"], value=app["name"]) for app in apps if app["name"].lower().startswith(current.lower())][:25]


async def bypass_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    data = await get_ios_cfw()
    bypasses = data.get("bypass")
    apps = [app for _, app in bypasses.items()]
    apps.sort(key=lambda x: x.get("name").lower())
    return [app_commands.Choice(name=app.get("name"), value=app.get("bundleId")) for app in apps if current.lower() in app.get("name").lower()][:25]


async def repo_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    repos = await canister_fetch_repos()
    if repos is None:
        return []
    repos = [repo['slug'] for repo in repos if repo.get(
        "slug") and repo.get("slug") is not None]
    repos.sort()
    return [app_commands.Choice(name=repo, value=repo) for repo in repos if current.lower() in repo.lower()][:25]


async def issue_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    issue_titles = [issue for issue in interaction.client.issue_cache.cache]
    issue_titles.sort(key=lambda issue: issue.lower())
    return [app_commands.Choice(name=issue_title, value=issue_title) for issue_title in issue_titles if current.lower() in issue_title.lower()][:25]


async def rule_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    rule_titles = [(issue_title, issue.description) for issue_title,
                   issue in interaction.client.rule_cache.cache.items()]

    def convert(text): return int(text) if text.isdigit() else text.lower()
    def alphanum_key(key): return [convert(c)
                                   for c in re.split('([0-9]+)', key[0])]
    rule_titles.sort(key=alphanum_key)
    return [app_commands.Choice(name=f"{title} - {description}"[:100], value=title) for title, description in rule_titles if current.lower() in title.lower() or current.lower() in description.lower()][:25]


async def time_suggestions(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    vals = ["1m", "15m", "30m", "1h", "6h", "12h", "1d", "1w"]
    return [app_commands.Choice(name=val, value=val) for val in vals]


async def date_autocompleter(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Autocompletes the date parameter for !mybirthday"""
    month = MONTH_MAPPING.get(interaction.namespace["month"])
    if month is None:
        return []

    return [app_commands.Choice(name=i, value=i) for i in range(1, month["max_days"]+1) if str(i).startswith(str(current))][:25]
