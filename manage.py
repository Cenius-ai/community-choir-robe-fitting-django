#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _bootstrap_for_runserver() -> None:
    """Self-heal on the boot path: ensure schema + demo data exist.

    Warm container reuse can skip the install phase, so a bare
    ``python manage.py runserver`` must still reach a populated app. Both steps
    are idempotent; the seed is skipped when the database already holds data so
    boots stay fast.
    """
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import connection

    call_command("migrate", interactive=False, verbosity=0)

    tables = set(connection.introspection.table_names())
    if "singers_singer" not in tables or "auth_user" not in tables:
        call_command("seed_demo", verbosity=0)
        return
    if not get_user_model().objects.exists() or not _has_any_singer():
        call_command("seed_demo", verbosity=0)


def _has_any_singer() -> bool:
    from singers.models import Singer

    return Singer.objects.exists()


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "choirfit.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - missing Django install
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available "
            "on your PYTHONPATH environment variable? Did you forget to "
            "activate a virtual environment?"
        ) from exc

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        _bootstrap_for_runserver()
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
