from data.database import database_method
from typing import Counter
from datetime import datetime
from threading import Lock
import re
from data.model import Case, Cases, User

# Bounded locks shared by repository instances. Hold them inside the worker so
# cancellation of an awaiting command cannot release an unfinished operation.
_warning_locks = tuple(Lock() for _ in range(64))

class UserService:
    def get_user(self, id: int) -> User:
        """Look up the User document of a user, whose ID is given by `id`.
        If the user doesn't have a User document in the database, first create that.

        Parameters
        ----------
        id : int
            The ID of the user we want to look up

        Returns
        -------
        User
            The User document we found from the database.
        """

        user = User.objects(_id=id).first()
        # first we ensure this user has a User document in the database before continuing
        if not user:
            User._get_collection().update_one(
                {"_id": id}, {"$setOnInsert": dict(User(_id=id).to_mongo())}, upsert=True)
            user = User.objects(_id=id).get()
        return user
    
    def leaderboard(self) -> list:
        return User.objects[0:130].only('_id', 'xp', 'level').order_by('-xp', '-_id').select_related()

    def leaderboard_rank(self, xp):
        users = User.objects().only('_id', 'xp')
        overall = users().count()
        rank = users(xp__gte=xp).count()
        return (rank, overall)
    
    def inc_points(self, _id: int, points: int) -> None:
        """Increments the warnpoints by `points` of a user whose ID is given by `_id`.
        If the user doesn't have a User document in the database, first create that.

        Parameters
        ----------
        _id : int
            The user's ID to whom we want to add/remove points
        points : int
            The amount of points to increment the field by, can be negative to remove points
        """

        # first we ensure this user has a User document in the database before continuing
        self.get_user(_id)
        if points < 0:
            self._deduct_points(_id, -points)
        else:
            User.objects(_id=_id).update_one(inc__warn_points=points)
        
    def inc_xp(self, id, xp):
        """Increments user xp.
        """

        self.get_user(id)
        User.objects(_id=id).update_one(inc__xp=xp)
        u = User.objects(_id=id).first()
        return (u.xp, u.level)

    def inc_level(self, id) -> None:
        """Increments user level.
        """

        self.get_user(id)
        User.objects(_id=id).update_one(inc__level=1)
    
    def get_cases(self, id: int) -> Cases:
        """Return the Document representing the cases of a user, whose ID is given by `id`
        If the user doesn't have a Cases document in the database, first create that.

        Parameters
        ----------
        id : int
            The user whose cases we want to look up.

        Returns
        -------
        Cases
            [description]
        """

        cases = Cases.objects(_id=id).first()
        # first we ensure this user has a Cases document in the database before continuing
        if cases is None:
            Cases._get_collection().update_one(
                {"_id": id}, {"$setOnInsert": {"cases": []}}, upsert=True)
            cases = Cases.objects(_id=id).get()
        return cases
    
    def add_case(self, _id: int, case: Case) -> None:
        """Cases holds all the cases for a particular user with id `_id` as an
        EmbeddedDocumentListField. This function appends a given case object to
        this list. If this user doesn't have any previous cases, we first add
        a new Cases document to the database.

        Parameters
        ----------
        _id : int
            ID of the user who we want to add the case to.
        case : Case
            The case we want to add to the user.
        """

        # ensure this user has a cases document before we try to append the new case
        self.get_cases(_id)
        Cases.objects(_id=_id).update_one(push__cases=case)

    def _deduct_points(self, member_id, points):
        """Atomic balance guard, including callers outside the member lock."""
        if points <= 0:
            raise ValueError("Points must be positive.")
        self.get_user(member_id)
        changed = User.objects(_id=member_id, warn_points__gte=points).update_one(
            inc__warn_points=-points)
        if not changed:
            raise ValueError("Can't deduct points because the balance would be negative.")

    def remove_points(self, member_id, points, case):
        with _warning_locks[member_id % len(_warning_locks)]:
            self._deduct_points(member_id, points)
            try:
                self.add_case(member_id, case)
            except Exception:
                # A write can succeed before the connection reports a failure.
                # Refund only when a subsequent read confirms it did not persist.
                if not Cases.objects(__raw__={"_id": member_id, "cases._id": case._id}).first():
                    self.inc_points(member_id, points)
                raise
            return case

    def lift_warn(self, member_id, case_id, reason, mod_id, mod_tag):
        """Serialize deductions; compensate confirmed persistence failures.

        The balance and history are separate documents: process death between
        writes (or an unavailable confirmation read) still needs reconciliation.
        This deliberately does not require replica-set transactions.
        """
        with _warning_locks[member_id % len(_warning_locks)]:
            cases = self.get_cases(member_id)
            case = cases.cases.filter(_id=case_id).first()
            if case is None:
                raise ValueError(f"No case with ID {case_id} for <@{member_id}>.")
            if case._type != "WARN":
                raise ValueError(f"Case with ID {case_id} is not a warn case.")
            if case.lifted:
                raise ValueError(f"Case with ID {case_id} already lifted.")
            points = int(case.punishment)
            self._deduct_points(member_id, points)
            case.lifted = True
            case.lifted_reason = reason
            case.lifted_by_tag = mod_tag
            case.lifted_by_id = mod_id
            case.lifted_date = datetime.now()
            try:
                changed = Cases.objects(__raw__={"_id": member_id, "cases._id": case._id}).update_one(
                    set__cases__S__lifted=True,
                    set__cases__S__lifted_reason=reason,
                    set__cases__S__lifted_by_tag=mod_tag,
                    set__cases__S__lifted_by_id=mod_id,
                    set__cases__S__lifted_date=case.lifted_date)
                if not changed:
                    raise RuntimeError("Warning disappeared during lift; retry after reviewing history.")
            except Exception:
                stored = self.get_cases(member_id).cases.filter(_id=case_id).first()
                if stored is None or not stored.lifted:
                    self.inc_points(member_id, points)
                raise
            return case

    def set_warn_kicked(self, _id: int) -> None:
        """Set the `was_warn_kicked` field in the User object of the user, whose ID is given by `_id`,
        to True. (this happens when a user reaches 400+ points for the first time and is kicked).
        If the user doesn't have a User document in the database, first create that.

        Parameters
        ----------
        _id : int
            The user's ID who we want to set `was_warn_kicked` for.
        """

        # first we ensure this user has a User document in the database before continuing
        self.get_user(_id)
        User.objects(_id=_id).update_one(set__was_warn_kicked=True)


    def _case_rows(self, member_id, predicate, sort, limit, offset=0):
        pipeline = [
            {"$match": {"_id": member_id}},
            {"$unwind": {"path": "$cases", "includeArrayIndex": "position"}},
            {"$match": predicate}, {"$sort": sort},
            {"$skip": offset}, {"$limit": limit},
            {"$project": {"_id": 0, "case": "$cases"}},
        ]
        return [Case._from_son(row["case"]) for row in
                Cases._get_collection().aggregate(pipeline)]

    def rundown(self, id: int) -> list:
        return self._case_rows(id, {"cases._type": {"$ne": "UNMUTE"}},
                               {"cases.date": -1, "position": -1}, 3)

    def warning_choices(self, member_id, prefix=""):
        # Case IDs are numeric; prefix filtering is explicitly string-based.
        predicate = {"cases._type": "WARN", "cases.lifted": {"$ne": True}}
        pipeline = [
            {"$match": {"_id": member_id}}, {"$unwind": "$cases"},
            {"$match": predicate},
            {"$addFields": {"case_id_text": {"$toString": "$cases._id"}}},
            {"$match": {"case_id_text": {"$regex": "^" + re.escape(prefix)}}},
            {"$sort": {"cases._id": -1}}, {"$limit": 25},
            {"$project": {"_id": 0, "case": "$cases"}},
        ]
        return [Case._from_son(row["case"]) for row in
                Cases._get_collection().aggregate(pipeline)]

    def case_count(self, member_id):
        rows = list(Cases._get_collection().aggregate([
            {"$match": {"_id": member_id}}, {"$unwind": "$cases"},
            {"$match": {"cases._type": {"$ne": "UNMUTE"}}},
            {"$count": "total"},
        ]))
        return rows[0]["total"] if rows else 0

    def case_page(self, member_id, page, per_page=10):
        if page < 1 or not 1 <= per_page <= 100:
            raise ValueError("Invalid case page.")
        return self._case_rows(member_id, {"cases._type": {"$ne": "UNMUTE"}},
                               {"position": -1}, per_page, (page - 1) * per_page)

    def retrieve_birthdays(self, date):
        return list(User.objects(birthday=date))
    
    def transfer_profile(self, oldmember, newmember):
        if oldmember == newmember:
            raise ValueError("Source and destination must be different users.")
        u = self.get_user(oldmember)
        u._id = newmember
        u.save()
        
        u2 = self.get_user(oldmember)
        u2.xp = 0
        u2.level = 0
        u2.save()
        
        cases = self.get_cases(oldmember)
        cases._id = newmember
        cases.save()
        
        cases2 = self.get_cases(oldmember)
        cases2.cases = []
        cases2.save()
        
        return u, len(cases.cases)
    
    def fetch_raids(self):
        values = {}
        values["Join spam"] = Cases.objects(cases__reason__contains="Join spam detected").count()
        values["Join spam over time"] = Cases.objects(cases__reason__contains="Join spam over time detected").count()
        values["Raid phrase"] = Cases.objects(cases__reason__contains="Raid phrase detected").count()
        values["Ping spam"] = Cases.objects(cases__reason__contains="Ping spam").count()
        values["Message spam"] = Cases.objects(cases__reason__contains="Message spam").count()
        
        return values

    def fetch_cases_by_mod(self, _id):
        rows = Cases._get_collection().aggregate([
            {"$match": {"cases.mod_id": int(_id)}}, {"$unwind": "$cases"},
            {"$match": {"cases.mod_id": int(_id)}},
            {"$group": {"_id": "$cases.reason", "count": {"$sum": 1}}},
        ])
        total = 0
        counts = Counter()
        for row in rows:
            total += row["count"]
            reason = ''.join(c for c in row["_id"].lower()
                             if c.isalnum() or c == " ").strip()
            if reason != "temporary mute expired":
                counts[reason] += row["count"]
        return {"total": total, "counts": sorted(counts.items(), key=lambda item: item[1], reverse=True)}

    def fetch_cases_by_keyword(self, keyword):
        # Keep Python's Unicode lower/substring behavior. Group projected strings
        # in Mongo rather than constructing entire Case/User histories in Python.
        rows = Cases._get_collection().aggregate([
            {"$match": {"cases.reason": {"$regex": re.escape(keyword), "$options": "i"}}},
            {"$unwind": "$cases"},
            {"$group": {"_id": {"reason": "$cases.reason", "mod": "$cases.mod_tag"},
                        "count": {"$sum": 1}}},
        ])
        total = 0
        counts = Counter()
        for row in rows:
            if keyword.lower() in row["_id"]["reason"].lower():
                total += row["count"]
                counts[row["_id"]["mod"]] += row["count"]
        return {"total": total, "counts": sorted(counts.items(), key=lambda item: item[1], reverse=True)}

    def set_sticky_roles(self, _id: int, roles) -> None:
        self.get_user(_id)
        User.objects(_id=_id).update_one(set__sticky_roles=roles)


_repository = UserService()


class AsyncUserService:
    """Bot-facing API; all persistence runs in the bounded database pool."""
    get_user = database_method(_repository.get_user)
    leaderboard = database_method(_repository.leaderboard)
    leaderboard_rank = database_method(_repository.leaderboard_rank)
    inc_points = database_method(_repository.inc_points)
    inc_xp = database_method(_repository.inc_xp)
    inc_level = database_method(_repository.inc_level)
    get_cases = database_method(_repository.get_cases)
    add_case = database_method(_repository.add_case)
    lift_warn = database_method(_repository.lift_warn)
    remove_points = database_method(_repository.remove_points)
    set_warn_kicked = database_method(_repository.set_warn_kicked)
    rundown = database_method(_repository.rundown)
    warning_choices = database_method(_repository.warning_choices)
    case_count = database_method(_repository.case_count)
    case_page = database_method(_repository.case_page)
    retrieve_birthdays = database_method(_repository.retrieve_birthdays)
    transfer_profile = database_method(_repository.transfer_profile)
    fetch_raids = database_method(_repository.fetch_raids)
    fetch_cases_by_mod = database_method(_repository.fetch_cases_by_mod)
    fetch_cases_by_keyword = database_method(_repository.fetch_cases_by_keyword)
    set_sticky_roles = database_method(_repository.set_sticky_roles)


user_service = AsyncUserService()
