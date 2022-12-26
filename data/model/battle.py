from typing import List
import mongoengine

class Battle(mongoengine.Document):
    _id = mongoengine.IntField(required=True)
    link = mongoengine.StringField()
    votes = mongoengine.ListField(default=[])
    seen_by = mongoengine.ListField(default=[])

    meta = {
        'db_alias': 'default',
        'collection': 'battle'
    }