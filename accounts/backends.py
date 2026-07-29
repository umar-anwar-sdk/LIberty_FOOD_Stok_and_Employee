"""Authentication backends for the accounts application."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate the configured user model by email, case-insensitively.

    This deliberately delegates password and ``is_active`` checks to Django's
    standard backend methods.  It is therefore safe for all three roles.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email") or username
        if not email or password is None:
            return None

        user_model = get_user_model()
        try:
            user = user_model._default_manager.get(email__iexact=email.strip())
        except user_model.DoesNotExist:
            # Run the hasher once to avoid disclosing whether an account exists.
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
