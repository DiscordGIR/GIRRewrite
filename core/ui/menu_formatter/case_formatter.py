def format_cases_page(ctx, entries, current_page, all_pages):
    """Formats the page for the cases embed.

    Parameters
    ----------
    entry : dict
        "The dictionary for the entry"
    all_pages : list
        "All entries that we will eventually iterate through"
    current_page : number
        "The number of the page that we are currently on"

    Returns
    -------
    discord.Embed
        "The embed that we will send"

    """
    page_count = 0

    user = ctx.case_user
    u = user_service.get_user(user.id)

    for page in all_pages:
        for case in page:
            page_count = page_count + 1
    embed = discord.Embed(
        title=f'Cases - {u.warn_points} warn points', color=discord.Color.blurple())
    embed.set_author(name=user, icon_url=user.display_avatar)
    for case in entries:
        timestamp = case.date
        formatted = f"{format_dt(timestamp, style='F')} ({format_dt(timestamp, style='R')})"
        if case._type == "WARN" or case._type == "LIFTWARN":
            if case.lifted:
                embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id} [LIFTED]',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Lifted by**: {case.lifted_by_tag}\n**Lift reason**: {case.lifted_reason}\n**Warned on**: {formatted}',
                                inline=True)
            elif case._type == "LIFTWARN":
                embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id} [LIFTED (legacy)]',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Warned on**: {formatted}',
                                inline=True)
            else:
                embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Warned on**: {formatted}',
                                inline=True)
        elif case._type == "MUTE" or case._type == "REMOVEPOINTS":
            embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                            value=f'**{pun_map[case._type]}**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Time**: {formatted}',
                            inline=True)
        elif case._type in pun_map:
            embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                            value=f'**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**{pun_map[case._type]} on**: {formatted}',
                            inline=True)
        else:
            embed.add_field(name=f'{determine_emoji(case._type)} Case #{case._id}',
                            value=f'**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Time**: {formatted}',
                            inline=True)
    embed.set_footer(
        text=f"Page {current_page} of {len(all_pages)} - newest cases first ({page_count} total cases)")
    return embed

pun_map = {
    "KICK": "Kicked",
    "BAN": "Banned",
    "CLEM": "Clemmed",
    "UNBAN": "Unbanned",
    "MUTE": "Duration",
    "REMOVEPOINTS": "Points removed"
}


def determine_emoji(type):
    emoji_dict = {
        "KICK": "👢",
        "BAN": "❌",
        "UNBAN": "✅",
        "MUTE": "🔇",
        "WARN": "⚠️",
        "UNMUTE": "🔈",
        "LIFTWARN": "⚠️",
        "REMOVEPOINTS": "⬇️",
        "CLEM": "👎"
    }
    return emoji_dict[type]