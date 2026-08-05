from django.test import SimpleTestCase

from charsheet.armor_generation import sync_armor_set_components
from charsheet.models import Item


class ArmorGenerationTests(SimpleTestCase):
    def test_suppressed_generation_does_not_touch_components(self):
        class ComponentAccessFails:
            def select_related(self, *_args, **_kwargs):
                raise AssertionError("suppressed armor must not inspect generated components")

        class Armor:
            pk = 1
            item = Item(name="Test Armor", item_type=Item.ItemType.ARMOR)
            parent_set_id = None
            suppress_component_generation = True
            components = ComponentAccessFails()

        self.assertEqual(sync_armor_set_components.__wrapped__(Armor()), [])
