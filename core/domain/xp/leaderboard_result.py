class LeaderboardEntry:
    def __init__(self, user_id: int, xp: int, level: int, rank: int):
        self.user_id = user_id
        self.xp = xp
        self.level = level
        self.rank = rank

    def __repr__(self):
        return f"<LeaderboardEntry(user_id={self.user_id}, xp={self.xp}, level={self.level}, rank={self.rank})>"