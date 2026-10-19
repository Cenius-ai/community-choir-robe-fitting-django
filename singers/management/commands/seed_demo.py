"""Alias for ``manage.py seed`` kept for the documented two-command quickstart."""

from .seed import Command as SeedCommand


class Command(SeedCommand):
    help = "Alias of `manage.py seed` — loads idempotent demo data."
