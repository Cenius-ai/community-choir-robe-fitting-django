"""Helpers that map an account to its choir role."""

from .models import Profile


def get_role(user) -> str | None:
    """Return the profile role for an authenticated user, if any."""
    if not getattr(user, "is_authenticated", False):
        return None
    profile = getattr(user, "profile", None)
    if profile is not None:
        return profile.role
    # A superuser without a profile is treated as the director account.
    if user.is_superuser:
        return Profile.Role.DIRECTOR
    return None


def is_director(user) -> bool:
    return get_role(user) == Profile.Role.DIRECTOR


def home_url(user) -> str:
    """Where an account lands after signing in."""
    return "/dashboard/" if is_director(user) else "/me/"
