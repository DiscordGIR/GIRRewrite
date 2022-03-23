import discord

from utils import BlooContext


class PFPView(discord.ui.View):
    def __init__(self, ctx: BlooContext, embed=discord.Embed):
        super().__init__(timeout=30)
        self.embed = embed
        self.ctx = ctx

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.ctx.respond_or_edit(embed=self.embed, view=self)


class PFPButton(discord.ui.Button):
    def __init__(self, ctx: BlooContext, member: discord.Member):
        super().__init__(label="Show other avatar", style=discord.ButtonStyle.primary)
        self.ctx = ctx
        self.member = member
        self.other = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return
        if not self.other:
            avatar = self.member.guild_avatar
            self.other = not self.other
        else:
            avatar = self.member.avatar or self.member.default_avatar
            self.other = not self.other

        embed = interaction.message.embeds[0]
        embed.set_image(url=avatar.replace(size=4096))

        animated = ["gif", "png", "jpeg", "webp"]
        not_animated = ["png", "jpeg", "webp"]

        def fmt(format_):
            return f"[{format_}]({avatar.replace(format=format_, size=4096)})"

        if avatar.is_animated():
            embed.description = f"View As\n {'  '.join([fmt(format_) for format_ in animated])}"
        else:
            embed.description = f"View As\n {'  '.join([fmt(format_) for format_ in not_animated])}"

        self.view.embed = embed
        await interaction.response.edit_message(embed=embed)
