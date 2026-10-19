"""Views for the Community Choir Robe Fitting app (server-rendered)."""

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db.models import Count, Prefetch
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .decorators import director_required, login_required_page
from .forms import (
    AlterationCreateForm,
    AlterationUpdateForm,
    RobeSizeForm,
    SignInForm,
    SingerCreateForm,
    SingerUpdateForm,
    VenueForm,
)
from .models import Alteration, RobeSize, Singer, Venue
from .roles import home_url, is_director

ALTERATION_TABS = [
    ("all", "All"),
    ("queued", "Queued"),
    ("in_progress", "In progress"),
    ("done", "Done"),
]


def _safe_next(request, candidate):
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return None


def _render_not_found(request, back_url, back_label):
    return render(
        request,
        "404.html",
        {"back_url": back_url, "back_label": back_label},
        status=404,
    )


def _sizes_with_usage():
    return RobeSize.objects.annotate(in_use=Count("singers")).order_by("length_inches", "code")


# --------------------------------------------------------------------------
# Entry points and health
# --------------------------------------------------------------------------
def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect(home_url(request.user))


@require_GET
def health(request):
    return HttpResponse("ok", content_type="text/plain")


def forbidden_page(request, exception=None):
    return render(
        request,
        "403.html",
        {
            "reason": "Your account does not have access to that page.",
            "back_url": home_url(request.user) if request.user.is_authenticated else reverse("login"),
            "back_label": "Go back" if request.user.is_authenticated else "Sign in",
        },
        status=403,
    )


def not_found_page(request, exception=None):
    return render(
        request,
        "404.html",
        {"back_url": reverse("home"), "back_label": "Back to the start"},
        status=404,
    )


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect(home_url(request.user))

    next_url = _safe_next(request, request.POST.get("next") or request.GET.get("next"))
    form = SignInForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        auth_login(request, user)
        messages.success(request, f"Signed in as {user.get_username()}.")
        return redirect(next_url or home_url(user))

    return render(
        request,
        "registration/login.html",
        {
            "form": form,
            "next": next_url or "",
            "signed_out": request.GET.get("signed_out") == "1",
            "needs_sign_in": bool(next_url),
        },
    )


@require_POST
def sign_out(request):
    auth_logout(request)
    return redirect(f"{reverse('login')}?signed_out=1")


# --------------------------------------------------------------------------
# Director dashboard
# --------------------------------------------------------------------------
@director_required
@require_GET
def dashboard(request):
    singer_count = Singer.objects.count()
    unassigned_count = Singer.objects.filter(robe_size__isnull=True).count()
    open_statuses = [Alteration.Status.QUEUED, Alteration.Status.IN_PROGRESS]
    open_alterations = Alteration.objects.filter(status__in=open_statuses)
    venue_count = Venue.objects.count()

    attention = (
        open_alterations.select_related("singer", "singer__robe_size")
        .order_by("due_date", "requested_at")[:5]
    )
    awaiting_size = (
        Singer.objects.filter(robe_size__isnull=True).prefetch_related("alterations")[:5]
    )

    return render(
        request,
        "dashboard.html",
        {
            "singer_count": singer_count,
            "unassigned_count": unassigned_count,
            "open_alteration_count": open_alterations.count(),
            "queued_count": open_alterations.filter(status=Alteration.Status.QUEUED).count(),
            "venue_count": venue_count,
            "attention": attention,
            "awaiting_size": awaiting_size,
        },
    )


# --------------------------------------------------------------------------
# Singer roster
# --------------------------------------------------------------------------
@director_required
@require_http_methods(["GET", "POST"])
def singer_list(request):
    form = SingerCreateForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            singer = form.save()
            messages.success(
                request, f"{singer.full_name} added to the roster — no robe size assigned yet."
            )
            return redirect("singer-list")

    query = (request.GET.get("q") or "").strip()
    voice = request.GET.get("voice") or ""
    if voice not in Singer.VoicePart.values:
        voice = ""

    singers = Singer.objects.select_related("robe_size").prefetch_related(
        Prefetch("alterations", queryset=Alteration.objects.order_by("-requested_at", "-id"))
    )
    if query:
        singers = singers.filter(full_name__icontains=query)
    if voice:
        singers = singers.filter(voice_part=voice)
    singers = singers.order_by("-created_at", "-id")

    part_counts = {
        row["voice_part"]: row["total"]
        for row in Singer.objects.values("voice_part").annotate(total=Count("id"))
    }
    voice_filters = [
        {"value": value, "label": label, "count": part_counts.get(value, 0)}
        for value, label in Singer.VoicePart.choices
    ]

    return render(
        request,
        "singers/list.html",
        {
            "singers": singers,
            "form": form,
            "query": query,
            "voice": voice,
            "voice_filters": voice_filters,
            "total_singers": Singer.objects.count(),
            "filters_active": bool(query or voice),
        },
    )


@director_required
@require_http_methods(["GET", "POST"])
def singer_detail(request, singer_id):
    singer = Singer.objects.select_related("robe_size").filter(pk=singer_id).first()
    if singer is None:
        return _render_not_found(request, reverse("singer-list"), "Back to the roster")

    form = SingerUpdateForm(request.POST or None, instance=singer)
    if request.method == "POST" and form.is_valid():
        singer = form.save()
        note = (form.cleaned_data.get("alteration_note") or "").strip()
        if form.cleaned_data.get("needs_alteration"):
            already_open = (
                Alteration.objects.filter(singer=singer)
                .exclude(status=Alteration.Status.DONE)
                .exists()
            )
            if already_open:
                messages.info(
                    request,
                    "This singer already has an open alteration — update it in the queue.",
                )
            else:
                Alteration.objects.create(
                    singer=singer,
                    status=Alteration.Status.QUEUED,
                    seamstress_notes=note,
                    requested_at=timezone.localdate(),
                    created_by=request.user,
                )
                messages.success(request, "Alteration queued for the seamstress.")
        messages.success(request, f"Fitting saved for {singer.full_name}.")
        return redirect("singer-detail", singer_id=singer.id)

    alterations = singer.alterations.select_related("singer").order_by("-requested_at", "-id")
    return render(
        request,
        "singers/detail.html",
        {
            "singer": singer,
            "form": form,
            "alterations": alterations,
            "open_alteration": singer.open_alteration,
            "voice_parts": Singer.VoicePart.choices,
        },
    )


@director_required
@require_http_methods(["GET", "POST"])
def singer_delete(request, singer_id):
    singer = Singer.objects.select_related("robe_size").filter(pk=singer_id).first()
    if singer is None:
        return _render_not_found(request, reverse("singer-list"), "Back to the roster")

    if request.method == "POST" and request.POST.get("confirm") == "yes":
        name = singer.full_name
        singer.delete()
        messages.success(request, f"{name} removed from the roster.")
        return redirect("singer-list")

    return render(
        request,
        "singers/delete.html",
        {"singer": singer, "alteration_count": singer.alterations.count()},
    )


# --------------------------------------------------------------------------
# Robe size catalog
# --------------------------------------------------------------------------
@director_required
@require_http_methods(["GET", "POST"])
def robe_list(request):
    form = RobeSizeForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            size = form.save()
            messages.success(request, f"Robe size {size.code} added to the catalog.")
            return redirect("robe-list")

    return render(
        request,
        "robes/list.html",
        {
            "sizes": _sizes_with_usage(),
            "form": form,
            "edit_form": RobeSizeForm(),
            "edit_size_id": None,
            "form_errors_present": request.method == "POST" and form.errors,
        },
    )


@director_required
@require_POST
def robe_update(request, size_id):
    size = RobeSize.objects.filter(pk=size_id).first()
    if size is None:
        return _render_not_found(request, reverse("robe-list"), "Back to robe sizes")

    form = RobeSizeForm(request.POST, instance=size)
    if form.is_valid():
        form.save()
        messages.success(request, f"Robe size {size.code} updated.")
        return redirect("robe-list")

    return render(
        request,
        "robes/list.html",
        {
            "sizes": _sizes_with_usage(),
            "form": RobeSizeForm(),
            "edit_form": form,
            "edit_size_id": size.id,
            "form_errors_present": True,
        },
    )


@director_required
@require_http_methods(["GET", "POST"])
def robe_delete(request, size_id):
    size = RobeSize.objects.filter(pk=size_id).first()
    if size is None:
        return _render_not_found(request, reverse("robe-list"), "Back to robe sizes")

    in_use = size.singers.count()
    if in_use:
        messages.error(
            request,
            f"Robe size {size.code} is worn by {in_use} singer"
            f"{'s' if in_use != 1 else ''} — reassign them before deleting it.",
        )
        return redirect("robe-list")

    if request.method == "POST" and request.POST.get("confirm") == "yes":
        size.delete()
        messages.success(request, f"Robe size {size.code} removed from the catalog.")
        return redirect("robe-list")

    return render(request, "robes/delete.html", {"size": size, "in_use": in_use})


# --------------------------------------------------------------------------
# Alteration queue
# --------------------------------------------------------------------------
@director_required
@require_http_methods(["GET", "POST"])
def alteration_list(request):
    form = AlterationCreateForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.status = Alteration.Status.QUEUED
            ticket.requested_at = timezone.localdate()
            ticket.created_by = request.user
            ticket.save()
            messages.success(request, f"Ticket queued for {ticket.singer.full_name}.")
            return redirect("alteration-list")

    tab = request.GET.get("status") or "all"
    if tab not in dict(ALTERATION_TABS):
        tab = "all"

    base = Alteration.objects.select_related("singer", "singer__robe_size")
    counts = {"all": base.count()}
    for key in Alteration.Status.values:
        counts[key] = base.filter(status=key).count()

    tickets = base if tab == "all" else base.filter(status=tab)
    tickets = tickets.order_by("-requested_at", "-id")

    return render(
        request,
        "alterations/list.html",
        {
            "tickets": tickets,
            "form": form,
            "counts": counts,
            "tabs": [(key, label, counts.get(key, 0)) for key, label in ALTERATION_TABS],
            "active_tab": tab,
            "total_tickets": counts["all"],
        },
    )


@director_required
@require_http_methods(["GET", "POST"])
def alteration_detail(request, alteration_id):
    ticket = (
        Alteration.objects.select_related("singer", "singer__robe_size")
        .filter(pk=alteration_id)
        .first()
    )
    if ticket is None:
        return _render_not_found(request, reverse("alteration-list"), "Back to the queue")

    form = AlterationUpdateForm(request.POST if request.POST.get("action") == "save" else None,
                                instance=ticket)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "status":
            requested = request.POST.get("status", "")
            if requested not in Alteration.Status.values:
                messages.error(request, "That status is not part of the queue workflow.")
            elif not ticket.apply_status(requested):
                messages.info(
                    request,
                    f"Ticket is already {ticket.get_status_display()} — nothing to change.",
                )
            else:
                ticket.save(update_fields=["status", "completed_at"])
                messages.success(
                    request, f"Status set to {ticket.get_status_display()}."
                )
            return redirect("alteration-detail", alteration_id=ticket.id)

        if form.is_valid():
            form.save()
            messages.success(request, "Seamstress notes saved.")
            return redirect("alteration-detail", alteration_id=ticket.id)

    return render(
        request,
        "alterations/detail.html",
        {
            "ticket": ticket,
            "form": form,
            "statuses": Alteration.Status.choices,
        },
    )


@director_required
@require_http_methods(["GET", "POST"])
def alteration_delete(request, alteration_id):
    ticket = (
        Alteration.objects.select_related("singer").filter(pk=alteration_id).first()
    )
    if ticket is None:
        return _render_not_found(request, reverse("alteration-list"), "Back to the queue")

    if request.method == "POST" and request.POST.get("confirm") == "yes":
        singer_name = ticket.singer.full_name
        ticket.delete()
        messages.success(request, f"Alteration ticket for {singer_name} deleted.")
        return redirect("alteration-list")

    return render(request, "alterations/delete.html", {"ticket": ticket})


# --------------------------------------------------------------------------
# Venues and dress codes
# --------------------------------------------------------------------------
@director_required
@require_http_methods(["GET", "POST"])
def venue_list(request):
    form = VenueForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            venue = form.save()
            messages.success(request, f"{venue.name} added with its dress code.")
            return redirect("venue-list")

    return render(
        request,
        "venues/list.html",
        {"venues": Venue.objects.all(), "form": form},
    )


@director_required
@require_http_methods(["GET", "POST"])
def venue_detail(request, venue_id):
    venue = Venue.objects.filter(pk=venue_id).first()
    if venue is None:
        return _render_not_found(request, reverse("venue-list"), "Back to venues")

    form = VenueForm(request.POST or None, instance=venue)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Dress code for {venue.name} saved.")
        return redirect("venue-detail", venue_id=venue.id)

    return render(request, "venues/detail.html", {"venue": venue, "form": form})


@director_required
@require_http_methods(["GET", "POST"])
def venue_delete(request, venue_id):
    venue = Venue.objects.filter(pk=venue_id).first()
    if venue is None:
        return _render_not_found(request, reverse("venue-list"), "Back to venues")

    if request.method == "POST" and request.POST.get("confirm") == "yes":
        name = venue.name
        venue.delete()
        messages.success(request, f"{name} removed from the venue list.")
        return redirect("venue-list")

    return render(request, "venues/delete.html", {"venue": venue})


# --------------------------------------------------------------------------
# Singer self-service
# --------------------------------------------------------------------------
@login_required_page
@require_GET
def my_robe(request):
    if is_director(request.user):
        messages.info(request, "The director's own fittings live on the roster.")
        return redirect("dashboard")

    singer = getattr(request.user, "singer", None)
    current = None
    if singer is not None:
        current = singer.open_alteration or singer.latest_alteration

    return render(
        request,
        "me.html",
        {"singer": singer, "current_alteration": current},
    )
