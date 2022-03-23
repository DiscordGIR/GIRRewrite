import re
from datetime import datetime

import discord
from utils.context import BlooContext
from utils.framework import gatekeeper

from .menu import Menu

url_pattern = re.compile(
    r"((http|https)\:\/\/)[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*")


default_repos = [
    "apt.bingner.com",
    "apt.elucubratus.com",
    "apt.procurs.us",
    "table.nickchan.gq",
    "ftp.sudhip.com/procursus",
    "repo.quiprr.dev/procursus",
    "apt.saurik.com",
    "apt.oldcurs.us",
    "repo.chimera.sh",
    "diatr.us/apt",
    "repo.theodyssey.dev",
]


class TweakMenu(Menu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, timeout_function=self.on_timeout)
        # TODO: look into JumpButton
        # self.jump_button = JumpButton(self.ctx.bot, len(self.pages), self)
        self.extra_buttons = []

    def refresh_button_state(self):
        if self.ctx.repo:
            extra_buttons = [
                discord.ui.Button(label='Add Repo to Sileo', emoji="<:sileo:679466569407004684>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=sileo&repo={self.ctx.repo}', style=discord.ButtonStyle.url, row=1),
                discord.ui.Button(label='Add Repo to Zebra', emoji="<:zebra:911433583032422420>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=zebra&repo={self.ctx.repo}', style=discord.ButtonStyle.url, row=1),
                discord.ui.Button(label='Other Package Managers', emoji="<:cydiasileosplit:932650041099825232>",
                                  url=f'https://sharerepo.stkc.win/?repo={self.ctx.repo}', style=discord.ButtonStyle.url, row=1)
            ]
        else:
            extra_buttons = [
                discord.ui.Button(label='Cannot add default repo', emoji="<:sileo:679466569407004684>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=sileo&repo={self.ctx.repo}', disabled=True, style=discord.ButtonStyle.url, row=1),
                discord.ui.Button(label='Cannot add default repo', emoji="<:zebra:911433583032422420>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=zebra&repo={self.ctx.repo}', disabled=True, style=discord.ButtonStyle.url, row=1),
                discord.ui.Button(label='Cannot add default repo', emoji="<:Add:947354227171262534>",
                                  url=f'https://sharerepo.stkc.win/?repo={self.ctx.repo}', style=discord.ButtonStyle.url, disabled=True, row=1)
            ]
        if self.ctx.depiction:
            extra_buttons.insert(0,
                                 discord.ui.Button(label='View Depiction', emoji="<:Depiction:947358756033949786>",
                                                   url=self.ctx.depiction, style=discord.ButtonStyle.url, row=1),
                                 )

        # if len(self.pages) > 1:
        #     extra_buttons.append(self.jump_button)

        self.clear_items()
        for item in [self.previous, self.pause, self.next]:
            self.add_item(item)

        for button in extra_buttons:
            self.add_item(button)

        self.extra_buttons = extra_buttons

        super().refresh_button_state()

    def on_interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.ctx.author or gatekeeper.has(interaction.guild, interaction.user, 4)


async def format_tweak_page(ctx, entries, current_page, all_pages):
    """Formats the page for the tweak embed.

    Parameters
    ----------
    entries : List[dict]
        "The list of dictionaries for each tweak"
    all_pages : list
        "All entries that we will eventually iterate through"
    current_page : number
        "The number of the page that we are currently on"

    Returns
    -------
    discord.Embed
        "The embed that we will send"

    """
    entry = entries[0]
    ctx.repo = entry.get('repository').get('uri')
    ctx.depiction = entry.get('depiction')

    for repo in default_repos:
        if repo in entry.get('repository').get('uri'):
            ctx.repo = None
            break

    titleKey = entry.get('name')

    if entry.get('name') is None:
        titleKey = entry.get('identifier')
    embed = discord.Embed(title=titleKey, color=discord.Color.blue())
    embed.description = discord.utils.escape_markdown(
        entry.get('description')) or "No description"

    if entry.get('author') is not None:
        embed.add_field(name="Author", value=discord.utils.escape_markdown(
            entry.get('author').split("<")[0]), inline=True)
    else:
        embed.add_field(name="Author", value=discord.utils.escape_markdown(
            entry.get('maintainer').split("<")[0]), inline=True)

    embed.add_field(name="Version", value=discord.utils.escape_markdown(
        entry.get('latestVersion') or "No Version"), inline=True)
    embed.add_field(name="Price", value=entry.get(
        "price") or "Free", inline=True)
    embed.add_field(
        name="Repo", value=f"[{entry.get('repository').get('name')}]({entry.get('repository').get('uri')})" or "No Repo", inline=True)
    embed.add_field(name="Bundle ID", value=entry.get(
        "identifier") or "Not found", inline=True)
    if entry.get('tintColor') is None and entry.get('packageIcon') is not None and url_pattern.match(entry.get('packageIcon')):
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(entry.get('packageIcon')) as icon:
        #         if icon.status == 200:
        #             color = ColorThief(IO.BytesIO(await icon.read())).get_color(quality=1000)
        #             embed.color = discord.Color.from_rgb(
        #                 color[0], color[1], color[2])
        #         else:
        embed.color = discord.Color.blue()
    elif entry.get('tintColor') is not None:
        embed.color = int(entry.get('tintColor').replace('#', '0x'), 0)

    if entry.get('packageIcon') is not None and url_pattern.match(entry.get('packageIcon')):
        embed.set_thumbnail(url=entry.get('packageIcon'))
    embed.set_footer(icon_url=f"{'https://assets.stkc.win/bigboss-sileo.png' if 'http://apt.thebigboss.org/repofiles/cydia/CydiaIcon.png' in entry.get('repository').get('uri')+'/CydiaIcon.png' else entry.get('repository').get('uri')+'/CydiaIcon.png'}",
                     text=f"Powered by Canister • Page {current_page}/{len(all_pages)}" or "No Package")
    embed.timestamp = datetime.now()
    return embed



async def canister(ctx: BlooContext, interaction: bool, whisper: bool, result):
    # await TweakMenu(ctx, result, per_page=1, page_formatter=format_tweak_page, whisper=whisper, start_page=25, show_skip_buttons=False, non_interaction_message=await ctx.interaction.original_message()).start()
    ctx.interaction.response._responded = True
    await TweakMenu(ctx, result, per_page=1, page_formatter=format_tweak_page, whisper=whisper, start_page=25, show_skip_buttons=False).start(ctx.interaction)


class TweakDropdown(discord.ui.Select):
    def __init__(self, author, entries, interaction, should_whisper):
        self.author = author
        self.interaction = interaction
        self.raw_entries = entries
        self.should_whisper = should_whisper
        entries = entries[:24]
        self.current_entry = entries[0]
        self.entries = {entry.get("identifier"): entry for entry in entries}
        options = [discord.SelectOption(label=(option.get("name") or option.get('identifier'))[:100] or "No title", description=f"{option.get('author').split('<')[0] if option.get('author') is not None else option.get('maintainer').split('<')[0]} • {option.get('repository').get('name')}"[:100], value=option.get(
            "identifier"), emoji="<:sileo_tweak_icon:922017793677869056>") for option in entries]

        if len(self.raw_entries) > 24:
            options.append(discord.SelectOption(
                label=f"View {len(self.raw_entries) - 24} more results...", value="view_more"))
        super().__init__(placeholder='Pick a tweak to view...',
                         min_values=1, max_values=1, options=options)

    def start(self, ctx):
        self.ctx = ctx

    async def callback(self, interaction):
        if interaction.user != self.author and not gatekeeper.has(interaction.guild, interaction.user, 4):
            return

        self.ctx.interaction = interaction

        if self.values[0] == "view_more":
            # self.ctx.author = self.author
            if self.interaction:
                await canister(self.ctx, self.interaction, self.should_whisper, self.raw_entries)
            else:
                await canister(self.ctx, False, False, self.raw_entries)
            self._view.stop()
            return

        selected_value = self.entries.get(self.values[0])
        if selected_value is None:
            return

        self.refresh_view(selected_value)
        if self.interaction:
            await self.ctx.interaction.response.edit_message(embed=await self.format_tweak_page(selected_value), view=self._view)
        else:
            await self.ctx.message.edit(embed=await self.format_tweak_page(selected_value), view=self._view)

    async def on_timeout(self):
        self.disabled = True
        self.placeholder = "Timed out"

        if self.interaction:
            await self.ctx.edit(view=self._view)
        else:
            await self.ctx.message.edit(view=self._view)

    async def format_tweak_page(self, entry):
        titleKey = entry.get('name')
        description = discord.utils.escape_markdown(entry.get('description'))

        if entry.get('name') is None:
            titleKey = entry.get('identifier')
        embed = discord.Embed(title=titleKey, color=discord.Color.blue())
        embed.description = description[:200]+"..." if len(description) > 200 else description

        if entry.get('author') is not None:
            embed.add_field(name="Author", value=discord.utils.escape_markdown(
                entry.get('author').split("<")[0]), inline=True)
        else:
            embed.add_field(name="Author", value=discord.utils.escape_markdown(
                entry.get('maintainer').split("<")[0]), inline=True)

        embed.add_field(name="Version", value=discord.utils.escape_markdown(
            entry.get('latestVersion') or "No Version"), inline=True)
        embed.add_field(name="Price", value=entry.get(
            "price") or "Free", inline=True)
        embed.add_field(
            name="Repo", value=f"[{entry.get('repository').get('name')}]({entry.get('repository').get('uri')})" or "No Repo", inline=True)
        embed.add_field(name="Bundle ID", value=entry.get(
            "identifier") or "Not found", inline=True)

        if entry.get('tintColor') is None and entry.get('packageIcon') is not None and url_pattern.match(entry.get('packageIcon')):
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(entry.get('packageIcon')) as icon:
            #         if icon.status == 200:
            #             color = ColorThief(io.BytesIO(await icon.read())).get_color(quality=1000)
            #             embed.color = discord.Color.from_rgb(
            #                 color[0], color[1], color[2])
            #         else:
            embed.color = discord.Color.blue()
        elif entry.get('tintColor') is not None:
            embed.color = int(entry.get('tintColor').replace('#', '0x'), 0)

        if entry.get('packageIcon') is not None and url_pattern.match(entry.get('packageIcon')):
            embed.set_thumbnail(url=entry.get('packageIcon'))
        embed.set_footer(icon_url=f"{'https://assets.stkc.win/bigboss-sileo.png' if 'http://apt.thebigboss.org/repofiles/cydia/CydiaIcon.png' in entry.get('repository').get('uri')+'/CydiaIcon.png' else entry.get('repository').get('uri')+'/CydiaIcon.png'}",
                         text=f"Powered by Canister" or "No Package")
        embed.timestamp = datetime.now()
        return embed

    def generate_buttons(self, entry):
        repo = entry.get('repository').get('uri')
        depiction = entry.get('depiction')

        for r in default_repos:
            if r in entry.get('repository').get('uri'):
                repo = None
                break

        if repo is not None:
            extra_buttons = [
                discord.ui.Button(label='Add Repo to Sileo', emoji="<:sileo:679466569407004684>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=sileo&repo={repo}', style=discord.ButtonStyle.url),
                discord.ui.Button(label='Add Repo to Zebra', emoji="<:zebra:911433583032422420>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=zebra&repo={repo}', style=discord.ButtonStyle.url),
                discord.ui.Button(label='Other Package Managers', emoji="<:Add:947354227171262534>",
                                  url=f'https://sharerepo.stkc.win/?repo={repo}', style=discord.ButtonStyle.url)
            ]
        else:
            extra_buttons = [
                discord.ui.Button(label='Cannot add default repo', emoji="<:sileo:679466569407004684>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=sileo&repo={repo}', disabled=True, style=discord.ButtonStyle.url),
                discord.ui.Button(label='Cannot add default repo', emoji="<:zebra:911433583032422420>",
                                  url=f'https://sharerepo.stkc.win/v2/?pkgman=zebra&repo={repo}', disabled=True, style=discord.ButtonStyle.url),
                discord.ui.Button(label='Cannot add default repo', emoji="<:Add:947354227171262534>",
                                  url=f'https://sharerepo.stkc.win/?repo={repo}', disabled=True, style=discord.ButtonStyle.url)
            ]
        if depiction is not None:
            extra_buttons.insert(0,
                                 discord.ui.Button(label='View Depiction', emoji="<:Depiction:947358756033949786>",
                                                   url=depiction, style=discord.ButtonStyle.url),
                                 )
        return extra_buttons

    def refresh_view(self, entry):
        extra_buttons = self.generate_buttons(entry)
        self._view.clear_items()

        if len(self.raw_entries) > 1:
            self._view.add_item(self)

        for button in extra_buttons:
            self._view.add_item(button)



class BypassMenu(Menu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, timeout_function=self.on_timeout)
        self.extra_buttons = []

    def refresh_button_state(self):
        app = self.ctx.app
        bypass = self.ctx.current_bypass
        extra_buttons = []

        if bypass.get("guide") is not None:
            extra_buttons.append(
                discord.ui.Button(
                    label="View Guide", style=discord.ButtonStyle.link, url=bypass.get("guide"))
            )
        if bypass.get("repository") is not None:
            extra_buttons.append(
                discord.ui.Button(label="View Repository", style=discord.ButtonStyle.link, url=bypass.get(
                    "repository").get("uri"))
            )

        if app.get("uri") is not None:
            extra_buttons.append(
                discord.ui.Button(label="View in App Store", emoji="<:appstore:392027597648822281>",
                                  style=discord.ButtonStyle.link, url=app.get("uri"))
            )

        for button in self.extra_buttons:
            self.remove_item(button)

        for button in extra_buttons:
            self.add_item(button)

        self.extra_buttons = extra_buttons

        super().refresh_button_state()

    async def on_timeout(self):
        self.stopped = True
        await self.refresh_response_message()
        self.stop()


# class JumpButton(discord.ui.Button):
#     def __init__(self, bot, max_page: int, tmb):
#         super().__init__(style=discord.ButtonStyle.primary, emoji="⤴️")
#         self.max_page = max_page
#         self.bot = bot
#         self.tmb = tmb
#         self.row = 2

#     async def callback(self, interaction: discord.Interaction):
#         if interaction.user != self.tmb.ctx.author:
#             return

#         # ctx = await self.bot.get_application_context(interaction, cls=BlooContext)
#         ctx = BlooContext(interaction)

#         await interaction.response.defer(ephemeral=True)
#         prompt = PromptData(
#             value_name="page",
#             description="What page do you want to jump to?",
#             timeout=10,
#             convertor=None)

#         res = await ctx.prompt(prompt)
#         if res is None:
#             await ctx.send_warning("Cancelled")
#             return

#         try:
#             res = int(res)
#         except ValueError:
#             await ctx.send_warning("Invalid page number!")
#             return

#         if res < 0 or res > self.max_page:
#             await ctx.send_warning("Invalid page number!")
#             return

#         self.tmb.current_page = res
#         await self.tmb.refresh_response_message()
#         await ctx.send_success(f"Jumped to page {res}!")
