from aiocache import cached, caches
from data.model import FilterWord, Guild, Tag, Giveaway
from utils import cfg

class GuildService:
    def get_guild(self) -> Guild:
        """Returns the state of the main guild from the database.

        Returns
        -------
        Guild
            The Guild document object that holds information about the main guild.
        """

        return Guild.objects(_id=cfg.guild_id).first()
    
    def add_tag(self, tag: Tag) -> None:
        Guild.objects(_id=cfg.guild_id).update_one(push__tags=tag)

    def remove_tag(self, tag: str):
        return Guild.objects(_id=cfg.guild_id).update_one(pull__tags__name=Tag(name=tag).name)

    def edit_tag(self, tag):
        return Guild.objects(_id=cfg.guild_id, tags__name=tag.name).update_one(set__tags__S=tag)

    def get_tag(self, name: str):
        tag = Guild.objects.get(_id=cfg.guild_id).tags.filter(name=name).first()
        if tag is None:
            return
        tag.use_count += 1
        self.edit_tag(tag)
        return tag

    def add_meme(self, meme: Tag) -> None:
        Guild.objects(_id=cfg.guild_id).update_one(push__memes=meme)

    def remove_meme(self, meme: str):
        return Guild.objects(_id=cfg.guild_id).update_one(pull__memes__name=Tag(name=meme).name)

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

        Guild.objects(_id=cfg.guild_id).update_one(inc__case_id=1)

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
        existing = self.get_guild().raid_phrases.filter(word=phrase)
        if(len(existing) > 0):
            return False
        Guild.objects(_id=cfg.guild_id).update_one(push__raid_phrases=FilterWord(word=phrase, bypass=5, notify=True))
        await self.get_raid_phrases.cache.clear()
        return True
    
    @cached(ttl=3600, key="guild_raid_phrases")
    async def get_raid_phrases(self):
        return self.get_guild().raid_phrases

    async def remove_raid_phrase(self, phrase: str):
        await self.get_raid_phrases.cache.clear()
        Guild.objects(_id=cfg.guild_id).update_one(pull__raid_phrases__word=FilterWord(word=phrase).word)

    def set_spam_mode(self, mode) -> None:
        Guild.objects(_id=cfg.guild_id).update_one(set__ban_today_spam_accounts=mode)

    async def add_filtered_word(self, fw: FilterWord) -> None:
        existing = self.get_guild().filter_words.filter(word=fw.word)
        if(len(existing) > 0):
            return False

        Guild.objects(_id=cfg.guild_id).update_one(push__filter_words=fw)
        await self.get_filtered_words.cache.clear()
        return True

    @cached(ttl=3600, key="guild_filtered_words")
    async def get_filtered_words(self) -> FilterWord:
        return self.get_guild().filter_words

    async def remove_filtered_word(self, word: str):
        await self.get_filtered_words.cache.clear()
        return Guild.objects(_id=cfg.guild_id).update_one(pull__filter_words__word=FilterWord(word=word).word)

    async def update_filtered_word(self, word: FilterWord):
        await self.get_filtered_words.cache.clear()
        return Guild.objects(_id=cfg.guild_id, filter_words__word=word.word).update_one(set__filter_words__S=word)

    def add_whitelisted_guild(self, id: int):
        g = Guild.objects(_id=cfg.guild_id)
        g2 = g.first()
        if id not in g2.filter_excluded_guilds:
            g.update_one(push__filter_excluded_guilds=id)
            return True
        return False

    def remove_whitelisted_guild(self, id: int):
        g = Guild.objects(_id=cfg.guild_id)
        g2 = g.first()
        if id in g2.filter_excluded_guilds:
            g.update_one(pull__filter_excluded_guilds=id)
            return True
        return False

    def add_ignored_channel(self, id: int):
        g = Guild.objects(_id=cfg.guild_id)
        g2 = g.first()
        if id not in g2.filter_excluded_channels:
            g.update_one(push__filter_excluded_channels=id)
            return True
        return False

    def remove_ignored_channel(self, id: int):
        g = Guild.objects(_id=cfg.guild_id)
        g2 = g.first()
        if id in g2.filter_excluded_channels:
            g.update_one(pull__filter_excluded_channels=id)
            return True
        return False

    def add_ignored_channel_logging(self, id: int):
        g = Guild.objects(_id=cfg.guild_id)
        g2 = g.first()
        if id not in g2.logging_excluded_channels:
            g.update_one(push__logging_excluded_channels=id)
            return True
        return False

    def remove_ignored_channel_logging(self, id: int):
        g = Guild.objects(_id=cfg.guild_id)
        g2 = g.first()
        if id in g2.logging_excluded_channels:
            g.update_one(pull__logging_excluded_channels=id)
            return True
        return False

    def get_locked_channels(self):
        return self.get_guild().locked_channels

    def add_locked_channels(self, channel):
        Guild.objects(_id=cfg.guild_id).update_one(push__locked_channels=channel)

    def remove_locked_channels(self, channel):
        Guild.objects(_id=cfg.guild_id).update_one(pull__locked_channels=channel)

    def set_nsa_mapping(self, channel_id, webhooks):
        guild = Guild.objects(_id=cfg.guild_id).first()
        guild.nsa_mapping[str(channel_id)] = webhooks
        guild.save()

guild_service = GuildService()
