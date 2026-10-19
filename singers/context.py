"""Template context shared by every page: product chrome and role-aware nav."""

from django.urls import reverse

from .roles import get_role, is_director
from .models import Profile

PRODUCT_NAME = "Community Choir Robe Fitting"


def nav_context(request):
    user = getattr(request, "user", None)
    authenticated = bool(user is not None and user.is_authenticated)
    role = get_role(user) if authenticated else None

    nav_items = []
    if authenticated and role == Profile.Role.DIRECTOR:
        nav_items = [
            {"label": "Dashboard", "url": reverse("dashboard"), "match": "/dashboard/"},
            {"label": "Roster", "url": reverse("singer-list"), "match": "/singers/"},
            {"label": "Alterations", "url": reverse("alteration-list"), "match": "/alterations/"},
            {"label": "Robe sizes", "url": reverse("robe-list"), "match": "/robes/"},
            {"label": "Venues", "url": reverse("venue-list"), "match": "/venues/"},
        ]
    elif authenticated:
        nav_items = [{"label": "My robe", "url": reverse("my-robe"), "match": "/me/"}]

    path = request.path if hasattr(request, "path") else ""
    for item in nav_items:
        item["active"] = path.startswith(item["match"])

    return {
        "product_name": PRODUCT_NAME,
        "nav_items": nav_items,
        "signed_in": authenticated,
        "is_director": authenticated and is_director(user),
        "account_name": user.get_full_name() or user.get_username() if authenticated else "",
    }
