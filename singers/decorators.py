"""Server-side role gates. Every director route is decorated."""

from functools import wraps

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .roles import home_url, is_director


def redirect_to_login(request):
    target = reverse("login")
    nxt = request.get_full_path()
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = f"{target}?next={nxt}"
    return redirect(target)


def login_required_page(view):
    """Require a signed-in account, sending visitors to the sign-in card."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request)
        return view(request, *args, **kwargs)

    return wrapper


def director_required(view):
    """Director-only pages; singers get a styled 403 that links back."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request)
        if not is_director(request.user):
            return render(
                request,
                "403.html",
                {
                    "reason": "The roster, alterations and venues are managed by the choir director.",
                    "back_url": home_url(request.user),
                    "back_label": "Go to my robe",
                },
                status=403,
            )
        return view(request, *args, **kwargs)

    return wrapper
