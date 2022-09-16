import mongoengine
from .filterword import FilterWord
from .tag import Tag

class Guild(mongoengine.Document):
    _id                       = mongoengine.IntField(required=True)
    case_id                   = mongoengine.IntField(min_value=1, required=True)
    reaction_role_mapping     = mongoengine.DictField(default={})
    role_administrator        = mongoengine.IntField()
    role_birthday             = mongoengine.IntField()
    role_dev                  = mongoengine.IntField()
    role_genius               = mongoengine.IntField()
    role_member               = mongoengine.IntField()
    role_memberone            = mongoengine.IntField()
    role_memberedition        = mongoengine.IntField()
    role_memberplus           = mongoengine.IntField()
    role_memberpro            = mongoengine.IntField()
    role_memberultra          = mongoengine.IntField()
    role_moderator            = mongoengine.IntField()
    role_mute                 = mongoengine.IntField()
    role_sub_mod              = mongoengine.IntField()
    role_sub_news             = mongoengine.IntField()
    
    channel_applenews         = mongoengine.IntField()
    channel_booster_emoji     = mongoengine.IntField()
    channel_botspam           = mongoengine.IntField()
    channel_common_issues     = mongoengine.IntField()
    channel_development       = mongoengine.IntField()
    channel_emoji_log         = mongoengine.IntField()
    channel_general           = mongoengine.IntField()
    channel_genius_bar        = mongoengine.IntField()
    channel_jailbreak         = mongoengine.IntField()
    channel_private           = mongoengine.IntField()
    channel_public            = mongoengine.IntField()
    channel_rules             = mongoengine.IntField()
    channel_reaction_roles    = mongoengine.IntField()
    channel_reports           = mongoengine.IntField()
    channel_subnews           = mongoengine.IntField()
    channel_music             = mongoengine.IntField()

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

