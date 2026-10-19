"""Domain models: profiles, singers, robe sizes, alterations and venues."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    """Role marker attached to every account (exactly one director)."""

    class Role(models.TextChoices):
        DIRECTOR = "director", "Director"
        SINGER = "singer", "Singer"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.DIRECTOR)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def is_director(self) -> bool:
        return self.role == self.Role.DIRECTOR


class RobeSize(models.Model):
    """A stocked robe size from the catalog."""

    code = models.CharField(max_length=12, unique=True)
    chest_range = models.CharField(max_length=24, help_text="Inches, e.g. 38-40")
    length_inches = models.PositiveSmallIntegerField(help_text="Garment length in inches")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["length_inches", "code"]
        verbose_name = "robe size"

    def __str__(self) -> str:
        return f"{self.code} ({self.chest_range})"

    @property
    def singers_in_use(self) -> int:
        return self.singers.count()


class Singer(models.Model):
    """A choir member who wears a robe."""

    class VoicePart(models.TextChoices):
        SOPRANO = "soprano", "Soprano"
        ALTO = "alto", "Alto"
        TENOR = "tenor", "Tenor"
        BASS = "bass", "Bass"

    full_name = models.CharField(max_length=120)
    voice_part = models.CharField(max_length=16, choices=VoicePart.choices)
    robe_size = models.ForeignKey(
        RobeSize,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="singers",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="singer",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["voice_part"])]

    def __str__(self) -> str:
        return self.full_name

    def _ordered_alterations(self):
        """Use a prefetch cache when the page loaded one, avoiding N+1."""
        return self.alterations.all()

    @property
    def open_alteration(self):
        """The newest ticket that is not yet done, if any."""
        for alteration in self._ordered_alterations():
            if alteration.status != Alteration.Status.DONE:
                return alteration
        return None

    @property
    def latest_alteration(self):
        return next(iter(self._ordered_alterations()), None)


class Alteration(models.Model):
    """An alteration ticket in the seamstress queue."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    singer = models.ForeignKey(Singer, on_delete=models.CASCADE, related_name="alterations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    seamstress_notes = models.TextField(blank=True)
    requested_at = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alterations_created",
    )

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [models.Index(fields=["status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["queued", "in_progress", "done"]),
                name="alteration_status_valid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.singer.full_name} — {self.get_status_display()}"

    def clean(self) -> None:
        super().clean()
        if self.status not in self.Status.values:
            raise ValidationError({"status": "Status must be queued, in progress, or done."})

    @property
    def is_done(self) -> bool:
        return self.status == self.Status.DONE

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.due_date and not self.is_done and self.due_date < timezone.localdate()
        )

    @property
    def notes_excerpt(self) -> str:
        text = " ".join(self.seamstress_notes.split())
        return text if len(text) <= 90 else f"{text[:87].rstrip()}…"

    def apply_status(self, new_status: str) -> bool:
        """Move the ticket through the workflow; returns True when it changed."""
        if new_status not in self.Status.values:
            raise ValidationError("Unknown alteration status.")
        if new_status == self.status:
            return False
        self.status = new_status
        if new_status == self.Status.DONE:
            self.completed_at = timezone.now()
        else:
            self.completed_at = None
        return True


class Venue(models.Model):
    """A concert venue together with the dress code worn there."""

    name = models.CharField(max_length=140)
    address = models.TextField()
    dress_code = models.TextField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def dress_code_excerpt(self) -> str:
        text = " ".join(self.dress_code.split())
        return text if len(text) <= 120 else f"{text[:117].rstrip()}…"
