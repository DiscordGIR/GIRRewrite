import inspect
from typing import Callable, Union

import discord
from discord import ui
from utils import BlooContext


class Menu(ui.View):
    # def __init__(self, ctx: Union[BlooContext, BlooOldContext], entries: list, per_page: int, page_formatter: Callable[[Union[BlooContext, BlooOldContext], list, int, list], None], whisper: bool, show_skip_buttons: bool = True, start_page=1, non_interaction_message=None, timeout_function=None):
    def __init__(self, ctx: BlooContext, entries: list, per_page: int, page_formatter: Callable[[BlooContext, list, int, list], None], whisper: bool, show_skip_buttons: bool = True, start_page=1, non_interaction_message=None, timeout_function=None):
        super().__init__(timeout=60)

        self.ctx = ctx
        self.is_interaction = isinstance(ctx, BlooContext)

        """Initializes a menu"""
        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        self.pages = list(chunks(entries, per_page))
        self.per_page = per_page
        self.page_formatter = page_formatter
        self.whisper = whisper
        self.show_skip_buttons = show_skip_buttons
        self.current_page = start_page
        self.non_interaction_message = non_interaction_message
        self.on_timeout = timeout_function or self.on_timeout

        self.stopped = False
        self.page_cache = {}

        if not self.show_skip_buttons:
            self.remove_item(self.first)
            self.remove_item(self.last)

    async def start(self):
        await self.refresh_response_message()

    async def generate_next_embed(self):
        if self.current_page in self.page_cache:
            return self.page_cache.get(self.current_page)

        if inspect.iscoroutinefunction(self.page_formatter):
            embed = await self.page_formatter(self.ctx, self.pages[self.current_page - 1], self.current_page, self.pages)
        else:
            embed = self.page_formatter(
                self.ctx, self.pages[self.current_page - 1], self.current_page, self.pages)

        self.page_cache[self.current_page] = embed
        return embed

    def refresh_button_state(self):
        built_in_buttons = [self.first, self.previous,
                            self.pause, self.next, self.last]
        if len(self.pages) == 1:
            for button in built_in_buttons:
                self.remove_item(button)
            self.stop()
            return
        elif self.stopped:
            for button in built_in_buttons:
                button.disabled = True
            return

        self.first.disabled = self.current_page == 1
        self.previous.disabled = self.current_page == 1
        self.next.disabled = self.current_page == len(self.pages)
        self.last.disabled = self.current_page == len(self.pages)

    async def refresh_response_message(self, interaction: discord.Interaction = None):
        if interaction is not None:
            self.ctx = BlooContext(interaction)

        embed = await self.generate_next_embed()
        self.refresh_button_state()
        if self.is_interaction:
            msg_send_method = self.ctx.respond_or_edit
        elif self.non_interaction_message is None:
            msg_send_method = self.ctx.channel.send
        else:
            msg_send_method = self.non_interaction_message.edit

        if self.is_interaction:
            await msg_send_method(embed=embed, view=self, ephemeral=self.whisper)
        else:
            response = await msg_send_method(embed=embed, view=self)
            if self.non_interaction_message is None:
                self.non_interaction_message = response

    async def on_timeout(self):
        self.stopped = True
        self.stop()

    @ui.button(emoji='⏮️', style=discord.ButtonStyle.blurple, row=2, disabled=True)
    async def first(self, button: ui.Button, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            self.current_page = 1
            await self.refresh_response_message(interaction)

    @ui.button(emoji='⬅️', style=discord.ButtonStyle.blurple, row=2, disabled=True)
    async def previous(self, button: ui.Button, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            self.current_page -= 1
            await self.refresh_response_message(interaction)

    @ui.button(emoji='⏹️', style=discord.ButtonStyle.blurple, row=2)
    async def pause(self, button: ui.Button, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            await self.on_timeout()
            await self.refresh_response_message(interaction)

    @ui.button(emoji='➡️', style=discord.ButtonStyle.blurple, row=2, disabled=True)
    async def next(self, button: ui.Button, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            self.current_page += 1
            await self.refresh_response_message(interaction)

    @ui.button(emoji='⏭️', style=discord.ButtonStyle.blurple, row=2, disabled=True)
    async def last(self, button: ui.Button, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            self.current_page = len(self.pages)
            await self.refresh_response_message(interaction)
