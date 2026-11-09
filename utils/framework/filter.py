import string
from typing import List

import discord
from data.model import FilterWord
from data.services import guild_service
from fold_to_ascii import fold
from utils.framework import gatekeeper


_SYMBOLS = ("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
            "abBrdeex3nnKnmHonpcTyoxu4wwbbbeoRABBrDEEX3NNKNMHONPCTyOXU4WWbbbEOR")
_TRANSLATION = {ord(a): ord(b) for a, b in zip(*_SYMBOLS)}
_PUNCTUATION = str.maketrans('', '', string.punctuation)


def _normalized(text, strip_colons=False):
    folded = fold(text.translate(_TRANSLATION).lower()).lower()
    if strip_colons:
        folded = folded.strip(':')
    tokens = folded.split()
    compact = ''.join(tokens)
    return folded, compact, compact.translate(_PUNCTUATION), frozenset(tokens)


async def find_triggered_filters(input, member: discord.Member) -> List[FilterWord]:
    folded, compact, plain, tokens = _normalized(input, strip_colons=True)
    if not folded:
        return []
    found = []
    permissions = {}
    for word in await guild_service.get_filtered_words():
        if word.bypass not in permissions:
            permissions[word.bypass] = gatekeeper.has(member.guild, member, word.bypass)
        if permissions[word.bypass]:
            continue
        if (word.lower in folded or (not word.false_positive and
                (word.lower in compact or word.lower in plain or word.compact in plain))):
            if word.false_positive and word.lower not in tokens:
                continue
            if word.notify:
                return [word]
            found.append(word)
    return found


def has_only_silent_filtered_words(triggered_filter_words: List[FilterWord]):
    return all(word.silent_filter for word in triggered_filter_words)


async def find_triggered_raid_phrases(input, member):
    # Raid phrases intentionally retain surrounding colons and don't use the
    # word filter's extra compact-rule matching branch.
    folded, compact, plain, tokens = _normalized(input)
    if not folded:
        return None
    permissions = {}
    for word in await guild_service.get_raid_phrases():
        if word.bypass not in permissions:
            permissions[word.bypass] = gatekeeper.has(member.guild, member, word.bypass)
        if permissions[word.bypass]:
            continue
        if word.lower in folded or (not word.false_positive and
                                   (word.lower in compact or word.lower in plain)):
            if word.false_positive and word.lower not in tokens:
                continue
            return word
