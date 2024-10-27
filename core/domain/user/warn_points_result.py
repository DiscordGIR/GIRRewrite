class WarnPoints:
    def __init__(self, user_id: int, warn_points: int):
        self.user_id = user_id
        self.warn_points = warn_points

    def __str__(self):
        return f"<WarnPoints(user_id={self.user_id}, warn_points={self.warn_points})>"