from django.urls import path

from . import announcement_views as views


urlpatterns = [
    path("create/", views.create_announcement, name="create_announcement"),
    path(
        "<int:pk>/delete/", views.delete_announcement,
        name="delete_announcement",
    ),
]
