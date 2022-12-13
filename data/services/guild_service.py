from io import BytesIO
from data.model import FilterWord, Guild, Tag, Giveaway
from data.model.guild import TagView
from utils import cfg
from beanie.odm.operators.update.array import Push, Pull

class GuildService:
    async def get_guild(self) -> Guild:
        """Returns the state of the main guild from the database.

        Returns
        -------
        Guild
            The Guild document object that holds information about the main guild.
        """

        return await Guild.find_one(Guild.id == cfg.guild_id)
    
    async def add_tag(self, tag: Tag) -> None:
        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.tags: tag}))

    async def remove_tag(self, tag: str):
        return await Guild.find(Guild.id == cfg.guild_id).update(Pull({ Guild.tags: { "name": tag } }))

    async def edit_tag(self, tag):
        return await Guild.find(Guild.id == cfg.guild_id).update({ "$set": { "tags.$[elem]": tag } }, array_filters=[ { "elem.name": tag.name } ])

    async def all_tags(self):
        tags = await Guild.find(Guild.id == cfg.guild_id).project(TagView).first_or_none()
        return tags.tags

    async def get_tag(self, name: str):
        tags = await self.all_tags()
        tags = list(filter(lambda tag: tag.name == name, tags))
        if not tags:
            return

        tag = tags[0]
        tag.use_count += 1
        await self.edit_tag(tag)
        return tag

    async def read_image(self, image_id):
        from utils import db

        image = await db.fs.open_download_stream(image_id)
        return image

    async def delete_image(self, image_id):
        from utils import db
        await db.fs.delete(image_id)

    async def save_image(self, image_buffer, filename, content_type):
        from utils import db

        async with db.fs.open_upload_stream(filename=filename) as stream:
            await stream.write(image_buffer)
            await stream.set("contentType", content_type)
            _id = stream._id

        return _id
        
    def add_meme(self, meme: Tag) -> None:
        Guild.find(Guild.id == cfg.guild_id).update_one(push__memes=meme)

    def remove_meme(self, meme: str):
        return Guild.find(Guild.id == cfg.guild_id).update_one(pull__memes__name=Tag(name=meme).name)

    def edit_meme(self, meme):
        return Guild.objects(_id=cfg.guild_id, memes__name=meme.name).update_one(set__memes__S=meme)

    def get_meme(self, name: str):
        meme = Guild.objects.get(_id=cfg.guild_id).memes.filter(name=name).first()
        if meme is None:
            return
        meme.use_count += 1
        self.edit_meme(meme)
        return meme
    
    def inc_caseid(self) -> None:
        """Increments Guild.case_id, which keeps track of the next available ID to
        use for a case.
        """

        Guild.find(Guild.id == cfg.guild_id).update_one(inc__case_id=1)

    async def all_rero_mappings(self):
        g = await self.get_guild()
        current = g.reaction_role_mapping
        return current

    async def add_rero_mapping(self, mapping):
        g = await self.get_guild()
        current = g.reaction_role_mapping
        the_key = list(mapping.keys())[0]
        current[str(the_key)] = mapping[the_key]
        g.reaction_role_mapping = current
        g.save()

    async def append_rero_mapping(self, message_id, mapping):
        g = await self.get_guild()
        current = g.reaction_role_mapping
        current[str(message_id)] = current[str(message_id)] | mapping
        g.reaction_role_mapping = current
        g.save()

    async def get_rero_mapping(self, id):
        g = await self.get_guild()
        if id in g.reaction_role_mapping:
            return g.reaction_role_mapping[id]
        else:
            return None

    async def delete_rero_mapping(self, id):
        g = await self.get_guild()
        if str(id) in g.reaction_role_mapping.keys():
            g.reaction_role_mapping.pop(str(id))
            g.save()
    
    def get_giveaway(self, _id: int) -> Giveaway:
        """
        Return the Document representing a giveaway, whose ID (message ID) is given by `id`
        If the giveaway doesn't exist in the database, then None is returned.
        Parameters
        ----------
        id : int
            The ID (message ID) of the giveaway
        
        Returns
        -------
        Giveaway
        """
        giveaway = Giveaway.objects(_id=_id).first()
        return giveaway
    
    def add_giveaway(self, id: int, channel: int, name: str, entries: list, winners: int, ended: bool = False, prev_winners=[]) -> None:
        """
        Add a giveaway to the database.
        Parameters
        ----------
        id : int
            The message ID of the giveaway
        channel : int
            The channel ID that the giveaway is in
        name : str
            The name of the giveaway.
        entries : list
            A list of user IDs who have entered (reacted to) the giveaway.
        winners : int
            The amount of winners that will be selected at the end of the giveaway.
        """
        giveaway = Giveaway()
        giveaway._id = id
        giveaway.channel = channel
        giveaway.name = name
        giveaway.entries = entries
        giveaway.winners = winners
        giveaway.is_ended = ended
        giveaway.previous_winners = prev_winners
        giveaway.save()
        
    async def add_raid_phrase(self, phrase: str) -> bool:
        existing = await self.get_guild().raid_phrases.filter(word=phrase)
        if(len(existing) > 0):
            return False
        Guild.find(Guild.id == cfg.guild_id).update_one(push__raid_phrases=FilterWord(word=phrase, bypass=5, notify=True))
        return True
    
    def remove_raid_phrase(self, phrase: str):
        Guild.find(Guild.id == cfg.guild_id).update_one(pull__raid_phrases__word=FilterWord(word=phrase).word)

    def set_spam_mode(self, mode) -> None:
        Guild.find(Guild.id == cfg.guild_id).update_one(set__ban_today_spam_accounts=mode)

    async def add_filtered_word(self, fw: FilterWord) -> None:
        existing = await self.get_guild().filter_words.filter(word=fw.word)
        if(len(existing) > 0):
            return False

        Guild.find(Guild.id == cfg.guild_id).update_one(push__filter_words=fw)
        return True

    def remove_filtered_word(self, word: str):
        return Guild.find(Guild.id == cfg.guild_id).update_one(pull__filter_words__word=FilterWord(word=word).word)

    def update_filtered_word(self, word: FilterWord):
        return Guild.objects(_id=cfg.guild_id, filter_words__word=word.word).update_one(set__filter_words__S=word)

    def add_whitelisted_guild(self, id: int):
        g = Guild.find(Guild.id == cfg.guild_id)
        g2 = g.first()
        if id not in g2.filter_excluded_guilds:
            g.update_one(push__filter_excluded_guilds=id)
            return True
        return False

    def remove_whitelisted_guild(self, id: int):
        g = Guild.find(Guild.id == cfg.guild_id)
        g2 = g.first()
        if id in g2.filter_excluded_guilds:
            g.update_one(pull__filter_excluded_guilds=id)
            return True
        return False

    def add_ignored_channel(self, id: int):
        g = Guild.find(Guild.id == cfg.guild_id)
        g2 = g.first()
        if id not in g2.filter_excluded_channels:
            g.update_one(push__filter_excluded_channels=id)
            return True
        return False

    def remove_ignored_channel(self, id: int):
        g = Guild.find(Guild.id == cfg.guild_id)
        g2 = g.first()
        if id in g2.filter_excluded_channels:
            g.update_one(pull__filter_excluded_channels=id)
            return True
        return False

    def add_ignored_channel_logging(self, id: int):
        g = Guild.find(Guild.id == cfg.guild_id)
        g2 = g.first()
        if id not in g2.logging_excluded_channels:
            g.update_one(push__logging_excluded_channels=id)
            return True
        return False

    def remove_ignored_channel_logging(self, id: int):
        g = Guild.find(Guild.id == cfg.guild_id)
        g2 = g.first()
        if id in g2.logging_excluded_channels:
            g.update_one(pull__logging_excluded_channels=id)
            return True
        return False

    async def get_locked_channels(self):
        return await self.get_guild().locked_channels

    def add_locked_channels(self, channel):
        Guild.find(Guild.id == cfg.guild_id).update_one(push__locked_channels=channel)

    def remove_locked_channels(self, channel):
        Guild.find(Guild.id == cfg.guild_id).update_one(pull__locked_channels=channel)

    def set_nsa_mapping(self, channel_id, webhooks):
        guild = Guild.find(Guild.id == cfg.guild_id).first()
        guild.nsa_mapping[str(channel_id)] = webhooks
        guild.save()

guild_service = GuildService()