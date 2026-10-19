"""URL configuration for the Community Choir Robe Fitting app."""

from django.contrib import admin
from django.urls import path

from singers import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("accounts/login/", views.sign_in, name="login"),
    path("accounts/logout/", views.sign_out, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("me/", views.my_robe, name="my-robe"),
    path("singers/", views.singer_list, name="singer-list"),
    path("singers/<int:singer_id>/", views.singer_detail, name="singer-detail"),
    path("singers/<int:singer_id>/delete/", views.singer_delete, name="singer-delete"),
    path("robes/", views.robe_list, name="robe-list"),
    path("robes/<int:size_id>/", views.robe_update, name="robe-update"),
    path("robes/<int:size_id>/delete/", views.robe_delete, name="robe-delete"),
    path("alterations/", views.alteration_list, name="alteration-list"),
    path("alterations/<int:alteration_id>/", views.alteration_detail, name="alteration-detail"),
    path(
        "alterations/<int:alteration_id>/delete/",
        views.alteration_delete,
        name="alteration-delete",
    ),
    path("venues/", views.venue_list, name="venue-list"),
    path("venues/<int:venue_id>/", views.venue_detail, name="venue-detail"),
    path("venues/<int:venue_id>/delete/", views.venue_delete, name="venue-delete"),
]

handler403 = "singers.views.forbidden_page"
handler404 = "singers.views.not_found_page"
