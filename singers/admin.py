from django.contrib import admin

from .models import Alteration, Profile, RobeSize, Singer, Venue


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)


@admin.register(RobeSize)
class RobeSizeAdmin(admin.ModelAdmin):
    list_display = ("code", "chest_range", "length_inches")
    search_fields = ("code", "chest_range")


@admin.register(Singer)
class SingerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "voice_part", "robe_size", "created_at")
    list_filter = ("voice_part", "robe_size")
    search_fields = ("full_name",)
    list_select_related = ("robe_size",)


@admin.register(Alteration)
class AlterationAdmin(admin.ModelAdmin):
    list_display = ("singer", "status", "requested_at", "due_date", "completed_at")
    list_filter = ("status",)
    search_fields = ("singer__full_name", "seamstress_notes")
    list_select_related = ("singer",)


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "address")
    search_fields = ("name", "address", "dress_code")
