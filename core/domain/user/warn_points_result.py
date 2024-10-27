class WarnPointsResult:
    def __init__(self, user_id: int, points: int):
        self.user_id = user_id
        self.points = points

    def __str__(self):
        return f"<WarnPoints(user_id={self.user_id}, warn_points={self.points})>"