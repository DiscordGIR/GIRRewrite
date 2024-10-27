class UserXpAndLeaderboardRank:
    def __init__(self, xp: int, level: int, rank: int, total_user_count: int, is_clem: bool):
        self.xp = xp
        self.level = level
        self.rank = rank
        self.total_user_count = total_user_count
        self.is_clem = is_clem

    def __repr__(self):
        return f"<UserXpAndLeaderboardRank(xp={self.xp}, level={self.level}, rank={self.rank}, total_user_count={self.total_user_count})>"