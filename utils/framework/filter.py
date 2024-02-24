import string
from typing import List

import discord
from data.model import FilterWord
from data.services import guild_service
from fold_to_ascii import fold
from utils.framework import gatekeeper


async def find_triggered_filters(input, member: discord.Member) -> List[FilterWord]:
    """
    BAD WORD FILTER
    """
    symbols = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
               u"abBrdeex3nnKnmHonpcTyoxu4wwbbbeoRABBrDEEX3NNKNMHONPCTyOXU4WWbbbEOR")

    tr = {ord(a): ord(b) for a, b in zip(*symbols)}

    input_lowercase = fold(input.translate(tr).lower()).lower().strip(":")   
    folded_without_spaces = "".join(input_lowercase.split())
    folded_without_spaces_and_punctuation = folded_without_spaces.translate(
        str.maketrans('', '', string.punctuation))

    db_guild = guild_service.get_guild()

    if not input_lowercase:
        return []
    # reported = False

    words_found = []
    for word in await guild_service.get_filtered_words():
        if gatekeeper.has(member.guild, member, word.bypass):
            continue

        filter_word_without_spaces = "".join(word.word.lower().split())
        if (word.word.lower() in input_lowercase) or \
            (not word.false_positive and word.word.lower() in folded_without_spaces) or \
                (not word.false_positive and word.word.lower() in folded_without_spaces_and_punctuation or
                    (not word.false_positive and filter_word_without_spaces in folded_without_spaces_and_punctuation)):

            # remove all whitespace, punctuation in message and run filter again
            if word.false_positive and word.word.lower() not in input_lowercase.split():
                continue

            if word.notify:
                return [word]

            words_found.append(word)
    return words_found


async def find_triggered_raid_phrases(input, member):
    symbols = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
               u"abBrdeex3nnKnmHonpcTyoxu4wwbbbeoRABBrDEEX3NNKNMHONPCTyOXU4WWbbbEOR")

    tr = {ord(a): ord(b) for a, b in zip(*symbols)}

    folded_message = fold(input.translate(tr).lower()).lower()
    folded_without_spaces = "".join(folded_message.split())
    folded_without_spaces_and_punctuation = folded_without_spaces.translate(
        str.maketrans('', '', string.punctuation))

    if folded_message:
        for word in await guild_service.get_raid_phrases():
            if not gatekeeper.has(member.guild, member, word.bypass):
                if (word.word.lower() in folded_message) or \
                    (not word.false_positive and word.word.lower() in folded_without_spaces) or \
                        (not word.false_positive and word.word.lower() in folded_without_spaces_and_punctuation):
                    # remove all whitespace, punctuation in message and run filter again
                    if word.false_positive and word.word.lower() not in folded_message.split():
                        continue

                    return word
