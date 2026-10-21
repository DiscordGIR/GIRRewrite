"""XP persistence with one atomic update on the common existing-user path."""
from dataclasses import dataclass

from pymongo import ReturnDocument
from data.model import User


def level_for_xp(current_xp):
    # Preserve the legacy thresholds, including the initial level offset.
    level = 0
    threshold = 0
    while threshold <= current_xp:
        threshold += 45 * level * (level // 10 + 1)
        level += 1
    return level


@dataclass(frozen=True)
class XpResult:
    xp: int
    level: int


def award_xp(member_id, amount):
    collection = User._get_collection()
    eligible = {"_id": member_id, "is_xp_frozen": {"$ne": True}, "is_clem": {"$ne": True}}
    user = collection.find_one_and_update(
        eligible, {"$inc": {"xp": amount}}, return_document=ReturnDocument.AFTER,
        projection={"xp": 1, "level": 1},
    )
    if user is None:
        # Only insert defaults for a genuinely new profile. Never upsert using
        # the eligibility filter: a frozen profile already owns this _id.
        defaults = dict(User(_id=member_id).to_mongo())
        defaults.pop("_id", None)
        collection.update_one({"_id": member_id}, {"$setOnInsert": defaults}, upsert=True)
        user = collection.find_one_and_update(
            eligible, {"$inc": {"xp": amount}}, return_document=ReturnDocument.AFTER,
            projection={"xp": 1, "level": 1},
        )
    if user is None:
        return None
    level = level_for_xp(user["xp"])
    if level > user.get("level", 0):
        # An older worker cannot lower the level or undo a concurrent XP reset.
        collection.update_one({**eligible, "xp": {"$gte": user["xp"]}},
                              {"$max": {"level": level}})
    return XpResult(user["xp"], level)
