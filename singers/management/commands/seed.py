"""Idempotent demo seed: accounts, robe sizes, singers, alterations and venues.

Re-running never duplicates rows and never overwrites edits the director made
(robe assignments, dress-code text, notes, statuses). It only fills what is
missing.
"""

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from singers.models import Alteration, Profile, RobeSize, Singer, Venue

# Demo credentials are overridable through the environment, with the documented
# development values as the fallback so a fresh clone always has a way in.
DIRECTOR = {
    "username": "cenius",
    "email": "cenius@cenius.ai",
    "password": os.environ.get("CHOIR_DEMO_PASSWORD", "cenius"),
    "first_name": "Cenius",
    "last_name": "Doyle",
}

SINGER_ACCOUNTS = [
    {"username": "nadia", "email": "nadia@choir.test", "first_name": "Nadia", "last_name": "Okonkwo"},
    {"username": "rowan", "email": "rowan@choir.test", "first_name": "Rowan", "last_name": "Whitfield"},
    {"username": "aisling", "email": "aisling@choir.test", "first_name": "Aisling", "last_name": "Byrne"},
]
SINGER_PASSWORD = os.environ.get("CHOIR_DEMO_SINGER_PASSWORD", "singer-demo")

ROBE_SIZES = [
    {"code": "S", "chest_range": "32-34", "length_inches": 54, "notes": "Junior cut — closet rail A"},
    {"code": "M", "chest_range": "36-38", "length_inches": 56, "notes": "Most common size — closet rail A"},
    {"code": "L", "chest_range": "40-42", "length_inches": 58, "notes": "Closet rail B"},
    {"code": "XL", "chest_range": "44-46", "length_inches": 60, "notes": "Closet rail B"},
]

# full_name, voice_part, robe size code (None = awaiting assignment), linked account
SINGERS = [
    ("Naomi Ferreira", "soprano", "M", None),
    ("Hollis Grant", "soprano", "S", None),
    ("Priya Raghunathan", "soprano", None, None),
    ("Nadia Okonkwo", "soprano", "M", "nadia"),
    ("Elena Márquez", "alto", "M", None),
    ("Greta Lindqvist", "alto", "S", None),
    ("Dana Osei", "alto", None, None),
    ("Aisling Byrne", "alto", "L", "aisling"),
    ("Marcus Bell", "tenor", "L", None),
    ("Tomás Silva", "tenor", "L", None),
    ("Yusuf Adeyemi", "bass", "XL", None),
    ("Rowan Whitfield", "bass", "XL", "rowan"),
]

# singer, status, requested (days ago), due (days from today, None allowed),
# completed (days ago when done), notes
ALTERATIONS = [
    (
        "Nadia Okonkwo",
        Alteration.Status.IN_PROGRESS,
        8,
        3,
        None,
        "Take in the waist by 1 inch and shorten the sleeves ½ inch.\n"
        "Pinned at the fitting on the 12th — check the shoulder seam before sewing.",
    ),
    (
        "Hollis Grant",
        Alteration.Status.QUEUED,
        3,
        5,
        None,
        "Hem two inches so it clears the floor; the left sleeve sits high at the cuff.",
    ),
    (
        "Marcus Bell",
        Alteration.Status.QUEUED,
        1,
        9,
        None,
        "Let out the shoulders 1 inch and re-press the back pleats before the winter concert.",
    ),
    (
        "Elena Márquez",
        Alteration.Status.IN_PROGRESS,
        12,
        -2,
        None,
        "Replace the concealed zip (teeth worn) and re-stitch the hook at the collar.\n"
        "Zip ordered from the supplier; waiting on delivery.",
    ),
    (
        "Yusuf Adeyemi",
        Alteration.Status.DONE,
        21,
        None,
        14,
        "Shortened the hem 3 inches and pressed the pleats. Collected after rehearsal.",
    ),
    (
        "Greta Lindqvist",
        Alteration.Status.DONE,
        30,
        None,
        25,
        "Took in the bodice 1½ inches and fitted a new hook at the collar.",
    ),
]

VENUES = [
    {
        "name": "St Brigid's Hall",
        "address": "14 Harbour Row, Galway",
        "dress_code": (
            "Full-length black robe with the emerald sash over the right shoulder.\n"
            "White cotton gloves and black flat shoes — no heels on the wooden stage.\n"
            "Warm-up in the green room with the sash folded, not worn."
        ),
        "notes": "Winter concert venue; stage door on the left of the hall.",
    },
    {
        "name": "The Old Mill Theatre",
        "address": "3 Mill Lane, Sligo",
        "dress_code": (
            "Concert black: robe, black long-sleeve top under the robe, black shoes.\n"
            "Silver choir pin on the left lapel. No jewellery at the wrists.\n"
            "Sashes are not worn at this venue — the stage lighting is warm."
        ),
        "notes": "Spring showcase; raked stage, so hems must clear the ankle.",
    },
    {
        "name": "Riverside Community Church",
        "address": "88 Riverbank Road, Limerick",
        "dress_code": (
            "Cassock and cotta, both pressed, with the choir's blue stole.\n"
            "Dark socks and closed black shoes; nothing visible below the hem.\n"
            "Hair tied back; no scarves during the service."
        ),
        "notes": "Sunday service and the charity carol evening.",
    },
]


class Command(BaseCommand):
    help = "Load idempotent demo data: director + singer accounts, sizes, singers, tickets, venues."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        created = {"users": 0, "sizes": 0, "singers": 0, "alterations": 0, "venues": 0}

        director = self._ensure_user(
            User,
            DIRECTOR,
            DIRECTOR["password"],
            Profile.Role.DIRECTOR,
            is_staff=True,
        )
        created["users"] += director["created"]
        director_user = director["user"]

        singer_users = {}
        for account in SINGER_ACCOUNTS:
            result = self._ensure_user(
                User, account, SINGER_PASSWORD, Profile.Role.SINGER
            )
            created["users"] += result["created"]
            singer_users[account["username"]] = result["user"]

        sizes = {}
        for row in ROBE_SIZES:
            size, made = RobeSize.objects.get_or_create(
                code=row["code"],
                defaults={
                    "chest_range": row["chest_range"],
                    "length_inches": row["length_inches"],
                    "notes": row["notes"],
                },
            )
            sizes[row["code"]] = size
            created["sizes"] += int(made)

        singers = {}
        for full_name, voice_part, size_code, account in SINGERS:
            singer, made = Singer.objects.get_or_create(
                full_name=full_name,
                defaults={
                    "voice_part": voice_part,
                    "robe_size": sizes[size_code] if size_code else None,
                    "user": singer_users.get(account) if account else None,
                },
            )
            if account and singer.user_id is None:
                singer.user = singer_users[account]
                singer.save(update_fields=["user"])
            singers[full_name] = singer
            created["singers"] += int(made)

        today = timezone.localdate()
        for full_name, status, requested_days, due_days, completed_days, notes in ALTERATIONS:
            singer = singers[full_name]
            if Alteration.objects.filter(singer=singer).exists():
                continue
            Alteration.objects.create(
                singer=singer,
                status=status,
                seamstress_notes=notes,
                requested_at=today - timedelta(days=requested_days),
                due_date=today + timedelta(days=due_days) if due_days is not None else None,
                completed_at=(
                    timezone.now() - timedelta(days=completed_days)
                    if completed_days is not None
                    else None
                ),
                created_by=director_user,
            )
            created["alterations"] += 1

        for row in VENUES:
            _, made = Venue.objects.get_or_create(
                name=row["name"],
                defaults={
                    "address": row["address"],
                    "dress_code": row["dress_code"],
                    "notes": row["notes"],
                },
            )
            created["venues"] += int(made)

        if options.get("verbosity", 1) >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    "Seed complete — "
                    f"{created['users']} new accounts, "
                    f"{created['sizes']} new robe sizes, "
                    f"{created['singers']} new singers, "
                    f"{created['alterations']} new alterations, "
                    f"{created['venues']} new venues."
                )
            )
            self.stdout.write(
                "Director sign-in: cenius / cenius. Singer sign-in: nadia / singer-demo."
            )

    @staticmethod
    def _ensure_user(User, account, password, role, is_staff=False):
        user, made = User.objects.get_or_create(
            username=account["username"],
            defaults={
                "email": account["email"],
                "first_name": account["first_name"],
                "last_name": account["last_name"],
                "is_staff": is_staff,
            },
        )
        # The documented demo credentials must keep working on every boot.
        if made or not user.check_password(password):
            user.set_password(password)
        user.email = account["email"]
        user.first_name = account["first_name"]
        user.last_name = account["last_name"]
        user.is_staff = is_staff
        user.save()
        Profile.objects.update_or_create(user=user, defaults={"role": role})
        return {"user": user, "created": int(made)}
