from dotenv import load_dotenv

from core.database import get_session, get_engine
import asyncio
import os
from typing import List

import mongoengine

from core import model
from data_mongo.model import User, Cases, Case, Tag
from data_mongo.services import guild_service

from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

async def batch_add(session, data, batch_size):
    for i in range(0, len(data), batch_size):
        session.add_all(data[i:i + batch_size])
        await session.commit()

async def setup():
    print("STARTING SETUP...")

    engine = get_engine()

    guild_mongo = guild_service.get_guild()
    async with get_session(engine) as session:
        guild_pg = model.GuildSetting(
            guild_id=int(os.environ.get("MAIN_GUILD_ID")),
            sabbath_mode=guild_mongo.sabbath_mode,
            ban_today_spam=guild_mongo.ban_today_spam_accounts,
        )
        session.add(guild_pg)

        locked_channels = [model.LockedChannel(channel_id=x) for x in guild_mongo.locked_channels]
        session.add_all(locked_channels)

        filter_excluded_guild = [model.FilterExcludedGuild(guild_id=x) for x in guild_mongo.filter_excluded_guilds]
        session.add_all(filter_excluded_guild)

        logging_excluded_channels = [model.LoggingExcludedChannel(channel_id=x) for x in
                                     guild_mongo.logging_excluded_channels]
        session.add_all(logging_excluded_channels)

        filter_words_pg = [model.FilterWord(
            phrase=x.word,
            bypass_level=x.bypass,
            should_notify=x.notify,
            is_piracy_phrase=x.piracy,
            disable_extra_checks=x.false_positive,
            filter_without_removing=x.silent_filter,
        ) for x in guild_mongo.filter_words]
        session.add_all(filter_words_pg)

        raid_phrase_pg = [model.RaidPhrase(
            phrase=x.word
        ) for x in guild_mongo.raid_phrases]
        session.add_all(raid_phrase_pg)
        await session.commit()

        users_mongo: List[User] = User.objects().all()
        users_pg = [model.User(
            user_id=x._id,
            is_clem=x.is_clem,
            was_warn_kicked=x.was_warn_kicked,
            is_birthday_banned=x.birthday_excluded,
            is_raid_verified=x.raid_verified,
            warn_points=x.warn_points,
            timezone=x.timezone,
            should_offline_report_ping=x.offline_report_ping,
            xp=x.xp,
            level=x.level,
            is_xp_frozen=x.is_xp_frozen
        ) for x in users_mongo]

        await batch_add(session, users_pg, 10000)
        await session.commit()

        birthday_pg = [model.UserBirthday(
            user_id=x._id,
            month=x.birthday[0],
            day=x.birthday[1]
        ) for x in users_mongo if x.birthday]
        session.add_all(birthday_pg)

        sticky_roles = [model.StickyRole(
            role_id=y,
            user_id=x._id
        ) for x in users_mongo for y in x.sticky_roles]

        await batch_add(session, sticky_roles, 10000)
        await session.commit()

        for _tag in guild_mongo.tags:
            tag: Tag = _tag
            pg_tag = model.Tag(
                phrase=tag.name,
                content=tag.content,
                creator_id=tag.added_by_id,
                updated_at=tag.added_date,
                uses=tag.use_count,
            )
            if (read_image := tag.image.read()) is not None:
                # upload to supabase.S3 and get the link
                ## generate random slug
                slug = os.urandom(8).hex()
                response = supabase.storage.from_(os.environ.get("SUPABASE_BUCKET")).upload(file=read_image,
                                                                                            path=f"tags/{slug}.png",
                                                                                            file_options={
                                                                                                "content-type": tag.image.content_type})
                pg_tag.image = str(response.url)

            session.add(pg_tag)
            await session.commit()

        tag_buttons = [model.TagButton(
            tag_name=x.name,
            label=y[0],
            link=y[1]
        ) for x in guild_mongo.tags for y in x.button_links]
        session.add_all(tag_buttons)

        for _tag in guild_mongo.memes:
            meme: Tag = _tag
            pg_meme = model.Meme(
                phrase=meme.name,
                content=meme.content,
                creator_id=meme.added_by_id,
                created_at=meme.added_date,
                uses=meme.use_count,
            )
            if (read_image := meme.image.read()) is not None:
                # upload to supabase.S3 and get the link
                ## generate random slug
                slug = os.urandom(8).hex()
                response = supabase.storage.from_(os.environ.get("SUPABASE_BUCKET")).upload(file=read_image,
                                                                                            path=f"memes/{slug}.png",
                                                                                            file_options={
                                                                                                "content-type": meme.image.content_type})
                pg_meme.image = str(response.url)

            session.add(pg_meme)
            await session.commit()

        user_cases_mongo: List[Cases] = Cases.objects().all()
        cases_with_user_id: List[Case] = []
        for u in user_cases_mongo:
            for c in u.cases:
                c.u = u._id
            cases_with_user_id.extend(u.cases)

        cases_with_user_id.sort(key=lambda x: x._id)

        cases_pg = [model.Case(
            user_id=c.u,
            mod_id=c.mod_id,
            punishment=c.punishment,
            reason=c.reason,
            date=c.date,
            until=c.until,
            lifted=c.lifted,
            lifted_by_id=c.lifted_by_id,
            lifted_reason=c.lifted_reason,
            lifted_date=c.lifted_date,
            type=c._type

        ) for c in cases_with_user_id]

        await batch_add(session, cases_pg, 10000)
        await session.commit()


    print("DONE!")


if __name__ == "__main__":
    if os.environ.get("DB_CONNECTION_STRING") is None:
        mongoengine.register_connection(
            host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT")), alias="default", name="botty")
    else:
        mongoengine.register_connection(
            host=os.environ.get("DB_CONNECTION_STRING"), alias="default", name="botty")
    res = asyncio.run(setup())
