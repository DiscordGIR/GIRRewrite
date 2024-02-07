import discord

from utils.config import cfg

class Permissions:
    """A way of calculating a user's permissions.
    Level 0 is everyone.
    Level 1 is people with Member+ role
    Level 2 is people with Member Pro role
    Level 3 is people with Member Edition role
    Level 4 is people with Genius role
    Level 5 is people with Moderator role
    Level 6 is Admins
    Level 7 is the Guild owner (Aaron)
    Level 9 and 10 is the bot owner

    """

    def __init__(self):
        """Initialize Permissions.

        Parameters
        ----------
        bot : discord.Client
            Instance of Discord client to look up a user's roles, permissions, etc.
        settings : Settings
            State of the bot
            
        """

        roles_to_check = [
            "member_plus",
            "member_pro",
            "member_edition",
            "genius",
            "moderator",
            "administrator",
        ]

        for role in roles_to_check:
            try:
                getattr(cfg.roles, role)
            except AttributeError:
                raise AttributeError(
                    f"Database is not set up properly! Role '{role}' is missing. Please refer to README.md.")

        self._permission_mapping = {
            1: cfg.roles.member_plus,
            2: cfg.roles.member_pro,
            3: cfg.roles.member_edition,
            4: cfg.roles.genius,
            5: cfg.roles.moderator,
            6: cfg.roles.administrator,
        }

        # This dict maps a permission level to a lambda function which, when given the right paramters,
        # will return True or False if a user has that permission level.
        self._permissions = {
            0: lambda x, y: True,

            1: (lambda guild, m: self.has(guild, m, 2) or (guild.id == cfg.guild_id
                and guild.get_role(cfg.roles.member_plus) in m.roles)),

            2: (lambda guild, m: self.has(guild, m, 3) or (guild.id == cfg.guild_id
                and guild.get_role(cfg.roles.member_pro) in m.roles)),

            3: (lambda guild, m: self.has(guild, m, 4) or (guild.id == cfg.guild_id
                and guild.get_role(cfg.roles.member_edition) in m.roles)),

            4: (lambda guild, m: self.has(guild, m, 5) or (guild.id == cfg.guild_id
                and guild.get_role(cfg.roles.genius) in m.roles)),

            5: (lambda guild, m: self.has(guild, m, 6) or (guild.id == cfg.guild_id
                and guild.get_role(cfg.roles.moderator) in m.roles)),

            6: (lambda guild, m: self.has(guild, m, 7) or (guild.id == cfg.guild_id
                and guild.get_role(cfg.roles.administrator) in m.roles)),

            7: (lambda guild, m: self.has(guild, m, 9) or (guild.id == cfg.guild_id
                and m == guild.owner)),

            9: (lambda guild, m: guild.id == cfg.guild_id
                and m.id == cfg.owner_id),

            10: (lambda guild, m: guild.id == cfg.guild_id
                 and m.id == cfg.owner_id),
        }

        self._permission_names = {
            0: "Everyone and up",
            1: "Member Plus and up",
            2: "Member Pros and up",
            3: "Member Editions and up",
            4: "Geniuses and up",
            5: "Moderators and up",
            6: "Administrators and up",
            7: "Guild owner (Aaron) and up",
            9: "Bot owner",
            10: "Bot owner",
        }

    @property
    def lowest_level(self) -> int:
        return list(sorted(self._permission_names.keys()))[0]

    @property
    def highest_level(self) -> int:
        return list(sorted(self._permission_names.keys()))[-1]

    def has(self, guild: discord.Guild, member: discord.Member, level: int) -> bool:
        """Checks whether a user given by `member` has at least the permission level `level`
        in guild `guild`. Using the `self.permissions` dict-lambda thing.

        Parameters
        ----------
        guild : discord.Guild
            The guild to check
        member : discord.Member
            The member whose permissions we're checking
        level : int
            The level we want to check if the user has

        Returns
        -------
        bool
            True if the user has that level, otherwise False.
            
        """

        if self._permissions.get(level) is None:
            raise AttributeError(f"Undefined permission level {level}")

        return self._permissions[level](guild, member)

    def calculate_permissions(self, level: int):
        if self._permissions.get(level) is None:
            raise AttributeError(f"Undefined permission level {level}")

        return self.level_list(level)

    def level_info(self, level: int) -> str:
        return self._permission_names[level]


gatekeeper = Permissions()
