from datetime import datetime

from core.model import Case, CaseType


class CaseResult:
    def __init__(self, case_id: int, user_id: int, mod_id: int, case_type: CaseType, punishment: str, reason: str, date: datetime, until: datetime, lifted: bool, lifted_by_id: int, lifted_by_tag: str, lifted_reason: str, lifted_date: datetime, mod_tag: str, warn_points: int):
        self.case_id = case_id
        self.user_id = user_id
        self.mod_id = mod_id
        self.case_type = case_type
        self.punishment = punishment
        self.reason = reason
        self.date = date
        self.until = until
        self.lifted = lifted
        self.lifted_by_id = lifted_by_id
        self.lifted_by_tag = lifted_by_tag
        self.lifted_reason = lifted_reason
        self.lifted_date = lifted_date
        self.mod_tag = mod_tag
        self.warn_points = warn_points

    @classmethod
    def from_orm(cls, case: Case, warn_points: int):
        return cls(
            case_id=case.case_id,
            user_id=case.user_id,
            mod_id=case.mod_id,
            mod_tag=case.mod_tag,
            case_type=case.case_type,
            punishment=case.punishment,
            reason=case.reason,
            date=case.date,
            until=case.until,
            lifted=case.lifted,
            lifted_by_id=case.lifted_by_id,
            lifted_by_tag=case.lifted_by_tag,
            lifted_reason=case.lifted_reason,
            lifted_date=case.lifted_date,
            warn_points=warn_points
        )