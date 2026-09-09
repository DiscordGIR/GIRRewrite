"""Modern community management tools inspired by popular general-purpose bots.

The module is intentionally configured through GIR's private dashboard.  Safety
actions start disabled, and every automatic action can be reviewed in Discord.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import zipfile
from io import BytesIO
import time
from urllib.parse import quote
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
import aiohttp
from data.model import IdentityHistory
from discord import app_commands
from discord.ext import commands, tasks

from utils import cfg, logger
from utils.framework.permissions import gatekeeper
from community_rules import (caps_percent, detect_scam, has_hidden_invite, has_invite,
                             has_suspicious_image_name, is_image_attachment,
                             normalize_obfuscated_text, recent_count)


from utils.runtime_paths import runtime_data_file


DATA_FILE = Path(os.environ.get("GIR_COMMUNITY_FILE", runtime_data_file("community.json")))
GAME_STATE_FILE = DATA_FILE.with_name("free-games-state.json")
GAME_STATUS_FILE = DATA_FILE.with_name("free-games-status.json")
GAME_REQUEST_FILE = DATA_FILE.with_name("free-games-request.json")
GAME_API = "https://www.gamerpower.com/api/giveaways"
EPIC_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=en-US&country=US&allowCountries=US"
CHEAPSHARK_API = "https://www.cheapshark.com/api/1.0/deals?onSale=1&pageSize=60&sortBy=Savings"

DEFAULTS = {
    "automod": {
        "enabled": False, "reportChannelID": 0, "deleteMessage": True,
        "timeoutHours": 168, "imageSpam": True, "imageThreshold": 4,
        "imageWindowSeconds": 20, "fastSpam": True, "messageThreshold": 7,
        "messageWindowSeconds": 8, "capsSpam": True, "capsPercent": 80,
        "mentionSpam": True, "mentionThreshold": 6, "inviteLinks": False,
        "scamDetection": True, "scamTimeoutHours": 168, "hiddenInvites": True,
        "suspiciousImageNames": True,
        "monitorAllChannels": True, "monitoredChannelIDs": [], "ignoredChannelIDs": [], "ignoredRoleIDs": [],
    },
    "reports": {"pingModeratorRole": True, "pingAdministratorRole": False, "pingRoleIDs": [],
                "pingUserIDs": [], "allowEveryone": True, "allowedRoleIDs": [], "allowedUserIDs": [],
                "ignoredUserIDs": [], "ignoredMessageIDs": [], "ignoredChannelIDs": [],
                "ignoredThreadIDs": [], "joinThreadsWhenMentioned": True, "notifyOnIgnoredPing": False,
                "includeImages": True, "maxLogImages": 4, "reportCooldownSeconds": 45,
                "batchBanMax": 50, "batchBanDelayMs": 1100, "detectInvisibleCharacters": True},
    "identityHistory": {"enabled": True, "refreshMinutes": 15, "storeUsernames": True,
                        "storeDisplayNames": True, "storeAvatarHashes": True, "storeRoles": True},
    "welcome": {"enabled": False, "channelID": 0, "message": "Welcome {mention} to {server}!", "goodbyeEnabled": False, "goodbyeMessage": "{name} left the server."},
    "autorole": {"enabled": False, "roleIDs": []},
    "starboard": {"enabled": False, "channelID": 0, "threshold": 5, "emoji": "⭐"},
    "suggestions": {"enabled": False, "channelID": 0},
    "freeGames": {"enabled": False, "channelID": 0, "platforms": ["pc", "steam", "epic-games-store", "ps4", "ps5", "xbox-one", "xbox-series-xs"], "types": ["game"], "sources": ["gamerpower", "epic", "cheapshark"], "offerMode": "both", "minimumDiscountPercent": 50, "checkMinutes": 15, "pingRoleID": 0, "minimumWorth": 0, "hideUnrated": False, "includeExpired": False, "maxPostsPerCheck": 5},
    "movieNight": {"enabled": False, "channelID": 0, "pingRoleID": 0},
    "relay": {"enabled": False, "destinationGuildID": 0, "messages": True, "edits": True,
              "deletes": True, "reactions": True, "channelRoutes": []},
    "customCommands": [], "autoResponses": [], "reactionRoles": [], "disabledCommands": [],
}

_SETTINGS_CACHE = None
_SETTINGS_MTIME = None


def _merge(base, incoming):
    result = dict(base)
    for key, value in incoming.items():
        result[key] = _merge(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else value
    return result


def load_settings():
    global _SETTINGS_CACHE, _SETTINGS_MTIME
    try:
        modified = DATA_FILE.stat().st_mtime_ns
        if _SETTINGS_CACHE is None or modified != _SETTINGS_MTIME:
            _SETTINGS_CACHE = _merge(DEFAULTS, json.loads(DATA_FILE.read_text()))
            _SETTINGS_MTIME = modified
        return _SETTINGS_CACHE
    except (OSError, ValueError, TypeError):
        if _SETTINGS_CACHE is None:
            _SETTINGS_CACHE = _merge(DEFAULTS, {})
        return _SETTINGS_CACHE


def render(template: str, member: discord.Member) -> str:
    return template.replace("{mention}", member.mention).replace("{name}", member.display_name).replace("{server}", member.guild.name)


class CommunitySuite(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.activity = defaultdict(lambda: deque(maxlen=30))
        self.images = defaultdict(lambda: deque(maxlen=30))
        self.star_posts = {}
        self.afk = {}
        self.relay_queue = asyncio.Queue(maxsize=10000)
        self.game_provider_health = {}
        self.game_check_lock = asyncio.Lock()
        self.identity_observed = {}
        self.recent_reports = {}
        self.report_batches = defaultdict(set)
        self.relay_worker = asyncio.create_task(self._relay_worker())
        self.free_game_check.start()
        self.free_game_request_check.start()

    def cog_unload(self):
        self.free_game_check.cancel()
        self.free_game_request_check.cancel()
        self.relay_worker.cancel()

    def settings(self):
        return load_settings()

    def _queue_relay(self, event: str, channel_id: int, payload: dict):
        relay = self.settings().get("relay", {})
        event_flag = {"message": "messages", "edit": "edits", "delete": "deletes", "reaction": "reactions"}[event]
        if not relay.get("enabled") or not relay.get(event_flag):
            return
        route = next((item for item in relay.get("channelRoutes", [])
                      if int(item.get("sourceChannelID", 0)) == channel_id), None)
        if not route:
            return
        payload.update({"event": event, "destinationChannelID": int(route.get("destinationChannelID", 0))})
        try:
            self.relay_queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.error("Audit relay queue is full; newest event was dropped")

    async def _relay_worker(self):
        while True:
            item = await self.relay_queue.get()
            try:
                destination = self.bot.get_channel(item["destinationChannelID"])
                if not isinstance(destination, discord.TextChannel):
                    continue
                colors = {"message": discord.Color.blurple(), "edit": discord.Color.orange(),
                          "delete": discord.Color.red(), "reaction": discord.Color.green()}
                titles = {"message": "Message", "edit": "Message edited", "delete": "Message deleted", "reaction": "Reaction"}
                embed = discord.Embed(title=titles[item["event"]], description=str(item.get("content") or "No text")[:3500],
                                      color=colors[item["event"]], timestamp=datetime.now(timezone.utc))
                embed.add_field(name="Member", value=f"{item.get('author', 'Unknown')} · `{item.get('authorID', 'Unknown')}`", inline=False)
                embed.add_field(name="Source", value=f"#{item.get('channel', 'unknown')} · `{item.get('channelID')}`", inline=True)
                if item.get("detail"):
                    embed.add_field(name="Details", value=str(item["detail"])[:1024], inline=True)
                if item.get("jumpURL"):
                    embed.add_field(name="Original", value=f"[Open message]({item['jumpURL']})", inline=False)
                attachments = item.get("attachments", [])
                if attachments:
                    embed.add_field(name="Attachments", value="\n".join(attachments)[:1024], inline=False)
                await destination.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Could not relay Discord audit event")
            finally:
                self.relay_queue.task_done()

    async def _fetch_json(self, session, name, url):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 201:
                    return name, []
                response.raise_for_status()
                return name, await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            logger.warning("Free-game provider %s failed: %s", name, error)
            return name, error

    @staticmethod
    def _epic_games(payload):
        rows = payload.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        games = []
        for row in rows:
            promotions = (row.get("promotions") or {}).get("promotionalOffers") or []
            offers = [offer for block in promotions for offer in block.get("promotionalOffers", [])]
            free = next((offer for offer in offers if offer.get("discountSetting", {}).get("discountPercentage") == 0), None)
            if not free:
                continue
            images = row.get("keyImages") or []
            image = next((item.get("url") for item in images if item.get("type") in {"OfferImageWide", "DieselStoreFrontWide"}), None)
            slug = row.get("productSlug") or row.get("urlSlug") or ""
            price = row.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice") or "Unknown"
            games.append({"id": f"epic:{row.get('id')}", "title": row.get("title"), "description": row.get("description"),
                          "platforms": "PC, Epic Games Store", "type": "game", "worth": price,
                          "end_date": free.get("endDate"), "image": image,
                          "open_giveaway_url": f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com/free-games",
                          "source": "Epic Games Store", "source_url": "https://store.epicgames.com/free-games"})
        return games

    @staticmethod
    def _cheapshark_games(rows):
        return [{"id": f"cheapshark:{row.get('dealID')}", "title": row.get("title"), "description": f"Discounted from ${float(row.get('normalPrice') or 0):.2f} to ${float(row.get('salePrice') or 0):.2f}.",
                 "platforms": "PC", "type": "game", "worth": f"${float(row.get('normalPrice') or 0):.2f}",
                 "salePrice": float(row.get("salePrice") or 0), "discountPercent": float(row.get("savings") or 0),
                 "end_date": None, "thumbnail": row.get("thumb"),
                 "open_giveaway_url": f"https://www.cheapshark.com/redirect?dealID={quote(str(row.get('dealID') or ''), safe='')}",
                 "source": "CheapShark", "source_url": "https://www.cheapshark.com/"}
                for row in rows]

    @staticmethod
    def _dedupe_games(games):
        unique = {}
        for game in games:
            key = re.sub(r"[^a-z0-9]", "", str(game.get("title", "")).lower())
            if key and key not in unique:
                unique[key] = game
        return list(unique.values())

    @staticmethod
    def _game_date(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            try:
                return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

    async def fetch_free_games(self, settings=None):
        settings = settings or {}
        enabled = set(settings.get("sources") or ["gamerpower", "epic", "cheapshark"])
        urls = {"gamerpower": GAME_API + "?sort-by=date", "epic": EPIC_API, "cheapshark": CHEAPSHARK_API}
        async with aiohttp.ClientSession(headers={"User-Agent": "GIR Discord Bot/1.0"}) as session:
            results = await asyncio.gather(*(self._fetch_json(session, name, url) for name, url in urls.items() if name in enabled))
        games = []
        for name, payload in results:
            if isinstance(payload, Exception):
                self.game_provider_health[name] = "Unavailable"
                continue
            self.game_provider_health[name] = f"OK · {len(payload.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', [])) if name == 'epic' else len(payload)} records"
            if name == "gamerpower":
                # Preserve GamerPower's historical IDs so upgrades do not repost every active offer.
                games.extend({**item, "id": str(item.get("id")), "source": "GamerPower", "source_url": "https://www.gamerpower.com/"} for item in payload)
            elif name == "epic":
                games.extend(self._epic_games(payload))
            elif name == "cheapshark":
                games.extend(self._cheapshark_games(payload))
        return self._dedupe_games(games)

    def filtered_games(self, games, settings):
        platforms = {str(value).lower() for value in settings.get("platforms", [])}
        types = {str(value).lower() for value in settings.get("types", [])}
        minimum_worth = max(0.0, float(settings.get("minimumWorth", 0) or 0))
        now = datetime.now(timezone.utc)
        offer_mode = str(settings.get("offerMode", "both")); minimum_discount = float(settings.get("minimumDiscountPercent", 50) or 0)

        def worth(game):
            match = re.search(r"\d+(?:\.\d+)?", str(game.get("worth") or "0").replace(",", ""))
            return float(match.group()) if match else 0.0

        def active(game):
            if settings.get("includeExpired") or not game.get("end_date"):
                return True
            end = self._game_date(game["end_date"])
            return end is None or end > now

        def offer_matches(game):
            source = str(game.get("source", "")).lower()
            text = " ".join(str(game.get(key, "")) for key in ("title", "description")).lower()
            free = game.get("salePrice") == 0 or source in {"gamerpower", "epic games store"} or bool(re.search(r"\b(free|giveaway)\b|\$0\.00|100% off", text))
            discounted = float(game.get("discountPercent") or 0) >= minimum_discount
            return free if offer_mode == "free" else discounted and not free if offer_mode == "discounts" else free or discounted

        aliases = {"epic-games-store": "epic games store", "ps4": "playstation 4", "ps5": "playstation 5",
                   "xbox-one": "xbox one", "xbox-series-xs": "xbox series x/s", "itchio": "itch.io"}

        def platform_matches(game):
            offered = {part.strip().lower() for part in str(game.get("platforms", "")).split(",")}
            return not platforms or any((value == "pc" and "pc" in offered) or aliases.get(value, value) in offered for value in platforms)

        return [game for game in games
                if platform_matches(game)
                and (not types or str(game.get("type", "")).lower() in types)
                and worth(game) >= minimum_worth
                and (not settings.get("hideUnrated") or worth(game) > 0)
                and offer_matches(game)
                and active(game)]

    @tasks.loop(minutes=15)
    async def free_game_check(self):
        settings = self.settings()["freeGames"]
        minutes = min(1440, max(5, int(settings.get("checkMinutes", 15) or 15)))
        if self.free_game_check.minutes != minutes:
            self.free_game_check.change_interval(minutes=minutes)
        await self.run_free_game_check(settings)

    def _save_game_status(self, state, **details):
        now = datetime.now(timezone.utc)
        payload = {"state": state, "updatedAt": int(now.timestamp()), "providerHealth": self.game_provider_health, **details}
        GAME_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = GAME_STATUS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temporary.replace(GAME_STATUS_FILE)
        return payload

    async def run_free_game_check(self, settings=None, *, manual=False):
        settings = settings or self.settings()["freeGames"]
        if not settings.get("enabled"):
            return self._save_game_status("disabled", message="Automatic free-game alerts are off")
        if self.game_check_lock.locked():
            return self._save_game_status("busy", message="A free-game check is already running")
        minutes = min(1440, max(5, int(settings.get("checkMinutes", 15) or 15)))
        channel = self.bot.get_channel(int(settings.get("channelID") or 0))
        if not channel:
            preferred = ("free-games", "freebies", "game-deals", "giveaways")
            guild = self.bot.get_guild(cfg.guild_id)
            by_name = {item.name.lower(): item for item in getattr(guild, "text_channels", [])}
            channel = next((by_name[name] for name in preferred if name in by_name), None)
            if channel:
                try:
                    saved = json.loads(DATA_FILE.read_text())
                    saved.setdefault("freeGames", {})["channelID"] = channel.id
                    temporary = DATA_FILE.with_suffix(".tmp")
                    temporary.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n")
                    temporary.replace(DATA_FILE)
                except (OSError, ValueError, TypeError):
                    logger.exception("Could not persist the recovered free-game channel")
        if not channel:
            logger.warning("Free-game alerts are enabled but no valid alert channel is available")
            return self._save_game_status("failed", message="No valid free-game channel is available")
        async with self.game_check_lock:
            started = datetime.now(timezone.utc)
            self._save_game_status("checking", startedAt=int(started.timestamp()), channelID=channel.id)
            try:
                games = self.filtered_games(await self.fetch_free_games(settings), settings)
                try:
                    saved = json.loads(GAME_STATE_FILE.read_text())
                    seen = set(saved.get("seen", [])); history = list(saved.get("history", []))
                except (OSError, ValueError, TypeError):
                    seen = {str(game.get("id")) for game in games}; history = []
                unseen = [item for item in games if str(item.get("id")) not in seen]
                post_limit = min(20, max(1, int(settings.get("maxPostsPerCheck", 5) or 5)))
                posted = []
                for game in reversed(unseen[:post_limit]):
                    await self.post_game(channel, game, settings)
                    record = {"id": str(game.get("id")), "title": str(game.get("title", "Free game"))[:256],
                              "source": str(game.get("source", "Unknown")), "channelID": channel.id,
                              "postedAt": int(datetime.now(timezone.utc).timestamp())}
                    posted.append(record); history.insert(0, record)
                seen.update(str(game.get("id")) for game in games)
                GAME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                temporary = GAME_STATE_FILE.with_suffix(".tmp")
                temporary.write_text(json.dumps({"seen": sorted(seen)[-4000:], "history": history[:250]}, indent=2) + "\n")
                temporary.replace(GAME_STATE_FILE)
                finished = datetime.now(timezone.utc)
                return self._save_game_status("complete", startedAt=int(started.timestamp()), lastCheck=int(finished.timestamp()),
                    nextCheck=int(finished.timestamp()) + minutes * 60, durationMs=int((finished - started).total_seconds() * 1000),
                    channelID=channel.id, offersFound=len(games), newOffers=len(unseen), posted=len(posted), manual=manual)
            except Exception as error:
                logger.exception("Free game check failed")
                return self._save_game_status("failed", startedAt=int(started.timestamp()), lastCheck=int(time.time()),
                                              channelID=channel.id, message=str(error)[:300], manual=manual)

    @free_game_check.before_loop
    async def before_free_game_check(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=10)
    async def free_game_request_check(self):
        try:
            request = json.loads(GAME_REQUEST_FILE.read_text())
        except (OSError, ValueError, TypeError):
            return
        if request.get("state") != "requested":
            return
        request["state"] = "working"; request["startedAt"] = int(time.time())
        temporary = GAME_REQUEST_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(request, indent=2) + "\n"); temporary.replace(GAME_REQUEST_FILE)
        result = await self.run_free_game_check(manual=True)
        request.update({"state": "complete" if result.get("state") == "complete" else result.get("state", "failed"),
                        "finishedAt": int(time.time()), "result": result})
        temporary.write_text(json.dumps(request, indent=2) + "\n"); temporary.replace(GAME_REQUEST_FILE)

    @free_game_request_check.before_loop
    async def before_free_game_request_check(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _game_platform(game):
        platforms = str(game.get("platforms", "")).lower()
        choices = (("steam", "Steam", "https://store.steampowered.com/search/?term="),
                   ("epic", "Epic Games Store", "https://store.epicgames.com/browse?q="),
                   ("gog", "GOG", "https://www.gog.com/en/games?query="),
                   ("xbox", "Xbox", "https://www.xbox.com/search/results?q="),
                   ("playstation", "PlayStation", "https://store.playstation.com/search/"),
                   ("switch", "Nintendo Switch", "https://www.nintendo.com/us/search/#q="),
                   ("itch", "itch.io", "https://itch.io/search?q="))
        for needle, label, search in choices:
            if needle in platforms:
                return label, search + quote(str(game.get("title", "")))
        return "PC and console", None

    @staticmethod
    def _claim_kind(game):
        if game.get("salePrice") is not None and float(game.get("salePrice") or 0) > 0:
            return f"{float(game.get('discountPercent') or 0):.0f}% off"
        text = " ".join(str(game.get(key, "")) for key in ("title", "description", "instructions")).lower()
        temporary = ("free weekend", "free week", "free to play until", "play for free", "open beta", "playtest")
        return "Free to play" if any(phrase in text for phrase in temporary) else "Free to keep"

    @staticmethod
    def game_embed(game):
        title = str(game.get("title", "Free game"))[:256]
        url = game.get("open_giveaway_url") or game.get("gamerpower_url") or "https://www.gamerpower.com/"
        end_time = CommunitySuite._game_date(game.get("end_date"))
        until = f" until {discord.utils.format_dt(end_time, 'd')}" if end_time else " while available"
        claim_kind = CommunitySuite._claim_kind(game)
        platform, _ = CommunitySuite._game_platform(game)
        description = f"**{claim_kind}**{until}\n\n{str(game.get('description', '')).strip()[:700]}".strip()
        embed = discord.Embed(title=title, url=url, description=description, color=discord.Color.from_rgb(88, 101, 242))
        embed.set_author(name=platform)
        if game.get("image") or game.get("thumbnail"):
            embed.set_image(url=game.get("image") or game.get("thumbnail"))
        source = str(game.get("source") or "Giveaway source")
        worth = str(game.get("worth") or "").strip()
        sale_price = game.get("salePrice")
        users = int(game.get("users") or 0)
        footer = f"via {source}"
        if worth and worth.lower() != "unknown":
            footer += f" · Usually {worth}"
        if sale_price is not None and float(sale_price or 0) > 0:
            footer += f" · Now ${float(sale_price):.2f}"
        if users:
            footer += f" · {users:,} claimed"
        embed.set_footer(text=footer[:2048])
        return embed

    @staticmethod
    def game_view(game):
        browser_url = str(game.get("open_giveaway_url") or game.get("gamerpower_url") or game.get("source_url") or "https://www.gamerpower.com/")
        platform, store_url = CommunitySuite._game_platform(game)
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Open in browser ↗", style=discord.ButtonStyle.link, url=browser_url[:512]))
        if store_url and store_url != browser_url:
            view.add_item(discord.ui.Button(label=f"Open in {platform} ↗"[:80], style=discord.ButtonStyle.link, url=store_url[:512]))
        return view

    async def post_game(self, channel, game, settings):
        embed = self.game_embed(game)
        role_id = int(settings.get("pingRoleID") or 0); role = channel.guild.get_role(role_id)
        mentions = discord.AllowedMentions(roles=[role] if role else False, users=False, everyone=False)
        await channel.send(content=role.mention if role else None, embed=embed, view=self.game_view(game), allowed_mentions=mentions)

    @staticmethod
    def _staff(member: discord.Member, settings: dict) -> bool:
        ignored = set(settings.get("ignoredRoleIDs", []))
        return member.guild_permissions.manage_messages or any(role.id in ignored for role in member.roles)

    @staticmethod
    def _ids(values):
        return {int(value) for value in values if str(value).isdigit()}

    def _ignored(self, message: discord.Message) -> bool:
        rules = self.settings().get("reports", {})
        channel_ids = {message.channel.id, int(getattr(message.channel, "parent_id", 0) or 0)}
        return (message.author.id in self._ids(rules.get("ignoredUserIDs", []))
                or message.id in self._ids(rules.get("ignoredMessageIDs", []))
                or bool(channel_ids & self._ids(rules.get("ignoredChannelIDs", [])))
                or message.channel.id in self._ids(rules.get("ignoredThreadIDs", [])))

    def _report_access(self, member: discord.Member) -> bool:
        rules = self.settings().get("reports", {})
        return (rules.get("allowEveryone", True) or member.guild_permissions.manage_messages
                or member.id in self._ids(rules.get("allowedUserIDs", []))
                or bool({role.id for role in member.roles} & self._ids(rules.get("allowedRoleIDs", []))))

    def _report_mentions(self, guild: discord.Guild):
        rules = self.settings().get("reports", {})
        role_ids = self._ids(rules.get("pingRoleIDs", []))
        if rules.get("pingModeratorRole", True):
            role_ids.add(int(getattr(cfg.roles, "moderator", 0) or 0))
        if rules.get("pingAdministratorRole", False):
            role_ids.add(int(getattr(cfg.roles, "administrator", 0) or 0))
        roles = [guild.get_role(value) for value in role_ids]
        roles = [role for role in roles if role]
        users = [guild.get_member(value) for value in self._ids(rules.get("pingUserIDs", []))]
        users = [user for user in users if user]
        content = " ".join([role.mention for role in roles] + [user.mention for user in users])
        return content or None, discord.AllowedMentions(roles=roles, users=users, everyone=False)

    def _report_channel(self, guild: discord.Guild):
        configured = int(self.settings().get("automod", {}).get("reportChannelID", 0) or 0)
        return (guild.get_channel(configured) if configured else None) or discord.utils.get(guild.text_channels, name="reports") or guild.get_channel(int(getattr(cfg.channels, "reports", 0) or 0))

    def _observe_identity(self, user, status="member", force=False):
        settings = self.settings().get("identityHistory", {})
        if not settings.get("enabled", True) or getattr(user, "bot", False):
            return
        now = datetime.now(timezone.utc)
        interval = max(1, min(1440, int(settings.get("refreshMinutes", 15)))) * 60
        if not force and now.timestamp() - self.identity_observed.get(user.id, 0) < interval:
            return
        self.identity_observed[user.id] = now.timestamp()
        names = {str(getattr(user, "name", "") or "")}
        displays = {str(getattr(user, "global_name", "") or ""), str(getattr(user, "display_name", "") or "")}
        avatar = getattr(getattr(user, "avatar", None), "key", None)
        update = {"set__last_seen": now, "set__status": status, "inc__observations": 1,
                  "set_on_insert__first_seen": now, "set_on_insert__account_created": getattr(user, "created_at", None)}
        if settings.get("storeUsernames", True): update["add_to_set__usernames"] = next(iter(names - {""}), None)
        if settings.get("storeDisplayNames", True): update["add_to_set__display_names"] = next(iter(displays - {""}), None)
        if settings.get("storeAvatarHashes", True) and avatar: update["add_to_set__avatar_hashes"] = avatar
        if settings.get("storeRoles", True) and hasattr(user, "roles"): update["set__role_ids"] = [role.id for role in user.roles]
        if getattr(user, "joined_at", None): update["set__last_joined"] = user.joined_at
        update = {key: value for key, value in update.items() if value is not None}
        try:
            IdentityHistory.objects(_id=user.id).update_one(upsert=True, **update)
        except Exception:
            logger.exception("Could not update identity history for %s", user.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self._observe_identity(member, "member", force=True)
        settings = self.settings()
        auto = settings["autorole"]
        if auto.get("enabled"):
            roles = [member.guild.get_role(int(role_id)) for role_id in auto.get("roleIDs", [])]
            roles = [role for role in roles if role and role < member.guild.me.top_role]
            if roles:
                try:
                    await member.add_roles(*roles, reason="GIR automatic member role")
                except discord.HTTPException:
                    logger.exception("Could not assign automatic roles")
        welcome = settings["welcome"]
        if welcome.get("enabled"):
            channel = member.guild.get_channel(int(welcome.get("channelID") or 0))
            if channel:
                await channel.send(render(str(welcome.get("message", "")), member), allowed_mentions=discord.AllowedMentions(users=True))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self._observe_identity(member, "left", force=True)
        welcome = self.settings()["welcome"]
        if welcome.get("goodbyeEnabled"):
            channel = member.guild.get_channel(int(welcome.get("channelID") or 0))
            if channel:
                await channel.send(render(str(welcome.get("goodbyeMessage", "")), member))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.guild.id != cfg.guild_id:
            return
        self._queue_relay("message", message.channel.id, {"author": str(message.author), "authorID": message.author.id,
            "channel": message.channel.name, "channelID": message.channel.id, "content": message.content,
            "jumpURL": message.jump_url, "attachments": [item.url for item in message.attachments]})
        settings = self.settings()
        self._observe_identity(message.author)
        visible_content = normalize_obfuscated_text(message.content) if settings.get("reports", {}).get("detectInvisibleCharacters", True) else message.content
        lowered = visible_content.lower().strip()

        if (isinstance(message.channel, discord.Thread) and self.bot.user in message.mentions
                and settings.get("reports", {}).get("joinThreadsWhenMentioned", True)):
            try:
                await message.channel.join()
                if settings.get("reports", {}).get("notifyOnIgnoredPing", False):
                    await message.reply("I joined this thread and can monitor it now.", mention_author=False)
            except discord.HTTPException:
                logger.warning("GIR could not join mentioned thread %s", message.channel.id)
        if self._ignored(message):
            return

        attachment_text = " ".join(f"{item.filename} {getattr(item, 'description', '') or ''}" for item in message.attachments)
        scam_reason = detect_scam(f"{visible_content} {attachment_text}")
        if settings["automod"].get("scamDetection", True) and scam_reason and not gatekeeper.has(message.guild, message.author, 1):
            scam_rule = dict(settings["automod"])
            scam_rule.update({"deleteMessage": True, "timeoutHours": int(scam_rule.get("scamTimeoutHours", 168))})
            await self._moderate(message, scam_rule, scam_reason)
            return

        if (settings["automod"].get("hiddenInvites", True) and has_hidden_invite(message.content)
                and not gatekeeper.has(message.guild, message.author, 1)):
            hidden_rule = dict(settings["automod"])
            hidden_rule.update({"deleteMessage": True, "timeoutHours": 168})
            await self._moderate(message, hidden_rule,
                                 "Discord invite obscured with invisible or compatibility characters")
            return

        # Prevent image dumps from accounts that have not reached Member+.
        # This focused safety rule stays active when general AutoMod is off.
        image_attachments = [attachment for attachment in message.attachments
                             if is_image_attachment(attachment.content_type, attachment.filename)]
        suspicious_names = [attachment.filename for attachment in image_attachments
                            if has_suspicious_image_name(attachment.filename)]
        suspicious_name = settings["automod"].get("suspiciousImageNames", True) and suspicious_names
        if (len(image_attachments) >= 4 or suspicious_name) and not gatekeeper.has(message.guild, message.author, 1):
            image_rule = dict(settings["automod"])
            image_rule.update({"deleteMessage": True, "timeoutHours": 168})
            trigger = (f"{len(image_attachments)} images in one message from a user below Member+"
                       if len(image_attachments) >= 4 else
                       f"Suspicious campaign image filename: {suspicious_names[0]}")
            await self._moderate(message, image_rule, trigger)
            return

        if message.author.id in self.afk:
            self.afk.pop(message.author.id, None)
            try:
                await message.channel.send(f"Welcome back, {message.author.mention}. I cleared your AFK status.", delete_after=7)
            except discord.HTTPException:
                pass
        for member in message.mentions:
            if member.id in self.afk:
                await message.channel.send(f"{member.display_name} is AFK: {self.afk[member.id]}", reference=message, mention_author=False)

        for item in settings.get("customCommands", []):
            if item.get("enabled", True) and lowered == str(item.get("trigger", "")).lower().strip():
                await message.channel.send(str(item.get("response", ""))[:2000], reference=message, mention_author=False)
                break
        for item in settings.get("autoResponses", []):
            trigger = str(item.get("trigger", "")).lower().strip()
            match_mode = str(item.get("matchMode", "contains"))
            matched = lowered == trigger if match_mode == "exact" else bool(re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", lowered)) if match_mode == "word" else trigger in lowered
            allowed_channels = {int(value) for value in item.get("channelIDs", []) if str(value).isdigit()}
            message_channels = {message.channel.id, int(getattr(message.channel, "parent_id", 0) or 0)}
            if (item.get("enabled", True) and trigger and matched
                    and (not allowed_channels or allowed_channels & message_channels)):
                emoji_text = str(item.get("emojiText", ""))[:100]
                content = " ".join(value for value in (emoji_text, str(item.get("response", ""))[:1900]) if value).strip()
                sticker = message.guild.get_sticker(int(item.get("stickerID", 0) or 0))
                for reaction in item.get("reactionEmojis", [])[:10]:
                    try:
                        await message.add_reaction(str(reaction))
                    except discord.HTTPException:
                        logger.warning("Could not add configured automatic reaction %s", reaction)
                if content or sticker:
                    send_options = {"reference": message, "mention_author": False}
                    if sticker:
                        send_options["stickers"] = [sticker]
                    await message.channel.send(content or None, **send_options)
                break

        auto = settings["automod"]
        monitored = set(auto.get("monitoredChannelIDs", []))
        channel_ids = {message.channel.id, getattr(message.channel, "parent_id", 0)}
        if (not auto.get("enabled") or self._staff(message.author, auto)
                or channel_ids & set(auto.get("ignoredChannelIDs", []))
                or (not auto.get("monitorAllChannels", True) and not channel_ids & monitored)):
            return
        now = time.monotonic()
        key = (message.guild.id, message.author.id)
        self.activity[key].append(now)
        if image_attachments:
            self.images[key].extend([now] * len(image_attachments))
        findings = []
        window = int(auto.get("imageWindowSeconds", 20))
        image_count = recent_count(self.images[key], now, window)
        if auto.get("imageSpam") and image_count >= int(auto.get("imageThreshold", 4)):
            findings.append(f"{image_count} image attachments in {window} seconds")
        msg_window = int(auto.get("messageWindowSeconds", 8))
        message_count = recent_count(self.activity[key], now, msg_window)
        if auto.get("fastSpam") and message_count >= int(auto.get("messageThreshold", 7)):
            findings.append(f"{message_count} messages in {msg_window} seconds")
        if auto.get("capsSpam") and len(message.content) >= 20 and caps_percent(message.content) >= int(auto.get("capsPercent", 80)):
            findings.append("mostly capital letters")
        if auto.get("mentionSpam") and len(message.mentions) + len(message.role_mentions) >= int(auto.get("mentionThreshold", 6)):
            findings.append("too many mentions")
        if auto.get("inviteLinks") and has_invite(visible_content):
            findings.append("Discord invite link")
        if findings:
            await self._moderate(message, auto, findings[0])
            self.activity[key].clear(); self.images[key].clear()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild.id == cfg.guild_id:
            self._observe_identity(after, "member", force=True)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if guild.id == cfg.guild_id:
            self._observe_identity(user, "banned", force=True)

    async def _preserve_image_evidence(self, message: discord.Message, maximum: int) -> list[discord.File]:
        images = [item for item in message.attachments
                  if is_image_attachment(item.content_type, item.filename)][:maximum]
        if not images:
            return []
        files = []
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for index, item in enumerate(images, 1):
                try:
                    async with session.get(item.url) as response:
                        response.raise_for_status()
                        data = await response.content.read(8 * 1024 * 1024 + 1)
                    if len(data) > 8 * 1024 * 1024:
                        logger.warning("Skipped oversized moderation evidence attachment %s", item.id)
                        continue
                    suffix = Path(item.filename).suffix.casefold()
                    suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ".png"
                    files.append(discord.File(BytesIO(data), filename=f"evidence-{index}{suffix}"))
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                    logger.warning("Could not preserve moderation evidence attachment %s", item.id)
        return files

    async def _moderate(self, message: discord.Message, settings: dict, trigger: str):
        report_settings = self.settings().get("reports", {})
        maximum = max(1, min(4, int(report_settings.get("maxLogImages", 4))))
        evidence = (await self._preserve_image_evidence(message, maximum)
                    if report_settings.get("includeImages", True) else [])
        if settings.get("deleteMessage"):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        hours = max(0, min(int(settings.get("timeoutHours", 0)), 336))
        action = "Message removed"
        if hours and isinstance(message.author, discord.Member) and message.author < message.guild.me.top_role:
            try:
                await message.author.timeout(datetime.now(timezone.utc) + timedelta(hours=hours), reason=f"GIR AutoMod: {trigger}")
                action = f"Timed out for {hours} hours"
            except discord.HTTPException:
                action = "Message removed; timeout could not be applied"
        channel = self._report_channel(message.guild)
        if not channel:
            return
        group = hashlib.sha256(trigger.casefold().encode()).hexdigest()[:16]
        self.report_batches[group].add(message.author.id)
        cooldown = max(0, min(3600, int(self.settings().get("reports", {}).get("reportCooldownSeconds", 45))))
        report_key = (message.author.id, group)
        if time.monotonic() - self.recent_reports.get(report_key, 0) < cooldown:
            return
        self.recent_reports[report_key] = time.monotonic()
        embed = discord.Embed(title="🚨 Automatic moderation alert", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Member", value=f"{message.author.mention}\n`{message.author.id}`", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Trigger", value=trigger, inline=True)
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Campaign group", value=f"`{group}` · {len(self.report_batches[group])} account(s)", inline=False)
        if evidence:
            embed.set_image(url=f"attachment://{evidence[0].filename}")
        elif message.attachments and report_settings.get("includeImages", True):
            embed.set_image(url=message.attachments[0].url)
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Ban", style=discord.ButtonStyle.danger, custom_id=f"gir:report:ban:{message.author.id}"))
        view.add_item(discord.ui.Button(label="Ban matching", style=discord.ButtonStyle.danger, custom_id=f"gir:report:banbatch:{group}"))
        view.add_item(discord.ui.Button(label="Dismiss", style=discord.ButtonStyle.secondary, custom_id=f"gir:report:dismiss:{message.author.id}"))
        content, mentions = self._report_mentions(message.guild)
        extras = []
        if evidence:
            for item in evidence[1:]:
                extra = discord.Embed(url=message.jump_url)
                extra.set_image(url=f"attachment://{item.filename}")
                extras.append(extra)
        elif report_settings.get("includeImages", True):
            for item in message.attachments[1:maximum]:
                if is_image_attachment(item.content_type, item.filename):
                    extra = discord.Embed(url=message.jump_url); extra.set_image(url=item.url); extras.append(extra)
        await channel.send(content=content, embeds=[embed, *extras], files=evidence,
                           view=view, allowed_mentions=mentions)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        custom_id = (interaction.data or {}).get("custom_id", "") if interaction.type == discord.InteractionType.component else ""
        if not custom_id.startswith("gir:report:"):
            return
        _, _, action, user_id = custom_id.split(":", 3)
        if action == "banbatch":
            if not interaction.user.guild_permissions.ban_members:
                await interaction.response.send_message("You need permission to ban members to use this.", ephemeral=True); return
            report_settings = self.settings().get("reports", {})
            target_set = set(self.report_batches.get(user_id, set()))
            if not target_set:
                async for report_message in interaction.channel.history(limit=500):
                    for report_embed in report_message.embeds:
                        fields = {field.name: field.value for field in report_embed.fields}
                        if f"`{user_id}`" in fields.get("Campaign group", ""):
                            match = re.search(r"`(\d{15,22})`", fields.get("Member", ""))
                            if match: target_set.add(int(match.group(1)))
            targets = list(target_set)[:max(1, min(100, int(report_settings.get("batchBanMax", 50))))]
            if not targets:
                await interaction.response.send_message("No matching accounts remain in this active campaign group.", ephemeral=True); return
            await interaction.response.defer(ephemeral=True); banned, failed = 0, 0
            delay = max(250, min(5000, int(report_settings.get("batchBanDelayMs", 1100)))) / 1000
            for target in targets:
                try:
                    await interaction.guild.ban(discord.Object(id=target), reason=f"Matching AutoMod campaign reviewed by {interaction.user}")
                    banned += 1
                except discord.HTTPException:
                    failed += 1
                await asyncio.sleep(delay)
            await interaction.followup.send(f"Batch review complete: **{banned} banned**, **{failed} failed**. Campaign `{user_id}`.", ephemeral=True)
            embed = interaction.message.embeds[0]; embed.add_field(name="Batch review", value=f"{interaction.user.mention}: {banned} banned, {failed} failed", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            return
        if action == "ban":
            if not interaction.user.guild_permissions.ban_members:
                await interaction.response.send_message("You need permission to ban members to use this.", ephemeral=True); return
            try:
                await interaction.guild.ban(discord.Object(id=int(user_id)), reason=f"Reviewed AutoMod report by {interaction.user}")
                embed = interaction.message.embeds[0]
                embed.add_field(name="Review outcome", value=f"Banned by {interaction.user.mention}\nCause: {next((f.value for f in embed.fields if f.name == 'Trigger'), 'reported message')}", inline=False)
                await interaction.response.edit_message(content=f"Banned by {interaction.user.mention}", embed=embed, view=None)
            except discord.Forbidden:
                await interaction.response.send_message("Discord would not allow that ban. Check GIR's Ban Members permission and role position.", ephemeral=True)
        else:
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message("You need permission to manage messages to dismiss reports.", ephemeral=True); return
            await interaction.response.edit_message(content=f"Dismissed by {interaction.user.mention}", view=None)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id != cfg.guild_id or payload.member is None or payload.member.bot:
            return
        channel = self.bot.get_channel(payload.channel_id)
        self._queue_relay("reaction", payload.channel_id, {"author": str(payload.member), "authorID": payload.user_id,
            "channel": getattr(channel, "name", "unknown"), "channelID": payload.channel_id,
            "content": str(payload.emoji), "detail": "Reaction added",
            "jumpURL": f"https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}"})
        settings = self.settings()
        for item in settings.get("reactionRoles", []):
            if item.get("enabled", True) and int(item.get("messageID", 0)) == payload.message_id and str(item.get("emoji")) == str(payload.emoji):
                role = payload.member.guild.get_role(int(item.get("roleID", 0)))
                if role:
                    await payload.member.add_roles(role, reason="GIR reaction role")
        star = settings["starboard"]
        if not star.get("enabled") or str(payload.emoji) != str(star.get("emoji", "⭐")):
            return
        channel = self.bot.get_channel(payload.channel_id)
        destination = self.bot.get_channel(int(star.get("channelID") or 0))
        if not channel or not destination:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return
        reaction = next((r for r in message.reactions if str(r.emoji) == str(payload.emoji)), None)
        if not reaction or reaction.count < int(star.get("threshold", 5)):
            return
        embed = discord.Embed(description=message.content or "Shared attachment", color=discord.Color.gold(), timestamp=message.created_at)
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Original", value=f"[Open message]({message.jump_url})")
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        existing = self.star_posts.get(message.id)
        if existing:
            try:
                post = await destination.fetch_message(existing); await post.edit(content=f"⭐ **{reaction.count}**", embed=embed); return
            except discord.HTTPException:
                pass
        post = await destination.send(content=f"⭐ **{reaction.count}**", embed=embed)
        self.star_posts[message.id] = post.id

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id != cfg.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id); member = guild.get_member(payload.user_id) if guild else None
        channel = self.bot.get_channel(payload.channel_id)
        if member and not member.bot:
            self._queue_relay("reaction", payload.channel_id, {"author": str(member), "authorID": payload.user_id,
                "channel": getattr(channel, "name", "unknown"), "channelID": payload.channel_id,
                "content": str(payload.emoji), "detail": "Reaction removed",
                "jumpURL": f"https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}"})
        for item in self.settings().get("reactionRoles", []):
            if item.get("enabled", True) and int(item.get("messageID", 0)) == payload.message_id and str(item.get("emoji")) == str(payload.emoji):
                guild = self.bot.get_guild(payload.guild_id); member = guild.get_member(payload.user_id) if guild else None
                role = guild.get_role(int(item.get("roleID", 0))) if guild else None
                if member and role:
                    await member.remove_roles(role, reason="GIR reaction role removed")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.guild.id != cfg.guild_id or before.author.bot or before.content == after.content:
            return
        self._queue_relay("edit", before.channel.id, {"author": str(before.author), "authorID": before.author.id,
            "channel": before.channel.name, "channelID": before.channel.id,
            "content": f"Before:\n{before.content[:1600]}\n\nAfter:\n{after.content[:1600]}", "jumpURL": after.jump_url})

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        message = payload.cached_message
        if payload.guild_id != cfg.guild_id or not message or message.author.bot:
            return
        self._queue_relay("delete", payload.channel_id, {"author": str(message.author), "authorID": message.author.id,
            "channel": message.channel.name, "channelID": payload.channel_id, "content": message.content,
            "attachments": [item.url for item in message.attachments]})

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="suggest", description="Send an idea to the server suggestion board")
    async def suggest(self, interaction: discord.Interaction, idea: str):
        settings = self.settings()["suggestions"]
        channel = interaction.guild.get_channel(int(settings.get("channelID") or 0)) if settings.get("enabled") else None
        if not channel:
            await interaction.response.send_message("Suggestions are not set up yet.", ephemeral=True); return
        embed = discord.Embed(title="New suggestion", description=idea[:4000], color=discord.Color.teal())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        post = await channel.send(embed=embed); await post.add_reaction("👍"); await post.add_reaction("👎")
        await interaction.response.send_message("Your suggestion was posted.", ephemeral=True)

    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="announce", description="Create and post a custom embed in a channel")
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str,
                       color: str = "5865F2", image_url: str | None = None,
                       thumbnail_url: str | None = None, footer: str | None = None):
        color_value = color.lstrip("#")
        try:
            if len(color_value) != 6:
                raise ValueError
            embed_color = discord.Color(int(color_value, 16))
        except ValueError:
            await interaction.response.send_message("Use a six-character color such as 5865F2.", ephemeral=True); return
        for label, value in (("image", image_url), ("thumbnail", thumbnail_url)):
            if value and not value.startswith("https://"):
                await interaction.response.send_message(f"The {label} must use an HTTPS link.", ephemeral=True); return
        embed = discord.Embed(title=title[:256], description=message[:4000], color=embed_color, timestamp=datetime.now(timezone.utc))
        if image_url:
            embed.set_image(url=image_url)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        embed.set_footer(text=(footer or f"Posted by {interaction.user.display_name}")[:2048])
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message("Embed posted.", ephemeral=True)

    @app_commands.default_permissions(manage_channels=True)
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="slowmode", description="Change how often members can send messages")
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=seconds, reason=f"Changed by {interaction.user}")
        await interaction.response.send_message("Slow mode turned off." if seconds == 0 else f"Members can now send one message every {seconds} seconds.", ephemeral=True)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="report", description="Privately report a member to the moderation team")
    async def report(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        channel = self._report_channel(interaction.guild)
        if not channel:
            await interaction.response.send_message("The reports channel is not set up yet.", ephemeral=True); return
        if not self._report_access(interaction.user):
            await interaction.response.send_message("You are not in a role allowed to submit reports.", ephemeral=True); return
        embed = discord.Embed(title="Member report", description=reason[:4000], color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Reported member", value=f"{member.mention}\n`{member.id}`")
        embed.add_field(name="Reported by", value=f"{interaction.user.mention}\n`{interaction.user.id}`")
        content, mentions = self._report_mentions(interaction.guild)
        await channel.send(content=content, embed=embed, allowed_mentions=mentions); await interaction.response.send_message("Your report was sent privately to the moderators.", ephemeral=True)

    async def report_message(self, interaction: discord.Interaction, message: discord.Message):
        if not self._report_access(interaction.user):
            await interaction.response.send_message("You are not in a role allowed to report messages.", ephemeral=True); return
        if self._ignored(message):
            await interaction.response.send_message("GIR is configured to ignore that message, person, channel, or thread.", ephemeral=True); return
        channel = self._report_channel(interaction.guild)
        if not channel:
            await interaction.response.send_message("The reports channel is not set up yet.", ephemeral=True); return
        embed = discord.Embed(title="Message reported", description=(message.content or "No message text")[:3500], color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Message author", value=f"{message.author.mention}\n`{message.author.id}`", inline=True)
        embed.add_field(name="Reported by", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=True)
        embed.add_field(name="Location", value=f"{message.channel.mention}\n[Open message]({message.jump_url})", inline=False)
        content, mentions = self._report_mentions(interaction.guild)
        await channel.send(content=content, embed=embed, allowed_mentions=mentions)
        await interaction.response.send_message("That message was sent privately to the moderation team.", ephemeral=True)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="afk", description="Let people know you are away")
    async def afk_command(self, interaction: discord.Interaction, reason: str = "Away for a while"):
        self.afk[interaction.user.id] = reason[:200]
        await interaction.response.send_message("Your AFK status is set. It will clear when you send a message.", ephemeral=True)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(("Heads 🪙", "Tails 🪙")))

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="roll", description="Roll dice")
    async def roll(self, interaction: discord.Interaction, sides: app_commands.Range[int, 2, 1000] = 6):
        await interaction.response.send_message(f"🎲 You rolled **{random.randint(1, sides)}** out of {sides}.")

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="choose", description="Let GIR choose from a comma-separated list")
    async def choose(self, interaction: discord.Interaction, choices: str):
        items = [item.strip() for item in choices.split(",") if item.strip()]
        if len(items) < 2:
            await interaction.response.send_message("Give me at least two choices separated by commas.", ephemeral=True); return
        await interaction.response.send_message(f"I choose **{random.choice(items)}**.")

    @app_commands.default_permissions(manage_nicknames=True)
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(name="nickname", description="Change or clear a member's nickname")
    async def nickname(self, interaction: discord.Interaction, member: discord.Member, nickname: str | None = None):
        await member.edit(nick=nickname, reason=f"Changed by {interaction.user}")
        await interaction.response.send_message("Nickname updated.", ephemeral=True)

    games = app_commands.Group(name="games", description="Free game alerts and current giveaways", guild_ids=[cfg.guild_id])

    @games.command(name="free", description="List free games and giveaways available now")
    async def games_free(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        settings = self.settings()["freeGames"]
        try:
            games = self.filtered_games(await self.fetch_free_games(settings), settings)[:10]
        except Exception:
            await interaction.followup.send("I could not reach the free-game list right now.", ephemeral=True); return
        if not games:
            await interaction.followup.send("No matching giveaways are listed right now.", ephemeral=True); return
        lines = [f"• [{game.get('title', 'Free game')}]({game.get('open_giveaway_url') or game.get('gamerpower_url')}) — {game.get('platforms', 'Unknown platform')}" for game in games]
        embed = discord.Embed(title="Free games available now", description="\n".join(lines)[:4000], color=discord.Color.green())
        embed.add_field(name="Sources", value=", ".join(sorted({str(game.get("source", "Unknown")) for game in games})))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @games.command(name="status", description="Show how free-game alerts are configured")
    async def games_status(self, interaction: discord.Interaction):
        settings = self.settings()["freeGames"]
        channel = interaction.guild.get_channel(int(settings.get("channelID") or 0))
        embed = discord.Embed(title="Free-game alerts", color=discord.Color.green())
        embed.add_field(name="Automatic alerts", value="On" if settings.get("enabled") else "Off")
        embed.add_field(name="Channel", value=channel.mention if channel else "Not selected")
        embed.add_field(name="Platforms", value=", ".join(settings.get("platforms", [])) or "All", inline=False)
        embed.add_field(name="Offer types", value=", ".join(settings.get("types", [])) or "All")
        embed.add_field(name="Minimum normal price", value=f"${float(settings.get('minimumWorth', 0) or 0):.2f}")
        embed.add_field(name="Check schedule", value=f"Every {int(settings.get('checkMinutes', 15))} minutes")
        health = "\n".join(f"**{name.title()}**: {state}" for name, state in sorted(self.game_provider_health.items()))
        if health:
            embed.add_field(name="Source health", value=health[:1024], inline=False)
        runtime = {}
        try:
            runtime = json.loads(GAME_STATUS_FILE.read_text())
        except (OSError, ValueError, TypeError):
            pass
        if runtime.get("lastCheck"):
            checked = datetime.fromtimestamp(runtime["lastCheck"], timezone.utc)
            embed.add_field(name="Last check", value=f"{discord.utils.format_dt(checked, 'R')} · {runtime.get('offersFound', 0)} matches · {runtime.get('posted', 0)} posted", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @games.command(name="check", description="Check all enabled free-game sources now")
    @app_commands.default_permissions(manage_guild=True)
    async def games_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await self.run_free_game_check(manual=True)
        await interaction.followup.send(f"Check **{result['state']}** · {result.get('offersFound', 0)} matches · {result.get('posted', 0)} new posts.", ephemeral=True)

    @games.command(name="preview", description="Preview the next matching free-game embed")
    async def games_preview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        settings = self.settings()["freeGames"]
        games = self.filtered_games(await self.fetch_free_games(settings), settings)
        if not games:
            await interaction.followup.send("No matching offers are available to preview.", ephemeral=True); return
        await interaction.followup.send(embed=self.game_embed(games[0]), view=self.game_view(games[0]), ephemeral=True)

    movie = app_commands.Group(name="movie", description="Plan a server movie night", guild_ids=[cfg.guild_id])

    @movie.command(name="suggest", description="Suggest a movie and let members vote")
    async def movie_suggest(self, interaction: discord.Interaction, title: str, notes: str = ""):
        settings = self.settings()["movieNight"]
        channel = interaction.guild.get_channel(int(settings.get("channelID") or 0)) if settings.get("enabled") else None
        if not channel:
            await interaction.response.send_message("Movie night is not set up yet.", ephemeral=True); return
        embed = discord.Embed(title=f"🎬 {title[:240]}", description=notes[:3500] or "Would you watch this?", color=discord.Color.purple())
        embed.set_footer(text=f"Suggested by {interaction.user.display_name}")
        post = await channel.send(embed=embed); await post.add_reaction("👍"); await post.add_reaction("👎")
        await interaction.response.send_message("Your movie was added for voting.", ephemeral=True)

    @movie.command(name="poll", description="Create a movie-night vote from comma-separated titles")
    @app_commands.default_permissions(manage_events=True)
    async def movie_poll(self, interaction: discord.Interaction, titles: str, when: str = "Date to be decided"):
        options = [value.strip() for value in titles.split(",") if value.strip()][:10]
        if len(options) < 2:
            await interaction.response.send_message("Add at least two movie titles separated by commas.", ephemeral=True); return
        settings = self.settings()["movieNight"]; channel = interaction.guild.get_channel(int(settings.get("channelID") or 0)) or interaction.channel
        numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        embed = discord.Embed(title="🎬 Movie night vote", description="\n".join(f"{numbers[i]} {title}" for i, title in enumerate(options)), color=discord.Color.purple())
        embed.add_field(name="When", value=when[:1024]); role = interaction.guild.get_role(int(settings.get("pingRoleID") or 0))
        await interaction.response.defer(ephemeral=True); post = await channel.send(content=role.mention if role else None, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
        for emoji in numbers[:len(options)]: await post.add_reaction(emoji)
        await interaction.followup.send("Movie-night vote posted.", ephemeral=True)

    emoji = app_commands.Group(name="emoji", description="Manage server emojis", guild_ids=[cfg.guild_id], default_permissions=discord.Permissions(manage_emojis=True))

    async def image_from_url(self, url: str) -> bytes:
        if not url.startswith("https://"):
            raise ValueError("Use an HTTPS image URL.")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status(); data = await response.read()
        if len(data) > 256 * 1024: raise ValueError("Discord emoji images must be smaller than 256 KB.")
        return data

    @emoji.command(name="add", description="Add an emoji from an image URL")
    async def emoji_add(self, interaction: discord.Interaction, name: str, image_url: str):
        await interaction.response.defer(ephemeral=True)
        try: emoji = await interaction.guild.create_custom_emoji(name=name[:32], image=await self.image_from_url(image_url), reason=f"Added by {interaction.user}")
        except Exception as error: await interaction.followup.send(f"I could not add that emoji: {error}", ephemeral=True); return
        await interaction.followup.send(f"Added {emoji}.", ephemeral=True)

    @emoji.command(name="copy", description="Copy a custom emoji into this server")
    async def emoji_copy(self, interaction: discord.Interaction, emoji: str, new_name: str = ""):
        match = re.fullmatch(r"<a?:([A-Za-z0-9_]+):(\d+)>", emoji)
        if not match: await interaction.response.send_message("Paste a custom Discord emoji, such as <:name:123>.", ephemeral=True); return
        extension = "gif" if emoji.startswith("<a:") else "png"; url = f"https://cdn.discordapp.com/emojis/{match.group(2)}.{extension}"
        await interaction.response.defer(ephemeral=True)
        try: created = await interaction.guild.create_custom_emoji(name=(new_name or match.group(1))[:32], image=await self.image_from_url(url), reason=f"Copied by {interaction.user}")
        except Exception as error: await interaction.followup.send(f"I could not copy that emoji: {error}", ephemeral=True); return
        await interaction.followup.send(f"Added {created}.", ephemeral=True)

    @emoji.command(name="delete", description="Delete a server emoji by name")
    async def emoji_delete(self, interaction: discord.Interaction, name: str):
        emoji = discord.utils.get(interaction.guild.emojis, name=name)
        if not emoji: await interaction.response.send_message("I could not find that emoji.", ephemeral=True); return
        await emoji.delete(reason=f"Deleted by {interaction.user}"); await interaction.response.send_message(f"Deleted `{name}`.", ephemeral=True)

    @emoji.command(name="list", description="List this server's custom emojis")
    async def emoji_list(self, interaction: discord.Interaction):
        text = " ".join(str(emoji) for emoji in interaction.guild.emojis) or "This server has no custom emojis."
        await interaction.response.send_message(text[:2000], ephemeral=True)

    @emoji.command(name="stats", description="Show emoji capacity and usage")
    async def emoji_stats(self, interaction: discord.Interaction):
        static = sum(not item.animated for item in interaction.guild.emojis); animated = sum(item.animated for item in interaction.guild.emojis)
        await interaction.response.send_message(f"Static emojis: **{static}**\nAnimated emojis: **{animated}**\nServer emoji limit: **{interaction.guild.emoji_limit}** per type", ephemeral=True)

    @emoji.command(name="export", description="Export server emojis as a ZIP file")
    async def emoji_export(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True); archive = BytesIO()
        async with aiohttp.ClientSession() as session:
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for item in interaction.guild.emojis:
                    try:
                        async with session.get(item.url, timeout=15) as response: data = await response.read()
                        bundle.writestr(f"{item.name}.{('gif' if item.animated else 'png')}", data)
                    except Exception: pass
        archive.seek(0); await interaction.followup.send(file=discord.File(archive, filename=f"{interaction.guild.name}-emojis.zip"), ephemeral=True)

    @emoji.command(name="import", description="Import PNG, JPEG, GIF, or WebP images from a ZIP")
    async def emoji_import(self, interaction: discord.Interaction, file: discord.Attachment):
        if file.size > 8 * 1024 * 1024: await interaction.response.send_message("Choose a ZIP smaller than 8 MB.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True); added = 0
        try:
            with zipfile.ZipFile(BytesIO(await file.read())) as bundle:
                safe = [info for info in bundle.infolist() if not info.is_dir() and info.file_size <= 256*1024 and info.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))][:50]
                for info in safe:
                    name = re.sub(r"[^A-Za-z0-9_]", "_", Path(info.filename).stem)[:32]
                    if len(name) < 2: continue
                    try: await interaction.guild.create_custom_emoji(name=name, image=bundle.read(info), reason=f"Imported by {interaction.user}"); added += 1
                    except discord.HTTPException: pass
        except (zipfile.BadZipFile, OSError): await interaction.followup.send("That file is not a readable ZIP.", ephemeral=True); return
        await interaction.followup.send(f"Imported **{added}** emojis.", ephemeral=True)

    @emoji.command(name="role-icon", description="Set a role icon from an image URL")
    async def emoji_role_icon(self, interaction: discord.Interaction, role: discord.Role, image_url: str):
        await interaction.response.defer(ephemeral=True)
        try: await role.edit(display_icon=await self.image_from_url(image_url), reason=f"Changed by {interaction.user}")
        except Exception as error: await interaction.followup.send(f"I could not set that role icon: {error}", ephemeral=True); return
        await interaction.followup.send("Role icon updated.", ephemeral=True)

    @emoji.command(name="pfp", description="Make an emoji from a Discord user's profile picture")
    async def emoji_pfp(self, interaction: discord.Interaction, name: str, discord_id: str):
        if not discord_id.isdigit(): await interaction.response.send_message("Enter a numeric Discord user ID.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(discord_id)); data = await user.display_avatar.with_size(128).read()
            emoji = await interaction.guild.create_custom_emoji(name=name[:32], image=data, reason=f"Added by {interaction.user}")
        except Exception as error: await interaction.followup.send(f"I could not create that emoji: {error}", ephemeral=True); return
        await interaction.followup.send(f"Added {emoji} from {user}.", ephemeral=True)

    sticker = app_commands.Group(name="sticker", description="Manage server stickers", guild_ids=[cfg.guild_id], default_permissions=discord.Permissions(manage_emojis=True))

    @sticker.command(name="list", description="List this server's stickers")
    async def sticker_list(self, interaction: discord.Interaction):
        stickers = await interaction.guild.fetch_stickers(); text = "\n".join(f"• {item.name} — {item.url}" for item in stickers) or "This server has no stickers."
        await interaction.response.send_message(text[:2000], ephemeral=True)

    @sticker.command(name="add", description="Add a sticker from an image URL")
    async def sticker_add(self, interaction: discord.Interaction, name: str, image_url: str, emoji: str, description: str = "Server sticker"):
        await interaction.response.defer(ephemeral=True)
        try:
            data = await self.image_from_url(image_url); extension = Path(image_url.split("?", 1)[0]).suffix.lower() or ".png"
            sticker = await interaction.guild.create_sticker(name=name[:30], description=description[:100], emoji=emoji, file=discord.File(BytesIO(data), filename="sticker" + extension), reason=f"Added by {interaction.user}")
        except Exception as error: await interaction.followup.send(f"I could not add that sticker: {error}", ephemeral=True); return
        await interaction.followup.send(f"Added sticker `{sticker.name}`.", ephemeral=True)

    @sticker.command(name="delete", description="Delete a server sticker by name")
    async def sticker_delete(self, interaction: discord.Interaction, name: str):
        sticker = discord.utils.get(await interaction.guild.fetch_stickers(), name=name)
        if not sticker: await interaction.response.send_message("I could not find that sticker.", ephemeral=True); return
        await sticker.delete(reason=f"Deleted by {interaction.user}"); await interaction.response.send_message(f"Deleted `{name}`.", ephemeral=True)

    @sticker.command(name="export", description="Export server stickers as a ZIP file")
    async def sticker_export(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True); archive = BytesIO(); stickers = await interaction.guild.fetch_stickers()
        async with aiohttp.ClientSession() as session:
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for item in stickers:
                    try:
                        async with session.get(item.url, timeout=15) as response: data = await response.read()
                        extension = ".png" if item.format in {discord.StickerFormatType.png, discord.StickerFormatType.apng} else ".json"
                        bundle.writestr(item.name + extension, data)
                    except Exception: pass
        archive.seek(0); await interaction.followup.send(file=discord.File(archive, filename=f"{interaction.guild.name}-stickers.zip"), ephemeral=True)

    @sticker.command(name="import", description="Import PNG or APNG stickers from a ZIP")
    async def sticker_import(self, interaction: discord.Interaction, file: discord.Attachment):
        if file.size > 8 * 1024 * 1024: await interaction.response.send_message("Choose a ZIP smaller than 8 MB.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True); added = 0
        try:
            with zipfile.ZipFile(BytesIO(await file.read())) as bundle:
                safe = [info for info in bundle.infolist() if not info.is_dir() and info.file_size <= 512*1024 and info.filename.lower().endswith((".png", ".apng"))][:15]
                for info in safe:
                    name = re.sub(r"[^A-Za-z0-9_ ]", "", Path(info.filename).stem)[:30]
                    if len(name) < 2: continue
                    try:
                        upload = discord.File(BytesIO(bundle.read(info)), filename=Path(info.filename).name)
                        await interaction.guild.create_sticker(name=name, description="Imported by GIR", emoji="⭐", file=upload, reason=f"Imported by {interaction.user}"); added += 1
                    except discord.HTTPException: pass
        except (zipfile.BadZipFile, OSError): await interaction.followup.send("That file is not a readable ZIP.", ephemeral=True); return
        await interaction.followup.send(f"Imported **{added}** stickers.", ephemeral=True)


async def setup(bot):
    cog = CommunitySuite(bot)
    await bot.add_cog(cog)
