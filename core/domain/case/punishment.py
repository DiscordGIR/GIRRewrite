from core.model import CaseType

pun_map = {
    "KICK": "Kicked",
    "BAN": "Banned",
    "CLEM": "Clemmed",
    "UNBAN": "Unbanned",
    "MUTE": "Duration",
    "REMOVEPOINTS": "Points removed"
}


def determine_emoji(_type: CaseType):
    match _type:
        case CaseType.KICK:
            return "👢"
        case CaseType.BAN:
            return "❌"
        case CaseType.UNBAN:
            return "✅"
        case CaseType.MUTE:
            return "🔇"
        case CaseType.WARN:
            return "⚠️"
        case CaseType.UNMUTE:
            return "🔈"
        case CaseType.LIFTWARN:
            return "⚠️"
        case CaseType.REMOVEPOINTS:
            return "⬇️"
        case CaseType.CLEM:
            return "👎"
        case _:
            return "❓"
