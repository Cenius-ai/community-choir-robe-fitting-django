"""Authentication backend that accepts either a username or an email."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameOrEmailBackend(ModelBackend):
    """Sign in with ``cenius`` or ``cenius@cenius.ai`` — both resolve to one account."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or password is None:
            return None

        identifier = username.strip()
        lookup = Q(username__iexact=identifier) | Q(email__iexact=identifier)
        try:
            user = UserModel.objects.filter(lookup).order_by("id").first()
        except (ValueError, TypeError):
            return None
        if user is None:
            # Spend roughly the same time as a real password check so the
            # response does not reveal whether the account exists.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
