"""Forms: sign-in, roster, robe catalog, alterations and venues.

Every form is CSRF-protected and validated on the server; failures re-render
the page with the submitted values kept and an inline message at the field.
"""

import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Alteration, RobeSize, Singer, Venue

CHEST_RANGE_PATTERN = re.compile(r"^\d{1,2}\s*[-–]\s*\d{1,2}$")


class AccessibleFormMixin:
    """Mark failing widgets with aria-invalid and link them to their error text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            return
        for name in self.errors:
            field = self.fields.get(name)
            if field is None:
                continue
            field.widget.attrs["aria-invalid"] = "true"
            field.widget.attrs["aria-describedby"] = f"id_{name}-error"


class SignInForm(AccessibleFormMixin, AuthenticationForm):
    """One non-enumerating error for every failed sign-in."""

    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autofocus": True,
                "placeholder": "cenius",
                "id": "id_username",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "id": "id_password"}
        ),
    )

    error_messages = {
        "invalid_login": "Those credentials did not match our records. Please try again.",
        "inactive": "This account is not active. Ask the choir director for access.",
    }


class SingerCreateForm(AccessibleFormMixin, forms.ModelForm):
    class Meta:
        model = Singer
        fields = ["full_name", "voice_part", "notes"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"placeholder": "e.g. Naomi Ferreira", "autocomplete": "off"}
            ),
            "notes": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Optional: fitting preferences, contact note…"}
            ),
        }

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise forms.ValidationError("Enter the singer's name.")
        if len(name) < 2:
            raise forms.ValidationError("Enter at least two characters for the name.")
        return name


class SingerUpdateForm(AccessibleFormMixin, forms.ModelForm):
    """Robe assignment plus the fields the director edits on the detail page."""

    needs_alteration = forms.BooleanField(required=False, label="Needs alteration")
    alteration_note = forms.CharField(
        required=False,
        label="Seamstress note",
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": "e.g. Hem 2 inches, take in the waist"}
        ),
    )

    class Meta:
        model = Singer
        fields = ["full_name", "voice_part", "robe_size", "notes"]
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "robe_size": forms.Select(),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["robe_size"].queryset = RobeSize.objects.all()
        self.fields["robe_size"].empty_label = "Unassigned"
        self.fields["robe_size"].required = False
        self.fields["robe_size"].label = "Robe size"

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Enter at least two characters for the name.")
        return name

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("needs_alteration"):
            if not cleaned.get("robe_size"):
                self.add_error(
                    "robe_size",
                    "Assign a robe size from the catalog before raising an alteration.",
                )
            if not (cleaned.get("alteration_note") or "").strip():
                self.add_error(
                    "alteration_note",
                    "Write a short seamstress note so the queue is actionable.",
                )
        return cleaned


class RobeSizeForm(AccessibleFormMixin, forms.ModelForm):
    length_inches = forms.IntegerField(
        label="Length (in)",
        min_value=24,
        max_value=90,
        error_messages={
            "invalid": "Enter a whole number of inches, e.g. 56.",
            "min_value": "Length must be at least 24 inches.",
            "max_value": "Length must be 90 inches or less.",
        },
    )

    class Meta:
        model = RobeSize
        fields = ["code", "chest_range", "length_inches", "notes"]
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "e.g. M", "autocomplete": "off"}),
            "chest_range": forms.TextInput(attrs={"placeholder": "e.g. 38-40"}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def clean_code(self):
        code = " ".join(self.cleaned_data["code"].split()).upper()
        if not code:
            raise forms.ValidationError("Enter a size code, e.g. M.")
        return code

    def clean_chest_range(self):
        value = " ".join(self.cleaned_data["chest_range"].split())
        if not CHEST_RANGE_PATTERN.match(value):
            raise forms.ValidationError("Use a chest range like 38-40.")
        low, high = [int(part) for part in re.split(r"\s*[-–]\s*", value)]
        if low >= high:
            raise forms.ValidationError("The lower chest measurement must come first.")
        return f"{low}-{high}"


class AlterationCreateForm(AccessibleFormMixin, forms.ModelForm):
    class Meta:
        model = Alteration
        fields = ["singer", "seamstress_notes", "due_date"]
        widgets = {
            "seamstress_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Pinning, hem, sleeve length — what needs doing?",
                }
            ),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["singer"].queryset = Singer.objects.select_related("robe_size").order_by(
            "full_name"
        )
        self.fields["singer"].empty_label = "Choose a singer"
        self.fields["singer"].required = True
        self.fields["seamstress_notes"].required = True
        self.fields["seamstress_notes"].error_messages = {
            "required": "Describe the alteration so the seamstress knows what to do."
        }

    def clean_singer(self):
        singer = self.cleaned_data["singer"]
        if singer is None:  # pragma: no cover - required field guards this
            raise forms.ValidationError("Choose a singer for this ticket.")
        return singer


class AlterationUpdateForm(AccessibleFormMixin, forms.ModelForm):
    class Meta:
        model = Alteration
        fields = ["seamstress_notes", "due_date"]
        widgets = {
            "seamstress_notes": forms.Textarea(
                attrs={"rows": 7, "placeholder": "Pinning, hem, sleeve changes…"}
            ),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }


class VenueForm(AccessibleFormMixin, forms.ModelForm):
    class Meta:
        model = Venue
        fields = ["name", "address", "dress_code", "notes"]
        error_messages = {
            "dress_code": {"required": "Enter the dress code the choir wears at this venue."},
            "name": {"required": "Enter the venue name."},
            "address": {"required": "Enter the venue address."},
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. St Brigid's Hall"}),
            "address": forms.Textarea(attrs={"rows": 2, "placeholder": "Street, city"}),
            "dress_code": forms.Textarea(
                attrs={"rows": 4, "placeholder": "e.g. Full robe, black shoes, white gloves"}
            ),
            "notes": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError("Enter the venue name.")
        return name

    def clean_dress_code(self):
        code = self.cleaned_data["dress_code"].strip()
        if not code:
            raise forms.ValidationError(
                "Enter the dress code the choir wears at this venue."
            )
        return code
