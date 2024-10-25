class UserXpResult:
    def __init__(self, xp: int, level: int, rank: int, total_count: int, is_clem: bool = False):
        self.xp = xp
        self.level = level
        self.rank = rank
        self.total_count = total_count
        self.is_clem = False

    def __repr__(self):
        return f"<UserXpResult(xp={self.xp}, level={self.level}, rank={self.rank}, total_count={self.total_count})>"
