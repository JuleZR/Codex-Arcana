from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase

from charsheet.admin import TraitAdmin
from charsheet.models import Trait


class TraitAdminInlineTests(SimpleTestCase):
    def test_existing_trait_change_inlines_build(self):
        request = RequestFactory().get("/admin/charsheet/trait/1/change/")
        request.user = User(is_staff=True, is_superuser=True)
        trait = Trait(
            name="Test Trait",
            slug="test-trait",
            trait_type=Trait.TraitType.ADV,
            description="Test description",
        )
        admin = TraitAdmin(Trait, AdminSite())

        inline_names = []
        for inline in admin.get_inline_instances(request, trait):
            inline_names.append(type(inline).__name__)
            inline.get_formset(request, trait)

        self.assertIn("TraitSemanticEffectInline", inline_names)
