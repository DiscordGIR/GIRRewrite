import mongoengine
from data.model.case import Case

class Cases(mongoengine.Document):
    _id   = mongoengine.IntField(required=True)
    cases = mongoengine.EmbeddedDocumentListField(Case, default=[])
    meta = {
        'db_alias': 'default',
        'collection': 'cases'
    }