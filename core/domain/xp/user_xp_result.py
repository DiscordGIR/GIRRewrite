class UserXpAndLeaderboardRank:
    def __init__(self, user_id: int, xp: int, level: int, rank: int, total_user_count: int, is_clem: bool):
        self.user_id = user_id
        self.xp = xp
        self.level = level
        self.rank = rank
        self.total_user_count = total_user_count
        self.is_clem = is_clem

    def __repr__(self):
        return f"<UserXpAndLeaderboardRank(user_id={self.user_id}, xp={self.xp}, level={self.level}, rank={self.rank}, total_user_count={self.total_user_count})>"