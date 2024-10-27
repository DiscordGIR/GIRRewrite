from typing import List

from core.model import TagButton, Tag


class TagResult:
    def __init__(self, tag: Tag, buttons: List[TagButton]):
        self.tag = tag
        self.buttons = buttons

    def __repr__(self):
        return f"<TagResult tag={self.tag} buttons={self.buttons}>"