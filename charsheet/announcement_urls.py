from django.urls import path

from . import announcement_views as views


urlpatterns = [
    path(
        "<int:pk>/update/", views.update_announcement,
        name="update_announcement",
    ),
    path("create/", views.create_announcement, name="create_announcement"),
    path(
        "<int:pk>/delete/", views.delete_announcement,
        name="delete_announcement",
    ),
]
