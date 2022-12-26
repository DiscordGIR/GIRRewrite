from aiocache import cached
import time
from typing import List, Optional
from data.model import FilterWord, Guild, Tag, Giveaway
from data.model.guild import CaseIdView, ChannelsView, FilterWordView, MemeView, MetaProperties, RaidPhraseView, RolesAndChannelsView, RolesView, TagView
from utils import cfg
from utils.database import db
from beanie.odm.operators.update.array import Push, Pull
from beanie.odm.operators.update.general import Set, Inc

class GuildService:
    async def get_guild(self) -> Guild:
        """Returns the state of the main guild from the database.

        Returns
        -------
        Guild
            The Guild document object that holds information about the main guild.
        """

        return await Guild.find_one(Guild.id == cfg.guild_id)

    @cached(ttl=3600)
    async def get_channels(self) -> ChannelsView:
        return await Guild.find_one(Guild.id == cfg.guild_id).project(ChannelsView)

    @cached(ttl=3600)
    async def get_roles(self) -> RolesView:
        return await Guild.find_one(Guild.id == cfg.guild_id).project(RolesView)

    @cached(ttl=3600)
    async def get_roles_and_channels(self) -> RolesAndChannelsView:
        return await Guild.find_one(Guild.id == cfg.guild_id).project(RolesAndChannelsView)

    async def get_new_case_id(self) -> int:
        return (await Guild.find_one(Guild.id == cfg.guild_id).project(CaseIdView)).case_id

    async def get_meta_properties(self) -> MetaProperties:
        return await Guild.find_one(Guild.id == cfg.guild_id).project(MetaProperties)
    
    async def get_raid_phrases(self) -> List[FilterWord]:
        return (await Guild.find_one(Guild.id == cfg.guild_id).project(RaidPhraseView)).raid_phrases
    
    async def get_filter_words(self) -> List[FilterWord]:
        return (await Guild.find_one(Guild.id == cfg.guild_id).project(FilterWordView)).filter_words

    async def add_tag(self, tag: Tag) -> None:
        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.tags: tag}))

    async def remove_tag(self, tag: str):
        return await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.tags: { "name": tag } }))

    async def edit_tag(self, tag):
        return await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ "tags.$[elem]": tag }), array_filters=[ { "elem.name": tag.name } ])

    async def all_tags(self) -> list[Tag]:
        tags = await Guild.find_one(Guild.id == cfg.guild_id).project(TagView)
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
        image = await db.fs.open_download_stream(image_id)
        return image

    async def delete_image(self, image_id):
        await db.fs.delete(image_id)

    async def save_image(self, image_buffer, filename, content_type):
        async with db.fs.open_upload_stream(filename=filename) as stream:
            await stream.write(image_buffer)
            await stream.set("contentType", content_type)
            _id = stream._id

        return _id

    async def update_image(self, image_id, image_buffer, filename, content_type):
        await self.delete_image(image_id)
        return await self.save_image(image_buffer, filename, content_type)

    async def add_meme(self, meme: Tag) -> None:
        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.memes: meme}))

    async def remove_meme(self, meme: str):
        return await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.memes: { "name": meme } }))

    async def edit_meme(self, meme):
        return await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ "memes.$[elem]": meme }), array_filters=[ { "elem.name": meme.name } ])

    async def all_memes(self) -> list[Tag]:
        tags = await Guild.find_one(Guild.id == cfg.guild_id).project(MemeView)
        return tags.memes

    async def get_meme(self, name: str):
        memes = await self.all_memes()
        memes = list(filter(lambda meme: meme.name == name, memes))
        if not memes:
            return

        meme = memes[0]
        meme.use_count += 1
        await self.edit_meme(meme)
        return meme
    
    async def inc_case_id(self) -> None:
        """Increments Guild.case_id, which keeps track of the next available ID to
        use for a case.
        """

        await Guild.find_one(Guild.id == cfg.guild_id).update(Inc({Guild.case_id: 1}))

    async def all_rero_mappings(self):
        return (await Guild.find_one(Guild.id == cfg.guild_id).project(MetaProperties)).reaction_role_mapping

    async def add_rero_mapping(self, mapping):
        current = await self.all_rero_mappings()
        the_key = list(mapping.keys())[0]
        current[str(the_key)] = mapping[the_key]
        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ Guild.reaction_role_mapping: current }))

    async def append_rero_mapping(self, message_id, mapping):
        current = await self.all_rero_mappings()
        current[str(message_id)] = current[str(message_id)] | mapping
        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ Guild.reaction_role_mapping: current }))

    async def get_rero_mapping(self, id):
        g = await self.all_rero_mappings()
        if id in g:
            return g[id]
        else:
            return None

    async def delete_rero_mapping(self, id):
        g = await self.all_rero_mappings()
        if str(id) in g.keys():
            g.pop(str(id))
            await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ Guild.reaction_role_mapping: g }))
    
    async def get_giveaway(self, _id: int) -> Giveaway:
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
        
        return await Giveaway.find_one(Giveaway.id == _id)
    
    async def add_giveaway(self, id: int, channel: int, name: str, entries: list, winners: int, ended: bool = False, prev_winners=[]) -> None:
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
        giveaway = Giveaway(
            id = id,
            channel = channel,
            name = name,
            entries = entries,
            winners = winners,
            is_ended = ended,
            previous_winners = prev_winners
        )
        
        await giveaway.save()
        
    async def add_raid_phrase(self, phrase: str) -> bool:
        existing = await self.get_guild().raid_phrases.filter(word=phrase)
        if(len(existing) > 0):
            return False
        Guild.find(Guild.id == cfg.guild_id).update_one(push__raid_phrases=FilterWord(word=phrase, bypass=5, notify=True))
        return True
    
    async def remove_raid_phrase(self, phrase: str):
        await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.raid_phrases: { "word": phrase } }))

    async def set_spam_mode(self, mode) -> None:
        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ Guild.ban_today_spam_accounts: mode }))

    async def add_filtered_word(self, fw: FilterWord) -> None:
        existing = await self.get_filter_words()
        existing = list(filter(lambda word: word.word == fw.word, existing))
        if existing:
            return False

        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.filter_words: fw }))
        return True

    async def remove_filtered_word(self, word: str) -> None:
        await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.filter_words: { "word": word } }))

    async def update_filtered_word(self, word: FilterWord):
        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ "filter_words.$[elem]": word }), array_filters=[ { "elem.word": word.word } ])

    async def add_whitelisted_guild(self, id: int):
        if id in (await self.get_meta_properties()).filter_excluded_guilds:
            return False

        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.filter_excluded_guilds: id }))
        return True

    async def remove_whitelisted_guild(self, id: int):
        if id not in (await self.get_meta_properties()).filter_excluded_guilds:
            return False

        await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.filter_excluded_guilds: id }))
        return True

    async def add_ignored_channel(self, id: int):
        if id in (await self.get_meta_properties()).filter_excluded_channels:
            return False
        
        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.filter_excluded_channels: id }))
        return True

    async def remove_ignored_channel(self, id: int):
        if id not in (await self.get_meta_properties()).filter_excluded_channels:
            return False
        
        await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.filter_excluded_channels: id }))
        return True

    async def add_ignored_channel_logging(self, id: int):
        if id in (await self.get_meta_properties()).logging_excluded_channels:
            return False
        
        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.logging_excluded_channels: id }))
        return True

    async def remove_ignored_channel_logging(self, id: int):
        if id not in (await self.get_meta_properties()).logging_excluded_channels:
            return False
        
        await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.logging_excluded_channels: id }))
        return True

    async def set_emoji_logging_webhook(self, webhook: str):
        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ Guild.emoji_logging_webhook: webhook }))

    async def get_locked_channels(self):
        return (await self.get_meta_properties()).locked_channels

    async def add_locked_channels(self, channel):
        await Guild.find_one(Guild.id == cfg.guild_id).update(Push({ Guild.locked_channels: channel }))

    async def remove_locked_channels(self, channel):
        await Guild.find_one(Guild.id == cfg.guild_id).update(Pull({ Guild.locked_channels: channel }))

    async def set_nsa_mapping(self, channel_id, webhooks):
        current = await self.get_meta_properties()
        current.nsa_mapping[str(channel_id)] = webhooks
        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({ Guild.nsa_mapping: current }))

    async def set_sabbath_mode(self, mode: Optional[bool]):
        if mode is None:
            current = await self.get_meta_properties()
            mode = not current.sabbath_mode

        await Guild.find_one(Guild.id == cfg.guild_id).update(Set({Guild.sabbath_mode: mode}))
        return mode


guild_service = GuildService()