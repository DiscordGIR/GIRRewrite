from datetime import datetime, timedelta
import pytz

from data.services import guild_service

eastern_timezone = pytz.timezone('US/Eastern')


MONTH_MAPPING = {
    "January": {
        "value": 1,
        "max_days": 31,
    },
    "February": {
        "value": 2,
        "max_days": 29,
    },
    "March": {
        "value": 3,
        "max_days": 31,
    },
    "April": {
        "value": 4,
        "max_days": 30,
    },
    "May": {
        "value": 5,
        "max_days": 31,
    },
    "June": {
        "value": 6,
        "max_days": 30,
    },
    "July": {
        "value": 7,
        "max_days": 31,
    },
    "August": {
        "value": 8,
        "max_days": 31,
    },
    "September": {
        "value": 9,
        "max_days": 30,
    },
    "October": {
        "value": 10,
        "max_days": 31,
    },
    "November": {
        "value": 11,
        "max_days": 30,
    },
    "December": {
        "value": 12,
        "max_days": 31,
    },
    
}


async def give_user_birthday_role(bot, user, guild):
    birthday_role = guild.get_role((await guild_service.get_roles()).role_birthday)
    if birthday_role is None:
        return

    if birthday_role in user.roles:
        return

    # calculate the different between now and tomorrow 12AM
    now = datetime.now(eastern_timezone)
    h = now.hour / 24
    m = now.minute / 60 / 24

    # schedule a task to remove birthday role (tomorrow) 12AM
    try:
        time = now + timedelta(days=1-h-m)
        bot.tasks.schedule_remove_bday(user.id, time)
    except Exception:
        return

    await user.add_roles(birthday_role)

    try:
        await user.send(f"According to my calculations, today is your birthday! We've given you the {birthday_role} role for 24 hours.")
    except Exception:
        pass
