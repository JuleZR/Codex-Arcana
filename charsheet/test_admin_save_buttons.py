"""Tests for shared Django admin form behavior."""

from django.contrib import admin
from django.test import SimpleTestCase


class AdminSaveButtonTests(SimpleTestCase):
    def test_all_registered_admin_forms_show_submit_buttons_on_top(self):
        admins_without_top_buttons = sorted(
            model_admin.model._meta.label
            for model_admin in admin.site._registry.values()
            if not model_admin.save_on_top
        )

        self.assertEqual(admins_without_top_buttons, [])
