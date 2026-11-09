import asyncio
from data.database import database_method, run_database
from typing import NamedTuple
from utils.cache_refresh import SnapshotCache
from data.model import FilterWord, Guild, Tag, Giveaway
from utils import cfg

class FilterSnapshot(NamedTuple):
    word: str
    bypass: int
    notify: bool
    silent_filter: bool
    false_positive: bool
    piracy: bool
    lower: str
    compact: str

    @classmethod
    def from_document(cls, word):
        lower = word.word.lower()
        return cls(word.word, word.bypass, word.notify, word.silent_filter,
                   word.false_positive, word.piracy, lower, "".join(lower.split()))


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
        return Guild.objects(_id=cfg.guild_id, tags__name=tag.name).update_one(
            set__tags__S__content=tag.content, set__tags__S__image=tag.image.grid_id,
            set__tags__S__button_links=tag.button_links)

    def get_tag(self, name: str):
        guild = Guild.objects(_id=cfg.guild_id, tags__name=name).fields(elemMatch__tags={'name': name}).modify(
            inc__tags__S__use_count=1, new=True)
        if guild is None:
            return
        return guild.tags.filter(name=name).first()

    def add_meme(self, meme: Tag) -> None:
        Guild.objects(_id=cfg.guild_id).update_one(push__memes=meme)

    def remove_meme(self, meme: str):
        return Guild.objects(_id=cfg.guild_id).update_one(pull__memes__name=Tag(name=meme).name)

    def edit_meme(self, meme):
        return Guild.objects(_id=cfg.guild_id, memes__name=meme.name).update_one(
            set__memes__S__content=meme.content, set__memes__S__image=meme.image.grid_id,
            set__memes__S__button_links=meme.button_links)

    def get_meme(self, name: str):
        guild = Guild.objects(_id=cfg.guild_id, memes__name=name).fields(elemMatch__memes={'name': name}).modify(
            inc__memes__S__use_count=1, new=True)
        if guild is None:
            return
        return guild.memes.filter(name=name).first()
    
    def allocate_case_id(self) -> int:
        """Reserve the next case number atomically; failed actions may leave gaps."""
        guild = Guild.objects(_id=cfg.guild_id).only('case_id').modify(inc__case_id=1, new=False)
        if guild is None:
            raise RuntimeError("Cannot allocate a case number: guild is not configured")
        return guild.case_id

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
        
    def add_raid_phrase(self, phrase: str) -> bool:
        existing = self.get_guild().raid_phrases.filter(word=phrase)
        if(len(existing) > 0):
            return False
        Guild.objects(_id=cfg.guild_id).update_one(push__raid_phrases=FilterWord(word=phrase, bypass=5, notify=True))
        return True
    
    def get_raid_phrases(self):
        return tuple(FilterSnapshot.from_document(word) for word in
                     Guild.objects(_id=cfg.guild_id).only('raid_phrases').get().raid_phrases)

    def remove_raid_phrase(self, phrase: str):
        Guild.objects(_id=cfg.guild_id).update_one(pull__raid_phrases__word=FilterWord(word=phrase).word)

    def set_spam_mode(self, mode) -> None:
        Guild.objects(_id=cfg.guild_id).update_one(set__ban_today_spam_accounts=mode)

    def add_filtered_word(self, fw: FilterWord) -> None:
        existing = self.get_guild().filter_words.filter(word=fw.word)
        if(len(existing) > 0):
            return False

        Guild.objects(_id=cfg.guild_id).update_one(push__filter_words=fw)
        return True

    def get_filtered_words(self):
        return tuple(FilterSnapshot.from_document(word) for word in
                     Guild.objects(_id=cfg.guild_id).only('filter_words').get().filter_words)

    def remove_filtered_word(self, word: str):
        return Guild.objects(_id=cfg.guild_id).update_one(pull__filter_words__word=FilterWord(word=word).word)

    def toggle_filtered_word_flag(self, name, flag):
        if flag not in ('silent_filter', 'piracy', 'false_positive'):
            raise ValueError("Unknown filter flag")
        # Compare-and-set only the chosen flag; never replace another editor's
        # flags or share a mutable document with the cache.
        for _ in range(8):
            words = self.get_filtered_words()
            word = next((word for word in words if word.word == name), None)
            if word is None:
                raise ValueError("Filtered word no longer exists")
            old = getattr(word, flag)
            query = {'word': name, flag: old} if old else {
                'word': name, '$or': [{flag: False}, {flag: {'$exists': False}}]}
            changed = Guild.objects(_id=cfg.guild_id, __raw__={
                'filter_words': {'$elemMatch': query}}).update_one(
                **{'set__filter_words__S__' + flag: not old})
            if changed:
                return not old
        raise RuntimeError("Filter flag changed repeatedly; please retry")

    def get_config_value(self, field):
        if field not in ('emoji_logging_webhook', 'logging_excluded_channels',
                         'filter_excluded_guilds', 'sabbath_mode'):
            raise ValueError("Unknown configuration field")
        value = getattr(Guild.objects(_id=cfg.guild_id).only(field).get(), field)
        return tuple(value) if isinstance(value, list) else value

    def set_emoji_logging_webhook(self, url):
        Guild.objects(_id=cfg.guild_id).update_one(set__emoji_logging_webhook=url)

    def get_content_names(self, field):
        if field not in ('tags', 'memes'):
            raise ValueError("Unknown content collection")
        guild = Guild.objects(_id=cfg.guild_id).only(field + '.name').get()
        return tuple(item.name for item in getattr(guild, field))

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


_repository = GuildService()


class AsyncGuildService:
    """Bot-facing API; all persistence runs in the bounded database pool."""
    def __init__(self):
        self.snapshots = SnapshotCache(ttl=3600)

    get_guild = database_method(_repository.get_guild)
    get_config_value = database_method(_repository.get_config_value)
    set_emoji_logging_webhook = database_method(_repository.set_emoji_logging_webhook)
    get_content_names = database_method(_repository.get_content_names)
    add_tag = database_method(_repository.add_tag)
    remove_tag = database_method(_repository.remove_tag)
    edit_tag = database_method(_repository.edit_tag)
    get_tag = database_method(_repository.get_tag)
    add_meme = database_method(_repository.add_meme)
    remove_meme = database_method(_repository.remove_meme)
    edit_meme = database_method(_repository.edit_meme)
    get_meme = database_method(_repository.get_meme)
    allocate_case_id = database_method(_repository.allocate_case_id)
    get_giveaway = database_method(_repository.get_giveaway)
    add_giveaway = database_method(_repository.add_giveaway)

    async def _change(self, key, function, *args, **kwargs):
        loop = asyncio.get_running_loop()
        def write():
            result = function(*args, **kwargs)
            # This runs inside the managed database worker even if its caller
            # was cancelled. Only the bot loop ever mutates the snapshot cache.
            loop.call_soon_threadsafe(self.snapshots.invalidate, key)
            return result
        return await run_database(write)

    async def add_raid_phrase(self, *args, **kwargs):
        return await self._change('raid_phrases', _repository.add_raid_phrase, *args, **kwargs)

    async def get_raid_phrases(self):
        return await self.snapshots.get('raid_phrases',
                                        lambda: run_database(_repository.get_raid_phrases))

    async def remove_raid_phrase(self, *args, **kwargs):
        return await self._change('raid_phrases', _repository.remove_raid_phrase, *args, **kwargs)

    set_spam_mode = database_method(_repository.set_spam_mode)

    async def add_filtered_word(self, *args, **kwargs):
        return await self._change('filter_words', _repository.add_filtered_word, *args, **kwargs)

    async def get_filtered_words(self):
        return await self.snapshots.get('filter_words',
                                        lambda: run_database(_repository.get_filtered_words))

    async def remove_filtered_word(self, *args, **kwargs):
        return await self._change('filter_words', _repository.remove_filtered_word, *args, **kwargs)

    async def toggle_filtered_word_flag(self, *args, **kwargs):
        return await self._change('filter_words', _repository.toggle_filtered_word_flag, *args, **kwargs)

    add_whitelisted_guild = database_method(_repository.add_whitelisted_guild)
    remove_whitelisted_guild = database_method(_repository.remove_whitelisted_guild)
    add_ignored_channel = database_method(_repository.add_ignored_channel)
    remove_ignored_channel = database_method(_repository.remove_ignored_channel)
    add_ignored_channel_logging = database_method(_repository.add_ignored_channel_logging)
    remove_ignored_channel_logging = database_method(_repository.remove_ignored_channel_logging)
    get_locked_channels = database_method(_repository.get_locked_channels)
    add_locked_channels = database_method(_repository.add_locked_channels)
    remove_locked_channels = database_method(_repository.remove_locked_channels)
    set_nsa_mapping = database_method(_repository.set_nsa_mapping)


guild_service = AsyncGuildService()
