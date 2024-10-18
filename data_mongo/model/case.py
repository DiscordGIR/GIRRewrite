import mongoengine
import datetime

class Case(mongoengine.EmbeddedDocument):
    _id               = mongoengine.IntField(required=True)
    _type             = mongoengine.StringField(required=True)
    date              = mongoengine.DateTimeField(default=datetime.datetime.now, required=True)
    until             = mongoengine.DateTimeField(default=None)
    mod_id            = mongoengine.IntField(required=True)
    mod_tag           = mongoengine.StringField(required=True)
    reason            = mongoengine.StringField(required=True)
    punishment        = mongoengine.StringField()
    lifted            = mongoengine.BooleanField(default=False)
    lifted_by_tag     = mongoengine.StringField()
    lifted_by_id      = mongoengine.IntField()
    lifted_reason     = mongoengine.StringField()
    lifted_date       = mongoengine.DateField()