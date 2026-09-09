import mongoengine
from datetime import datetime


class IdentityHistory(mongoengine.Document):
    _id = mongoengine.LongField(required=True, primary_key=True)
    usernames = mongoengine.ListField(mongoengine.StringField(), default=[])
    display_names = mongoengine.ListField(mongoengine.StringField(), default=[])
    avatar_hashes = mongoengine.ListField(mongoengine.StringField(), default=[])
    role_ids = mongoengine.ListField(mongoengine.LongField(), default=[])
    account_created = mongoengine.DateTimeField()
    last_joined = mongoengine.DateTimeField()
    first_seen = mongoengine.DateTimeField(default=datetime.utcnow)
    last_seen = mongoengine.DateTimeField(default=datetime.utcnow)
    status = mongoengine.StringField(default="member")
    observations = mongoengine.IntField(default=0)

    meta = {"db_alias": "default", "collection": "identity_history", "indexes": ["usernames", "display_names", "avatar_hashes", "last_seen"]}
