import asyncio
import os
from typing import List, Tuple

import aiohttp
import mongoengine
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_mongo.model import User, Cases, Case, Tag
from data_mongo.model.guild import Guild
from data_mongo.services import guild_service

from models import base as Base
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

load_dotenv(find_dotenv())


async def setup():
    engine = create_engine(os.environ.get("PG_CONNECTION_STRING"), echo=True)

    print("STARTING SETUP...")

    with Session(engine) as session:
        guild_mongo = guild_service.get_guild()
        guild_pg = Base.GuildSetting(
            guild_id=int(os.environ.get("MAIN_GUILD_ID")),
            sabbath_mode=guild_mongo.sabbath_mode,
            ban_today_spam=guild_mongo.ban_today_spam_accounts,
        )

        session.add(guild_pg)

        locked_channels = [Base.LockedChannel(channel_id=x) for x in guild_mongo.locked_channels]
        session.add_all(locked_channels)

        filter_excluded_guild = [Base.FilterExcludedGuild(guild_id=x) for x in guild_mongo.filter_excluded_guilds]
        session.add_all(filter_excluded_guild)

        logging_excluded_channels = [Base.LoggingExcludedChannel(channel_id=x) for x in guild_mongo.logging_excluded_channels]
        session.add_all(logging_excluded_channels)

        filter_words_pg = [Base.FilterWord(
            phrase=x.word,
            bypass_level=x.bypass,
            should_notify=x.notify,
            is_piracy_phrase=x.piracy,
            disable_extra_checks=x.false_positive,
            filter_without_removing=x.silent_filter,
        ) for x in guild_mongo.filter_words]
        session.add_all(filter_words_pg)

        raid_phrase_pg = [Base.RaidPhrase(
            phrase=x.word
        ) for x in guild_mongo.raid_phrases]
        session.add_all(raid_phrase_pg)

        users_mongo: List[User] = User.objects().all()
        users_pg = [Base.User(
            user_id=x._id,
            is_clem=x.is_clem,
            was_warn_kicked=x.was_warn_kicked,
            is_birthday_banned=x.birthday_excluded,
            is_raid_verified=x.raid_verified,
            warn_points=x.warn_points,
            timezone=x.timezone,
            should_offline_report_ping=x.offline_report_ping
        ) for x in users_mongo]

        session.add_all(users_pg)

        session.commit()

        birthday_pg = [Base.UserBirthday(
            user_id=x._id,
            month=x.birthday[0],
            day=x.birthday[1]
        ) for x in users_mongo if x.birthday]
        session.add_all(birthday_pg)

        sticky_roles = [Base.StickyRole(
            role_id=y,
            user_id=x._id
        ) for x in users_mongo for y in x.sticky_roles]

        session.add_all(sticky_roles)

        user_xp_pg = [Base.UserXp(
            user_id=x._id,
            xp=x.xp,
            level=x.level,
            is_xp_frozen=x.is_xp_frozen
        ) for x in users_mongo]
        session.add_all(user_xp_pg)

        tags_pg = []
        for _tag in guild_mongo.tags:
            tag: Tag = _tag
            pg_tag = Base.Tag(
                phrase=tag.name,
                content=tag.content,
                creator_id=tag.added_by_id,
                updated_at=tag.added_date,
                uses=tag.use_count,
            )
            if (read_image := tag.image.read()) is not None:
                # upload to supabase S3 and get the link
                ## generate random slug
                slug = os.urandom(8).hex()
                response = supabase.storage.from_(os.environ.get("SUPABASE_BUCKET")).upload(file=read_image, path=f"tags/{slug}.png", file_options={"content-type": tag.image.content_type})
                pg_tag.image = str(response.url)

            tags_pg.append(pg_tag)

        session.add_all(tags_pg)

        tag_buttons = [Base.TagButton(
            tag_name=x.name,
            label=y[0],
            link=y[1]
        ) for x in guild_mongo.tags for y in x.button_links]
        session.add_all(tag_buttons)

        user_cases_mongo: List[Cases] = Cases.objects().all()
        cases_with_user_id: List[Case] = []
        for u in user_cases_mongo:
            for c in u.cases:
                c.u = u._id
            cases_with_user_id.extend(u.cases)

        cases_with_user_id.sort(key=lambda x: x._id)

        cases_pg = [Base.Case(
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

        session.add_all(cases_pg)

        session.commit()

        print("DONE!")


if __name__ == "__main__":
    if os.environ.get("DB_CONNECTION_STRING") is None:
        mongoengine.register_connection(
            host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT")), alias="default", name="botty")
    else:
        mongoengine.register_connection(
            host=os.environ.get("DB_CONNECTION_STRING"), alias="default", name="botty")
    res = asyncio.get_event_loop().run_until_complete(setup())
