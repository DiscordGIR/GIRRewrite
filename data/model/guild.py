import mongoengine
from .filterword import FilterWord
from .tag import Tag

class Guild(mongoengine.Document):
    _id                       = mongoengine.IntField(required=True)
    case_id                   = mongoengine.IntField(min_value=1, required=True)

    emoji_logging_webhook     = mongoengine.StringField()
    locked_channels           = mongoengine.ListField(default=[])
    filter_excluded_channels  = mongoengine.ListField(default=[])
    filter_excluded_guilds    = mongoengine.ListField(default=[349243932447604736])
    filter_words              = mongoengine.EmbeddedDocumentListField(FilterWord, default=[])
    raid_phrases              = mongoengine.EmbeddedDocumentListField(FilterWord, default=[])
    logging_excluded_channels = mongoengine.ListField(default=[])
    nsa_guild_id              = mongoengine.IntField()
    nsa_mapping               = mongoengine.DictField(default={})
    tags                      = mongoengine.EmbeddedDocumentListField(Tag, default=[])
    memes                     = mongoengine.EmbeddedDocumentListField(Tag, default=[])
    sabbath_mode              = mongoengine.BooleanField(default=False)
    ban_today_spam_accounts   = mongoengine.BooleanField(default=False)
    
    meta = {
        'db_alias': 'default',
        'collection': 'guilds'
    }

