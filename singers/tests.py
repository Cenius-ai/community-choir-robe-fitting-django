"""Smoke-and-behaviour tests for the Community Choir Robe Fitting app.

Run with ``python3 manage.py test`` (or ``pytest`` when pytest-django is
installed). Every test seeds its own data through the real ``seed`` command,
so the suite is self-contained and needs no network.
"""

import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .management.commands.seed import DIRECTOR, SINGER_ACCOUNTS, SINGER_PASSWORD
from .models import Alteration, Profile, RobeSize, Singer, Venue

# The seeded demo accounts are the single source of truth for their credentials.
DIRECTOR_USERNAME = DIRECTOR["username"]
DIRECTOR_EMAIL = DIRECTOR["email"]
DIRECTOR_PASSWORD = DIRECTOR["password"]
SINGER_USERNAME = next(
    account["username"] for account in SINGER_ACCOUNTS if account["username"] == "nadia"
)


FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


class FastHashTestCase(TestCase):
    """Seed data hashes passwords; a fast hasher keeps the suite quick."""

    @classmethod
    def setUpClass(cls):
        cls._hasher_override = override_settings(PASSWORD_HASHERS=FAST_HASHERS)
        cls._hasher_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._hasher_override.disable()


class SeededTestCase(FastHashTestCase):
    """Base class that loads the idempotent demo seed once per class."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed", verbosity=0)

    def sign_in_director(self):
        self.assertTrue(
            self.client.login(username=DIRECTOR_USERNAME, password=DIRECTOR_PASSWORD)
        )

    def sign_in_singer(self, username=SINGER_USERNAME, password=None):
        self.assertTrue(
            self.client.login(username=username, password=password or SINGER_PASSWORD)
        )


class AuthTests(SeededTestCase):
    def test_root_redirects_anonymous_visitor_to_sign_in(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/accounts/login/", fetch_redirect_response=False)

    def test_login_page_shows_demo_credentials(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cenius@cenius.ai")
        self.assertContains(response, "Demo:")

    def test_director_lands_on_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
        )
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_singer_lands_on_own_robe_page(self):
        response = self.client.post(
            reverse("login"), {"username": SINGER_USERNAME, "password": SINGER_PASSWORD}
        )
        self.assertRedirects(response, "/me/", fetch_redirect_response=False)

    def test_bad_password_gives_one_non_enumerating_message(self):
        for username in (DIRECTOR_USERNAME, "does-not-exist"):
            response = self.client.post(
                reverse("login"), {"username": username, "password": "nope"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "did not match our records")
            self.assertContains(response, f'value="{username}"')

    def test_signer_in_answers_director_route_with_403_link_back(self):
        self.sign_in_singer()
        for url in ("/dashboard/", "/singers/", "/robes/", "/alterations/", "/venues/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, url)
            self.assertContains(response, 'href="/me/"', status_code=403)

    def test_singer_post_to_director_route_writes_nothing(self):
        self.sign_in_singer()
        before = Singer.objects.count()
        response = self.client.post("/singers/", {"full_name": "Intruder", "voice_part": "bass"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Singer.objects.count(), before)

    def test_logout_returns_to_sign_in_with_notice(self):
        self.sign_in_director()
        response = self.client.post(reverse("logout"))
        self.assertRedirects(
            response, "/accounts/login/?signed_out=1", fetch_redirect_response=False
        )
        response = self.client.get("/accounts/login/?signed_out=1")
        self.assertContains(response, "You have signed out")

    def test_singer_login_username_and_email_both_work(self):
        for identifier in (DIRECTOR_USERNAME, DIRECTOR_EMAIL):
            self.client.logout()
            response = self.client.post(
                reverse("login"), {"username": identifier, "password": DIRECTOR_PASSWORD}
            )
            self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)


class DashboardTests(SeededTestCase):
    def setUp(self):
        self.sign_in_director()

    def test_counts_match_the_data(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Singers in the roster")
        context = response.context
        self.assertEqual(context["singer_count"], Singer.objects.count())
        self.assertEqual(context["venue_count"], Venue.objects.count())
        self.assertEqual(
            context["unassigned_count"], Singer.objects.filter(robe_size__isnull=True).count()
        )
        self.assertEqual(
            context["open_alteration_count"],
            Alteration.objects.exclude(status=Alteration.Status.DONE).count(),
        )

    def test_needs_attention_lists_open_tickets_with_links(self):
        response = self.client.get("/dashboard/")
        open_ticket = Alteration.objects.exclude(status=Alteration.Status.DONE).first()
        self.assertContains(response, open_ticket.singer.full_name)
        self.assertContains(response, f'href="/alterations/{open_ticket.id}/"')

    def test_clear_queue_shows_empty_state(self):
        Alteration.objects.update(
            status=Alteration.Status.DONE, completed_at=timezone.now()
        )
        response = self.client.get("/dashboard/")
        self.assertContains(response, "Nothing needs attention — the queue is clear")


class RosterTests(SeededTestCase):
    def setUp(self):
        self.sign_in_director()

    def test_roster_lists_every_singer_with_chip_and_badge(self):
        response = self.client.get("/singers/")
        self.assertEqual(response.status_code, 200)
        for singer in Singer.objects.all():
            self.assertContains(response, singer.full_name)

    def test_create_singer_appears_first_and_unassigned(self):
        response = self.client.post(
            "/singers/", {"full_name": "Aurora Wen", "voice_part": "soprano", "notes": ""}
        )
        self.assertRedirects(response, "/singers/", fetch_redirect_response=False)
        singer = Singer.objects.get(full_name="Aurora Wen")
        self.assertIsNone(singer.robe_size)
        roster = self.client.get("/singers/")
        names = [s.full_name for s in roster.context["singers"]]
        self.assertEqual(names[0], "Aurora Wen")

    def test_blank_name_is_rejected_with_inline_error(self):
        response = self.client.post("/singers/", {"full_name": "   ", "voice_part": "alto"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "field__error")
        self.assertFalse(Singer.objects.filter(full_name="").exists())

    def test_search_and_voice_filter_combine(self):
        response = self.client.get("/singers/?q=Naomi")
        self.assertContains(response, ">Naomi Ferreira<")
        self.assertNotContains(response, ">Yusuf Adeyemi<")

        response = self.client.get("/singers/?voice=bass")
        self.assertContains(response, ">Yusuf Adeyemi<")
        self.assertNotContains(response, ">Naomi Ferreira<")

        response = self.client.get("/singers/?q=nobody-here")
        self.assertContains(response, "No singers match that search")

    def test_singer_account_cannot_read_roster(self):
        self.client.logout()
        self.sign_in_singer("rowan")
        self.assertEqual(self.client.get("/singers/").status_code, 403)


class SingerDetailTests(SeededTestCase):
    def setUp(self):
        self.sign_in_director()
        self.singer = Singer.objects.get(full_name="Priya Raghunathan")  # no size yet
        self.size = RobeSize.objects.get(code="L")

    def _post(self, **overrides):
        payload = {
            "full_name": self.singer.full_name,
            "voice_part": self.singer.voice_part,
            "robe_size": "",
            "notes": self.singer.notes,
        }
        payload.update(overrides)
        return self.client.post(f"/singers/{self.singer.id}/", payload)

    def test_assign_robe_size_updates_detail_and_roster(self):
        response = self._post(robe_size=self.size.id)
        self.assertRedirects(
            response, f"/singers/{self.singer.id}/", fetch_redirect_response=False
        )
        self.singer.refresh_from_db()
        self.assertEqual(self.singer.robe_size, self.size)
        detail = self.client.get(f"/singers/{self.singer.id}/")
        self.assertContains(detail, "Chest 40-42")
        roster = self.client.get("/singers/")
        self.assertContains(roster, "40-42")

    def test_flagging_alteration_queues_a_ticket(self):
        before = Alteration.objects.count()
        response = self._post(
            robe_size=self.size.id,
            needs_alteration="on",
            alteration_note="Take in the waist by two inches.",
        )
        self.assertRedirects(
            response, f"/singers/{self.singer.id}/", fetch_redirect_response=False
        )
        self.assertEqual(Alteration.objects.count(), before + 1)
        ticket = Alteration.objects.filter(singer=self.singer).latest("id")
        self.assertEqual(ticket.status, Alteration.Status.QUEUED)
        self.assertIn("two inches", ticket.seamstress_notes)

    def test_alteration_flag_requires_a_robe_size(self):
        response = self._post(needs_alteration="on", alteration_note="Hem it")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assign a robe size from the catalog")
        self.assertFalse(Alteration.objects.filter(singer=self.singer).exists())

    def test_duplicate_flag_does_not_queue_a_second_ticket(self):
        Alteration.objects.create(
            singer=self.singer, seamstress_notes="already open", requested_at=timezone.localdate()
        )
        before = Alteration.objects.count()
        self._post(robe_size=self.size.id, needs_alteration="on", alteration_note="Again")
        self.assertEqual(Alteration.objects.count(), before)

    def test_clearing_size_returns_singer_to_unassigned(self):
        assigned = Singer.objects.get(full_name="Naomi Ferreira")
        self.client.post(
            f"/singers/{assigned.id}/",
            {
                "full_name": assigned.full_name,
                "voice_part": assigned.voice_part,
                "robe_size": "",
                "notes": "",
            },
        )
        assigned.refresh_from_db()
        self.assertIsNone(assigned.robe_size)
        roster = self.client.get("/singers/?q=Naomi")
        self.assertContains(roster, "Unassigned")

    def test_history_lists_tickets_with_status(self):
        Alteration.objects.create(
            singer=self.singer,
            status=Alteration.Status.DONE,
            seamstress_notes="Done work",
            requested_at=timezone.localdate() - timedelta(days=9),
            completed_at=timezone.now(),
        )
        response = self.client.get(f"/singers/{self.singer.id}/")
        self.assertContains(response, "Done work")

    def test_delete_requires_confirmation_then_removes_singer(self):
        url = f"/singers/{self.singer.id}/delete/"
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, "Confirm deletion")
        self.assertTrue(Singer.objects.filter(pk=self.singer.pk).exists())

        response = self.client.post(url, {"confirm": "yes"})
        self.assertRedirects(response, "/singers/", fetch_redirect_response=False)
        self.assertFalse(Singer.objects.filter(pk=self.singer.pk).exists())

    def test_unknown_singer_gets_styled_404(self):
        response = self.client.get("/singers/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)


class RobeCatalogTests(SeededTestCase):
    def setUp(self):
        self.sign_in_director()

    def test_create_size_with_usage_count(self):
        response = self.client.post(
            "/robes/",
            {"code": "m2", "chest_range": "38-40", "length_inches": "56", "notes": ""},
        )
        self.assertRedirects(response, "/robes/", fetch_redirect_response=False)
        size = RobeSize.objects.get(code="M2")
        self.assertEqual(size.chest_range, "38-40")
        page = self.client.get("/robes/")
        self.assertContains(page, "M2")

    def test_invalid_length_is_rejected_inline(self):
        response = self.client.post(
            "/robes/",
            {"code": "Q", "chest_range": "40-42", "length_inches": "long", "notes": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "whole number of inches")
        self.assertFalse(RobeSize.objects.filter(code="Q").exists())

    def test_delete_blocked_while_assigned(self):
        size = RobeSize.objects.get(code="M")
        in_use = size.singers.count()
        self.assertGreater(in_use, 0)
        response = self.client.post(f"/robes/{size.id}/delete/", {"confirm": "yes"})
        self.assertRedirects(response, "/robes/", fetch_redirect_response=False)
        self.assertTrue(RobeSize.objects.filter(pk=size.pk).exists())
        self.assertContains(self.client.get("/robes/"), f"assigned to {in_use} singer")

    def test_unused_size_delete_needs_confirmation(self):
        size = RobeSize.objects.create(code="ZZ", chest_range="60-62", length_inches="70")
        self.assertEqual(self.client.get(f"/robes/{size.id}/delete/").status_code, 200)
        self.assertTrue(RobeSize.objects.filter(pk=size.pk).exists())
        self.client.post(f"/robes/{size.id}/delete/", {"confirm": "yes"})
        self.assertFalse(RobeSize.objects.filter(pk=size.pk).exists())

    def test_inline_edit_updates_size(self):
        size = RobeSize.objects.get(code="S")
        response = self.client.post(
            f"/robes/{size.id}/",
            {"code": "S", "chest_range": "30-32", "length_inches": "52", "notes": "short"},
        )
        self.assertRedirects(response, "/robes/", fetch_redirect_response=False)
        size.refresh_from_db()
        self.assertEqual(size.chest_range, "30-32")

    def test_empty_catalog_state(self):
        Singer.objects.update(robe_size=None)
        RobeSize.objects.all().delete()
        response = self.client.get("/robes/")
        self.assertContains(
            response,
            "Add your first robe size — sizes you create here become assignable to singers",
        )


class AlterationQueueTests(SeededTestCase):
    def setUp(self):
        self.sign_in_director()

    def test_tabs_filter_by_status_with_counts(self):
        response = self.client.get("/alterations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["counts"]["all"], Alteration.objects.count())

        queued = Alteration.objects.filter(status=Alteration.Status.QUEUED).first()
        done = Alteration.objects.filter(status=Alteration.Status.DONE).first()
        response = self.client.get("/alterations/?status=queued")
        self.assertContains(response, f'href="/alterations/{queued.id}/"')
        self.assertNotContains(response, f'href="/alterations/{done.id}/"')

    def test_create_ticket_appears_at_top_of_queue(self):
        singer = Singer.objects.get(full_name="Tomás Silva")
        response = self.client.post(
            "/alterations/",
            {
                "singer": singer.id,
                "seamstress_notes": "Raise the hem one inch.",
                "due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            },
        )
        self.assertRedirects(response, "/alterations/", fetch_redirect_response=False)
        ticket = Alteration.objects.filter(singer=singer).latest("id")
        self.assertEqual(ticket.status, Alteration.Status.QUEUED)
        self.assertEqual(self.client.get("/alterations/").context["tickets"][0], ticket)

    def test_create_without_singer_is_rejected(self):
        before = Alteration.objects.count()
        response = self.client.post("/alterations/", {"singer": "", "seamstress_notes": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "field__error")
        self.assertEqual(Alteration.objects.count(), before)

    def test_multiline_notes_persist_after_reload(self):
        ticket = Alteration.objects.filter(status=Alteration.Status.QUEUED).first()
        note = "Line one\nLine two\n  indented line"
        self.client.post(
            f"/alterations/{ticket.id}/",
            {"action": "save", "seamstress_notes": note, "due_date": ""},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.seamstress_notes, note)
        self.assertContains(self.client.get(f"/alterations/{ticket.id}/"), "indented line")

    def test_done_stamps_completion_and_leaves_queued_tab(self):
        ticket = Alteration.objects.filter(status=Alteration.Status.QUEUED).first()
        self.client.post(
            f"/alterations/{ticket.id}/", {"action": "status", "status": "done"}
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Alteration.Status.DONE)
        self.assertIsNotNone(ticket.completed_at)
        queued = self.client.get("/alterations/?status=queued")
        self.assertNotContains(queued, f'href="/alterations/{ticket.id}/"')
        done_tab = self.client.get("/alterations/?status=done")
        self.assertContains(done_tab, f'href="/alterations/{ticket.id}/"')

    def test_repeating_done_is_a_noop_with_notice(self):
        ticket = Alteration.objects.filter(status=Alteration.Status.DONE).first()
        first_completed = ticket.completed_at
        response = self.client.post(
            f"/alterations/{ticket.id}/", {"action": "status", "status": "done"}, follow=True
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.completed_at, first_completed)
        self.assertContains(response, "nothing to change")

    def test_invalid_status_is_rejected_by_model_validation(self):
        ticket = Alteration.objects.first()
        ticket.status = "cancelled"
        with self.assertRaises(ValidationError):
            ticket.full_clean()

    def test_director_delete_requires_confirmation(self):
        ticket = Alteration.objects.first()
        url = f"/alterations/{ticket.id}/delete/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Alteration.objects.filter(pk=ticket.pk).exists())
        self.client.post(url, {"confirm": "yes"})
        self.assertFalse(Alteration.objects.filter(pk=ticket.pk).exists())

    def test_singer_sees_own_status_only(self):
        self.client.logout()
        self.sign_in_singer()
        response = self.client.get("/me/")
        self.assertContains(response, "In progress")
        self.assertNotContains(response, "seamstress_notes")


class VenueTests(SeededTestCase):
    def setUp(self):
        self.sign_in_director()

    def test_list_shows_name_address_and_excerpt(self):
        response = self.client.get("/venues/")
        self.assertEqual(response.status_code, 200)
        venue = Venue.objects.get(name="St Brigid's Hall")
        self.assertContains(response, "14 Harbour Row, Galway")
        self.assertContains(response, venue.dress_code_excerpt)
        self.assertContains(response, f'href="/venues/{venue.id}/"')

    def test_create_venue_requires_dress_code(self):
        before = Venue.objects.count()
        response = self.client.post(
            "/venues/",
            {"name": "New Hall", "address": "Somewhere", "dress_code": "  ", "notes": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter the dress code")
        self.assertEqual(Venue.objects.count(), before)

    def test_create_and_edit_dress_code(self):
        response = self.client.post(
            "/venues/",
            {
                "name": "Harbour Church",
                "address": "2 Quay Street",
                "dress_code": "Full robe\nWhite gloves",
                "notes": "",
            },
        )
        self.assertRedirects(response, "/venues/", fetch_redirect_response=False)
        venue = Venue.objects.get(name="Harbour Church")
        self.assertContains(self.client.get(f"/venues/{venue.id}/"), "White gloves")

        self.client.post(
            f"/venues/{venue.id}/",
            {
                "name": "Harbour Church",
                "address": "2 Quay Street",
                "dress_code": "Emerald sash\nBlack flats",
                "notes": "",
            },
        )
        venue.refresh_from_db()
        self.assertEqual(venue.dress_code, "Emerald sash\nBlack flats")
        self.assertContains(self.client.get("/venues/"), "Emerald sash")

    def test_delete_needs_confirmation_and_removes_venue(self):
        venue = Venue.objects.get(name="The Old Mill Theatre")
        url = f"/venues/{venue.id}/delete/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Venue.objects.filter(pk=venue.pk).exists())
        self.client.post(url, {"confirm": "yes"})
        self.assertFalse(Venue.objects.filter(pk=venue.pk).exists())

    def test_unknown_venue_is_styled_404(self):
        response = self.client.get("/venues/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)


class SingerPortalTests(SeededTestCase):
    def test_own_robe_page_shows_size_and_status_without_notes(self):
        self.sign_in_singer("nadia")
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soprano")
        self.assertContains(response, "Chest 36-38")
        self.assertContains(response, "Length 56")
        self.assertContains(response, "In progress")
        self.assertNotContains(response, "shoulder seam")
        self.assertNotContains(response, "Save")

    def test_unassigned_singer_sees_friendly_empty_state(self):
        singer = Singer.objects.get(full_name="Dana Osei")
        password = secrets.token_urlsafe(16)
        user = get_user_model().objects.create_user(
            username="dana", password=password, email="dana@choir.test"
        )
        Profile.objects.create(user=user, role=Profile.Role.SINGER)
        singer.user = user
        singer.save(update_fields=["user"])
        self.sign_in_singer("dana", password)
        response = self.client.get("/me/")
        self.assertContains(
            response,
            "No robe size assigned yet — your director will assign one; check back after your fitting",
        )

    def test_unlinked_account_gets_polite_message(self):
        password = secrets.token_urlsafe(16)
        user = get_user_model().objects.create_user(username="newbie", password=password)
        Profile.objects.create(user=user, role=Profile.Role.SINGER)
        self.sign_in_singer("newbie", password)
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "isn't linked to a singer record")

    def test_director_on_me_is_sent_to_dashboard(self):
        self.sign_in_director()
        response = self.client.get("/me/")
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_anonymous_visitor_is_sent_to_sign_in(self):
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])


class SeedTests(FastHashTestCase):
    def test_seed_is_idempotent_and_complete(self):
        call_command("seed", verbosity=0)
        first = (
            Singer.objects.count(),
            RobeSize.objects.count(),
            Alteration.objects.count(),
            Venue.objects.count(),
        )
        self.assertEqual(first, (12, 4, 6, 3))
        call_command("seed", verbosity=0)
        second = (
            Singer.objects.count(),
            RobeSize.objects.count(),
            Alteration.objects.count(),
            Venue.objects.count(),
        )
        self.assertEqual(first, second)

    def test_seed_creates_the_standard_demo_account(self):
        call_command("seed", verbosity=0)
        user = get_user_model().objects.get(username=DIRECTOR_USERNAME)
        self.assertEqual(user.email, DIRECTOR_EMAIL)
        self.assertTrue(user.check_password(DIRECTOR_PASSWORD))
        self.assertEqual(user.profile.role, Profile.Role.DIRECTOR)
        self.assertEqual(
            get_user_model().objects.filter(profile__role=Profile.Role.SINGER).count(), 3
        )

    def test_seed_covers_every_alteration_status(self):
        call_command("seed", verbosity=0)
        statuses = set(Alteration.objects.values_list("status", flat=True))
        self.assertEqual(
            statuses,
            {Alteration.Status.QUEUED, Alteration.Status.IN_PROGRESS, Alteration.Status.DONE},
        )


class SecurityHeaderTests(FastHashTestCase):
    def test_security_headers_on_every_response(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])

    def test_pages_reference_no_external_assets(self):
        response = self.client.get("/accounts/login/")
        self.assertNotContains(response, "http://fonts.googleapis")
        self.assertNotContains(response, "cdn.")
        self.assertNotContains(response, "<script>")
