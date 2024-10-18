import re
import discord

from data.model import Tag


class TagModal(discord.ui.Modal):
    def __init__(self, bot, tag_name, author: discord.Member) -> None:
        self.bot = bot
        self.tag_name = tag_name
        self.author = author
        self.tag = None

        super().__init__(title=f"Add tag {self.tag_name}")

        self.add_item(
            discord.ui.TextInput(
                label="Body of the tag",
                placeholder="Enter the body of the tag",
                style=discord.TextStyle.long,
            )
        )

        for i in range(2):
            self.add_item(
                discord.ui.TextInput(
                    label=f"Button {(i%2)+1} name",
                    placeholder="Enter a name for the button. You can also put an emoji at the start.",
                    style=discord.TextStyle.short,
                    required=False,
                    max_length=80
                )
            )
            self.add_item(
                discord.ui.TextInput(
                    label=f"Button {(i%2)+1} link",
                    placeholder="Enter a link for the button",
                    style=discord.TextStyle.short,
                    required=False
                )
            )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return

        button_names = [child.value.strip() for child in self.children[1::2] if child.value is not None and len(child.value.strip()) > 0]
        links = [child.value.strip() for child in self.children[2::2] if child.value is not None and len(child.value.strip()) > 0]

        # make sure all links are valid URLs with regex
        if not all(re.match(r'^(https|http)://.*', link) for link in links):
            await self.send_error(interaction, "The links must be valid URLs!")
            return

        if len(button_names) != len(links):
            await self.send_error(interaction, "All buttons must have labels and links!")
            return

        buttons = list(zip(button_names, links))
        description = self.children[0].value
        if not description:
            await self.send_error(interaction, "Description is missing!")
            return

        for label in button_names:
            custom_emojis = re.search(r'<:\d+>|<:.+?:\d+>|<a:.+:\d+>|[\U00010000-\U0010ffff]', label)
            if custom_emojis is not None:
                emoji = custom_emojis.group(0).strip()
                if not label.startswith(emoji):
                    await self.send_error(interaction, "Emojis must be at the start of labels!")
                    return
                label = label.replace(emoji, '')
                label = label.strip()
                if not label:
                    await self.send_error(interaction, "A button cannot just be an emoji!")
                    return

        # prepare tag data-mongo for database
        tag = Tag()
        tag.name = self.tag_name.lower()
        tag.content = description
        tag.added_by_id = self.author.id
        tag.added_by_tag = str(self.author)
        tag.button_links = buttons

        self.tag = tag
        self.stop()
        try:
            await interaction.response.send_message()
        except:
            pass
        
    async def send_error(self, interaction: discord.Interaction, error: str):
        embed = discord.Embed(title=":(\nYour command ran into a problem", description=error, color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class EditTagModal(discord.ui.Modal):
    def __init__(self, tag: Tag, author: discord.Member) -> None:
        self.tag = tag
        self.author = author
        self.edited = False

        super().__init__(title=f"Edit tag {self.tag.name}")

        self.add_item(
            discord.ui.TextInput(
                label="Body of the tag",
                placeholder="Enter the body of the tag",
                style=discord.TextStyle.long,
                default=tag.content
            )
        )
        
        for i in range(2):
            self.add_item(
                discord.ui.TextInput(
                    label=f"Button {(i%2)+1} name",
                    placeholder="Enter a name for the button. You can also put an emoji at the start.",
                    style=discord.TextStyle.short,
                    required=False,
                    max_length=80,
                    default=self.tag.button_links[i][0] if len(self.tag.button_links) > i else None
                )
            )
            self.add_item(
                discord.ui.TextInput(
                    label=f"Button {(i%2)+1} link",
                    placeholder="Enter a link for the button",
                    style=discord.TextStyle.short,
                    required=False,
                    default=self.tag.button_links[i][1] if len(self.tag.button_links) > i else None
                )
            )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return

        button_names = [child.value.strip() for child in self.children[1::2] if child.value is not None and len(child.value.strip()) > 0]
        links = [child.value.strip() for child in self.children[2::2] if child.value is not None and len(child.value.strip()) > 0]

        # make sure all links are valid URLs with regex
        if not all(re.match(r'^(https|http)://.*', link) for link in links):
            await self.send_error(interaction, "The links must be valid URLs!")
            return

        if len(button_names) != len(links):
            await self.send_error(interaction, "All buttons must have labels and links!")
            return

        buttons = list(zip(button_names, links))
        description = self.children[0].value
        if not description:
            await self.send_error(interaction, "Description is missing!")
            return

        for label in button_names:
            custom_emojis = re.search(r'<:\d+>|<:.+?:\d+>|<a:.+:\d+>|[\U00010000-\U0010ffff]', label)
            if custom_emojis is not None:
                emoji = custom_emojis.group(0).strip()
                if not label.startswith(emoji):
                    await self.send_error(interaction, "Emojis must be at the start of labels!")
                    return
                label = label.replace(emoji, '')
                label = label.strip()
                if not label:
                    await self.send_error(interaction, "A button cannot just be an emoji!")
                    return

        # prepare tag data-mongo for database
        self.tag.content = description
        self.tag.button_links = buttons
        self.edited = True
        self.stop()

        try:
            await interaction.response.send_message()
        except:
            pass

    async def send_error(self, interaction: discord.Interaction, error: str):
        embed = discord.Embed(title=":(\nYour command ran into a problem", description=error, color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
