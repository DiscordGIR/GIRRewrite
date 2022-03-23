import discord

from .menu import Menu


class CIJMenu(Menu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_buttons = []

    def refresh_button_state(self):
        extra_buttons = []
        if self.ctx.jb_info.get("website") is not None:
            extra_buttons.append(discord.ui.Button(label='Website', url=self.ctx.jb_info.get(
                "website").get("url"), style=discord.ButtonStyle.url, row=1))

        if self.ctx.jb_info.get('guide'):
            added = False
            for guide in self.ctx.jb_info.get('guide')[1:]:
                if self.ctx.build in guide.get("firmwares") and self.ctx.device_id in guide.get("devices"):
                    extra_buttons.append(discord.ui.Button(
                        label=f'{guide.get("name")} Guide', url=f"https://ios.cfw.guide{guide.get('url')}", style=discord.ButtonStyle.url, row=1))
                    added = True
                    break

            if not added:
                guide = self.ctx.jb_info.get('guide')[0]
                extra_buttons.append(discord.ui.Button(
                    label=f'{guide.get("name")} Guide', url=f"https://ios.cfw.guide{guide.get('url')}", style=discord.ButtonStyle.url, row=1))

        for button in self.extra_buttons:
            self.remove_item(button)

        for button in extra_buttons:
            self.add_item(button)

        self.extra_buttons = extra_buttons
        super().refresh_button_state()


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
                discord.ui.Button(label="View Guide", style=discord.ButtonStyle.link, url=bypass.get("guide"))
            )
        if bypass.get("repository") is not None:
            extra_buttons.append(
                discord.ui.Button(label="View Repository", style=discord.ButtonStyle.link, url=bypass.get("repository").get("uri"))
            )

        if app.get("uri") is not None:
            extra_buttons.append(
                discord.ui.Button(label="View in App Store", emoji="<:appstore:392027597648822281>", style=discord.ButtonStyle.link, url=app.get("uri"))
            )

        for button in self.extra_buttons:
            self.remove_item(button)

        for button in extra_buttons:
            self.add_item(button)

        self.extra_buttons = extra_buttons

        super().refresh_button_state()
