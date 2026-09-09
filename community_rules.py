"""Pure detection helpers for the community suite."""
import re
import unicodedata
from typing import Optional


INVITE_PATTERN = re.compile(
    r"(?:discord\.gg/(?:invite/)?|discord(?:app)?\.com/invite/|(?:dsc|invite)\.gg/|discord\.(?:io|li|me|st)/)[A-Za-z0-9-]{2,}",
    re.I,
)
IMAGE_EXTENSIONS = {".avif", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".webp"}
URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.I)
SCAM_BRANDS = re.compile(r"\b(mr\s*beast|steam|paypal|cash\s*app|coinbase|microsoft|xbox|playstation)\b", re.I)
SCAM_REWARDS = re.compile(r"\b(giveaway|winner|won|free\s+(?:nitro|gift|money|crypto)|bonus|reward|claim|double\s+(?:your|my)|investment)\b", re.I)
SCAM_ACTIONS = re.compile(r"\b(click|verify|connect|scan|deposit|send|withdraw|activate|sign\s*in|login|dm\s+me|message\s+me)\b", re.I)
SCAM_URGENCY = re.compile(r"\b(now|today only|limited time|act fast|expires?|within\s+\d+\s*(?:minutes?|hours?))\b", re.I)
SCAM_SECRETS = re.compile(r"\b(seed phrase|recovery phrase|private key|wallet phrase)\b", re.I)
SUSPICIOUS_HOST = re.compile(r"(?:xn--|bit\.ly|tinyurl\.com|t\.co|discord(?:-|\.)?gift|disc[o0]rd|ste[a4]m|mrbeast)[^\s/]*", re.I)
INVISIBLE_CHARACTERS = re.compile(r"[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\uffa0]")


def normalize_obfuscated_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(character for character in normalized
                   if unicodedata.category(character) not in {"Cf", "Cc"})


def has_hidden_invite(text: str) -> bool:
    """Detect an invite that only appears after removing hiding characters."""
    original = str(text or "")
    return has_invite(normalize_obfuscated_text(original)) and not has_invite(original)


def has_suspicious_image_name(filename: str) -> bool:
    """Match the generic numbered image name used by a recurring compromise campaign."""
    return bool(re.fullmatch(r"1\.[A-Za-z0-9]{1,10}", str(filename or "").casefold()))


def caps_percent(text: str) -> int:
    letters = [char for char in text if char.isalpha()]
    return round(100 * sum(char.isupper() for char in letters) / len(letters)) if letters else 0


def has_invite(text: str) -> bool:
    return bool(INVITE_PATTERN.search(text))


def recent_count(timestamps: list[float], now: float, window_seconds: int) -> int:
    return sum(now - stamp <= window_seconds for stamp in timestamps)


def is_image_attachment(content_type, filename: str) -> bool:
    """Recognize Discord image uploads even when their MIME type is unavailable."""
    if content_type and content_type.casefold().startswith("image/"):
        return True
    return any(filename.casefold().endswith(extension) for extension in IMAGE_EXTENSIONS)


def detect_scam(text: str) -> Optional[str]:
    """Return a plain-language reason when several independent scam signals agree."""
    normalized = " ".join(normalize_obfuscated_text(text).split())
    if not normalized:
        return None
    has_url = bool(URL_PATTERN.search(normalized))
    brand = SCAM_BRANDS.search(normalized)
    reward = SCAM_REWARDS.search(normalized)
    action = SCAM_ACTIONS.search(normalized)
    urgency = SCAM_URGENCY.search(normalized)
    secret = SCAM_SECRETS.search(normalized)
    suspicious_host = SUSPICIOUS_HOST.search(normalized) if has_url else None
    score = sum((bool(brand), bool(reward), bool(action), bool(urgency), bool(secret) * 2,
                 bool(suspicious_host) * 2, has_url))
    # Requiring multiple independent signals prevents ordinary discussion such as
    # "I saw a MrBeast scam" from being moderated.
    if score < 4 or not (has_url or secret):
        return None
    if brand and re.search(r"mr\s*beast", brand.group(), re.I):
        return "possible fake MrBeast giveaway"
    if secret:
        return "possible credential or wallet theft"
    if reward:
        return "possible fake giveaway or reward"
    return "possible phishing link"
