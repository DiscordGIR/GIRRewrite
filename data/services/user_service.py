from typing import Counter
from data.model import Case, Cases, User
from data.model.user import BirthdayView, XpView
from beanie.odm.operators.update.array import Push
from beanie.odm.operators.update.general import Set, Inc

class UserService:
    async def get_user(self, _id: int) -> User:
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
        user = await User.find_one(User.id == _id)
        if user is None:
            user = User(id=_id)
            await user.save()

        return user
    
    async def leaderboard(self) -> list:
        return await User.find().sort(-User.xp).limit(130).project(XpView).to_list()

    async def leaderboard_rank(self, xp):
        rank = await User.find(User.xp >= xp).count()
        total = await User.find().count()
        return (rank, total)
    
    async def inc_points(self, _id: int, points: int) -> None:
        """Increments the warnpoints by `points` of a user whose ID is given by `_id`.
        If the user doesn't have a User document in the database, first create that.

        Parameters
        ----------
        _id : int
            The user's ID to whom we want to add/remove points
        points : int
            The amount of points to increment the field by, can be negative to remove points
        """

        await self.get_user(_id)
        await User.find_one(User.id == _id).update(Inc({User.warn_points: points}))

    async def inc_xp(self, id, xp):
        """Increments user xp.
        """

        await self.get_user(id)
        await User.find_one(User.id == id).update(Inc({User.xp: xp}))
        u = await User.find_one(User.id == id).project(XpView)
        return (u.xp, u.level)

    async def inc_level(self, id) -> None:
        """Increments user level.
        """

        await self.get_user(id)
        await User.find_one(User.id == id).update(Inc({User.level: 1}))
    
    async def get_cases(self, id: int) -> Cases:
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

        cases = await Cases.find_one(Cases.id == id)
        if cases is None:
            cases = Cases(id=id)
            await cases.save()
        
        return cases
    
    async def add_case(self, _id: int, case: Case) -> None:
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
        await self.get_cases(_id)
        await Cases.find_one(Cases.id == _id).update(Push({Cases.cases: case}))

    async def set_warn_kicked(self, _id: int) -> None:
        """Set the `was_warn_kicked` field in the User object of the user, whose ID is given by `_id`,
        to True. (this happens when a user reaches 400+ points for the first time and is kicked).
        If the user doesn't have a User document in the database, first create that.

        Parameters
        ----------
        _id : int
            The user's ID who we want to set `was_warn_kicked` for.
        """

        # first we ensure this user has a User document in the database before continuing
        await self.get_user(_id)
        await User.find_one(User.id == _id).update(Set({User.was_warn_kicked: True}))


    async def rundown(self, id: int) -> list:
        """Return the 3 most recent cases of a user, whose ID is given by `id`
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

        cases = await self.get_cases(id)
        # first we ensure this user has a Cases document in the database before continuing
        if cases is None:
            cases = Cases(id=id)
            await cases.save()
            return []

        cases = cases.cases
        cases = filter(lambda x: x.type != "UNMUTE", cases)
        cases = sorted(cases, key=lambda i: i.date)
        cases.reverse()
        return cases[0:3]

    async def retrieve_birthdays(self, date):
        return await User.find(User.birthday == date).project(BirthdayView).to_list()
    
    async def transfer_profile(self, oldmember, newmember):
        u = await self.get_user(oldmember)
        u.id = newmember
        await u.save()
        
        u2 = await self.get_user(oldmember)
        u2.xp = 0
        u2.level = 0
        await u2.save()
        
        cases = await self.get_cases(oldmember)
        cases.id = newmember
        await cases.save()
        
        cases2 = await self.get_cases(oldmember)
        cases2.cases = []
        await cases2.save()
        
        return u, len(cases.cases)
    
    async def fetch_raids(self):
        values = {}

        values["Join spam"] = await Cases.find({ "cases": {"$elemMatch": { "reason": "Join spam detected" } } }).count()
        values["Join spam over time"] = await Cases.find({ "cases": {"$elemMatch": { "reason": "Join spam over time detected" } } }).count()
        values["Raid phrase"] = await Cases.find({ "cases": {"$elemMatch": { "reason": "Raid phrase detected" } } }).count()
        values["Ping spam"] = await Cases.find({ "cases": {"$elemMatch": { "reason": "Ping spam" } } }).count()
        values["Message spam"] = await Cases.find({ "cases": {"$elemMatch": { "reason": "Message spam" } } }).count()

        return values

    async def fetch_cases_by_mod(self, _id):
        values = {}
        # cases = Cases.objects(cases__mod_id=str(_id))
        cases = await Cases.find({ "cases": {"$elemMatch": { "mod_id": _id } } }).to_list()
        values["total"] = 0
        final_cases = []
        for target in cases:
            for case in target.cases:
                if str(case.mod_id) == str(_id):
                    final_cases.append(case)
                    values["total"] += 1

        def get_case_reason(reason):
            string = reason.lower()
            return ''.join(e for e in string if e.isalnum() or e == " ").strip()

        case_reasons = [get_case_reason(case.reason) for case in final_cases if get_case_reason(case.reason) != "temporary mute expired"]
        values["counts"] = sorted(Counter(case_reasons).items(), key=lambda item: item[1])
        values["counts"].reverse()
        return values

    async def fetch_cases_by_keyword(self, keyword):
        values = {}
        cases = await Cases.find({ "cases.reason": { "$regex": keyword }}).to_list()
        values["total"] = 0
        final_cases = []

        for target in cases:
            for case in target.cases:
                if keyword.lower() in case.reason:
                    values["total"] += 1
                    final_cases.append(case)

        case_mods = [case.mod_tag for case in final_cases]
        values["counts"] = sorted(Counter(case_mods).items(), key=lambda item: item[1])
        values["counts"].reverse()
        return values

    async def set_sticky_roles(self, _id: int, roles) -> None:
        await self.get_user(_id)
        await User.find_one(User.id == _id).update(Set({User.sticky_roles: roles}))

user_service = UserService()