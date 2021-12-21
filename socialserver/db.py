from pony import orm
import datetime
from socialserver.constants import BIO_MAX_LEN, COMMENT_MAX_LEN, DISPLAY_NAME_MAX_LEN, \
    REPORT_SUPPLEMENTARY_INFO_MAX_LEN, TAG_MAX_LEN, USERNAME_MAX_LEN, AccountAttributes
from socialserver.util.config import config
from socialserver.util.output import console


def _define_entities(db_object):
    class User(db_object.Entity):
        sessions = orm.Set("UserSession")
        display_name = orm.Required(str, max_len=DISPLAY_NAME_MAX_LEN)
        username = orm.Required(str, max_len=USERNAME_MAX_LEN, unique=True)
        password_hash = orm.Required(str)
        password_salt = orm.Required(str)
        creation_time = orm.Required(datetime.datetime)
        birthday = orm.Optional(datetime.date)
        # legacy accounts are the ones imported from socialserver 2.x during migration
        # this doesn't mean much now, but might become important in the future
        # so might as well have it.
        is_legacy_account = orm.Required(bool)
        # check out AccountAttributes enum in constants for more info
        account_attributes = orm.Required(orm.IntArray)
        bio = orm.Optional(str, max_len=BIO_MAX_LEN)
        totp_secret = orm.Optional(str, nullable=True)
        last_used_totp = orm.Optional(str, nullable=True)
        posts = orm.Set('Post', cascade_delete=True)
        comments = orm.Set('Comment', cascade_delete=True)
        post_likes = orm.Set('PostLike', cascade_delete=True)
        comment_likes = orm.Set('CommentLike', cascade_delete=True)
        followers = orm.Set("Follow", cascade_delete=True)
        following = orm.Set("Follow", cascade_delete=True)
        blocked_users = orm.Set("Block", cascade_delete=True)
        blocked_by = orm.Set("Block", cascade_delete=True)
        invite_codes = orm.Set("InviteCode", cascade_delete=True)
        profile_pic = orm.Optional("Image")
        header_pic = orm.Optional("Image")
        uploaded_images = orm.Set("Image", reverse="uploader")
        # deleting user should leave reports intact
        submitted_reports = orm.Set("PostReport", cascade_delete=False)
        associated_api_keys = orm.Set("ApiKey", cascade_delete=True)
        # whether the account is approved. this will be made true
        # automatically if admin approval requirement is off.
        account_approved = orm.Required(bool)

        @property
        def is_private(self):
            return AccountAttributes.PRIVATE.value in self.account_attributes

        @property
        def is_verified(self):
            return AccountAttributes.VERIFIED.value in self.account_attributes

        @property
        def is_admin(self):
            return AccountAttributes.ADMIN.value in self.account_attributes

        @property
        def is_moderator(self):
            return AccountAttributes.MODERATOR.value in self.account_attributes

        @property
        def has_config_permissions(self):
            return AccountAttributes.INSTANCE_ADMIN.value in self.account_attributes

        @property
        def has_profile_picture(self):
            return self.profile_pic is not None

        @property
        def has_header_picture(self):
            return self.header_pic is not None

    class UserSession(db_object.Entity):
        # data collection is for security purposes.
        # need to note that it's not used for advertising.
        # we hash the access token unsalted & hashed with sha256,
        # same as an API key.
        # check ApiKey for a quick explanation of why.
        access_token_hash = orm.Required(str)
        user = orm.Required('User')
        creation_ip = orm.Required(str)
        creation_time = orm.Required(datetime.datetime)
        last_access_time = orm.Required(datetime.datetime)
        user_agent = orm.Required(str)

    class Post(db_object.Entity):
        # whether the post is currently in the mod-queue
        under_moderation = orm.Required(bool)
        user = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        text = orm.Required(str)
        images = orm.Set('Image', reverse="associated_posts")
        comments = orm.Set('Comment', cascade_delete=True)
        likes = orm.Set('PostLike', cascade_delete=True)
        hashtags = orm.Set('Hashtag')
        reports = orm.Set('PostReport', cascade_delete=True)

    class PostReport(db_object.Entity):
        # we don't want to just delete these I don't think?
        # better to mark them inactive, until the post is deleted.
        # that way if it's moderated, an admin can still see the acted
        # on report. rather than expose deletion via the API, we should
        # just rely on database constraints to delete reports when the
        # post they are associated with has been removed.
        # IMPORTANT NOTE: could this result in users posting illegal things
        # and then deleting them soon after to prevent reports being seen by a
        # moderator? this needs investigating, but I can't think of a clean
        # solution right now.
        active = orm.Required(bool)
        # we want to ensure that the report has a user,
        # but we don't want to actually tie it to a user,
        # since if somebody reports illegal content, and then
        # deletes their account, we still want to know about
        # the report, so we can take action
        reporter = orm.Optional('User', reverse="submitted_reports")
        post = orm.Required('Post', reverse="reports")
        creation_time = orm.Required(datetime.datetime)
        # since we do one report per post, we want to be able to
        # report multiple infringements at once, hence the array.
        # NOTE: not sure if we do want this? Need to figure that one
        # out soon I guess.
        # check out the socialserver.constants.ReportReasons enum
        # for a list of these.
        report_reason = orm.Required(orm.IntArray)
        supplementary_info = orm.Optional(str, max_len=REPORT_SUPPLEMENTARY_INFO_MAX_LEN)

    class Image(db_object.Entity):
        uploader = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        # uuid used to retrieve the image from storage
        identifier = orm.Required(str)
        # upload_hash = orm.Required(str)
        associated_profile_pics = orm.Set('User', reverse='profile_pic')
        associated_header_pics = orm.Set('User', reverse='header_pic')
        associated_posts = orm.Set('Post', reverse='images')

        # SHA256 hash of the original file, for later adaption
        # original_hash = orm.Required(str)

        @property
        def is_orphan(self):
            return len(self.associated_posts) == 0 and len(self.associated_profile_pics) == 0 \
                   and len(self.associated_header_pics) == 0

    class Hashtag(db_object.Entity):
        creation_time = orm.Required(datetime.datetime)
        name = orm.Required(str, max_len=TAG_MAX_LEN, unique=True)
        posts = orm.Set('Post', reverse='hashtags')

    class PostLike(db_object.Entity):
        user = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        post = orm.Required('Post')

    class CommentLike(db_object.Entity):
        user = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        comment = orm.Required('Comment')

    class Follow(db_object.Entity):
        user = orm.Required('User', reverse='following')
        following = orm.Required('User', reverse='followers')
        creation_time = orm.Required(datetime.datetime)

    class Comment(db_object.Entity):
        user = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        text = orm.Required(str, max_len=COMMENT_MAX_LEN)
        post = orm.Required('Post')
        likes = orm.Set('CommentLike', cascade_delete=True)

    class Block(db_object.Entity):
        user = orm.Required('User', reverse='blocked_users')
        blocking = orm.Required('User', reverse='blocked_by')
        creation_time = orm.Required(datetime.datetime)

    class InviteCode(db_object.Entity):
        user = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        code = orm.Required(str)
        used = orm.Required(bool)

    class ApiKey(db_object.Entity):
        owner = orm.Required('User')
        creation_time = orm.Required(datetime.datetime)
        # we store this with sha256, not pbkdf2 or argon2,
        # since we want it to be super-fast, as each request
        # will have to verify it if it's in use.
        # no point salting it since it's high entropy already,
        # and practically impossible to build a lookup table for
        key_hash = orm.Required(str)
        permissions = orm.Required(orm.IntArray)  # constants.ApiKeyPermissions


"""
    create_memory_db
    
    Create a database object bound to an in-memory sqlite database.
    For testing, since data is purged upon app exit.
"""


def create_memory_db():
    console.log("Creating in memory database instance.")
    mem_db = orm.Database()
    _define_entities(mem_db)
    mem_db.bind('sqlite', ':memory:')
    mem_db.generate_mapping(create_tables=True)
    return mem_db


"""
    _bind_to_config_specified_db
    
    Binds to the database specified in the configuration file.
    Any connector logic should be put here.
"""


def _bind_to_config_specified_db(db_object):
    # TODO: improve database support. list of pony supported databases:
    # https://docs.ponyorm.org/database.html#binding-the-database-object-to-a-specific-database
    # I think only sqlite, postgres, and mariadb will be supported, since Cockroach is commercial,
    # and I don't want to touch Oracle Database with a 10 foot pole for fear of Larry Ellison showing
    # up in my room at midnight and demanding money
    if config.database.connector == 'sqlite':
        db_object.bind('sqlite', config.database.address, create_db=True)
    elif config.database.connector == 'postgres':
        # TODO: add postgres support back in
        # FIXME: this isn't even the right syntax for this I don't think. fix this soon.
        db_object.bind('postgres', config.database.address)
    else:
        raise ValueError("Invalid connector specified in config file.")
    db_object.generate_mapping(create_tables=True)


db = orm.Database()
_define_entities(db)
_bind_to_config_specified_db(db)
