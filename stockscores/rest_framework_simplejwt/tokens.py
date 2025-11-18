import secrets
from datetime import timedelta, datetime


def _make_token_value(user_id):
    """
    Encode the user id alongside a random suffix so we can recover the user
    later in the lightweight authentication stub.
    """

    return f"{user_id}:{secrets.token_urlsafe(32)}"


def parse_user_id(token_value):
    try:
        user_id, _ = token_value.split(":", 1)
        return int(user_id)
    except (ValueError, TypeError):
        return None


class _BaseToken:
    """
    Extremely small stand-in token object that mimics the real library enough
    for local testing. It simply produces opaque strings scoped to a user id.
    """

    lifetime = timedelta(hours=1)

    def __init__(self, user_id=None, token=None):
        self.created = datetime.utcnow()
        self.user_id = user_id
        self.token = token or _make_token_value(user_id)

    def __str__(self):
        return self.token

    def __repr__(self):
        return f"<{self.__class__.__name__} token={self.token!r}>"


class AccessToken(_BaseToken):
    lifetime = timedelta(hours=4)

    @classmethod
    def for_user(cls, user):
        return cls(user_id=getattr(user, "pk", None))


class RefreshToken(_BaseToken):
    lifetime = timedelta(days=7)

    def __init__(self, user_id=None, token=None, username=None):
        super().__init__(user_id=user_id, token=token)
        self.username = username
        self.access_token = AccessToken(user_id=user_id)

    @classmethod
    def for_user(cls, user):
        """
        Mirror the public API of the real library. The token contents are not
        signed JWTs—just opaque strings suitable for smoke tests.
        """

        return cls(
            user_id=getattr(user, "pk", None),
            username=getattr(user, "get_username", lambda: None)(),
        )
