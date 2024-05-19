import mongoengine

class FilterWord(mongoengine.EmbeddedDocument):
    notify               = mongoengine.BooleanField(required=True)
    silent_filter         = mongoengine.BooleanField(default=False)
    bypass               = mongoengine.IntField(required=True)
    word                 = mongoengine.StringField(required=True)
    false_positive       = mongoengine.BooleanField(default=False)
    piracy               = mongoengine.BooleanField(default=False)
