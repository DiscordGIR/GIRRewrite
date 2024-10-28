from typing import List

import discord

from core.model import TagButton, Tag


class TagToCreate:
    image: discord.Attachment

    def __init__(self, tag: Tag, buttons: List[TagButton]):
        self.tag = tag
        self.buttons = buttons

    def __repr__(self):
        return f"<TagToCreate tag={self.tag} buttons={self.buttons}, image={self.image.filename}>"