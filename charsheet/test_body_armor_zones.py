from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import DEFENSE_RS, QUALITY_EXCELLENT
from charsheet.models import (
    ArmorStats,
    Character,
    CharacterItem,
    Item,
    ItemRune,
    Modifier,
    Race,
    Rune,
    ShieldStats,
)
from charsheet.sheet_context import (
    _build_shop_item_groups,
    _build_shop_sell_item_groups,
    build_character_sheet_context,
)


FULL_ARMOR_COVERAGE = {
    "covers_head": True,
    "covers_face": True,
    "covers_eyes": False,
    "covers_neck": True,
    "covers_torso": True,
    "covers_organs": True,
    "covers_soft_tissue": True,
    "covers_arm_left": True,
    "covers_hand_left": True,
    "covers_leg_left": True,
    "covers_foot_left": True,
    "covers_arm_right": True,
    "covers_hand_right": True,
    "covers_leg_right": True,
    "covers_foot_right": True,
}


class BodyArmorZoneTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="body-armor-user", password="secret")
        race = Race.objects.create(name="Mensch")
        self.character = Character.objects.create(owner=self.user, name="Geralt", race=race)

    @staticmethod
    def _item(name: str, item_type: str = Item.ItemType.ARMOR, **kwargs) -> Item:
        return Item.objects.create(
            name=name,
            price=kwargs.pop("price", 1),
            item_type=item_type,
            stackable=False,
            weight=kwargs.pop("weight", 1),
            **kwargs,
        )

    def test_equipped_complete_armor_fills_every_covered_sheet_zone(self):
        armor = self._item("Vollplatte", price=8000, weight=Decimal("35"))
        ArmorStats.objects.create(
            item=armor,
            rs_total=12,
            encumbrance=4,
            min_st=6,
            **FULL_ARMOR_COVERAGE,
        )
        CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            equipped=True,
            armor_rs_total_override=15,
        )

        context = build_character_sheet_context(self.character, read_only=True)

        self.assertEqual(context["armor_summary"]["total_rs"], 15)
        self.assertEqual(context["body_armor"]["head"], 15)
        self.assertEqual(context["body_armor"]["face"], 15)
        self.assertEqual(context["body_armor"]["neck"], 15)
        self.assertEqual(context["body_armor"]["hand_left"], 15)
        self.assertEqual(context["body_armor"]["foot_right"], 15)
        self.assertEqual(context["body_armor"]["eyes"], 0)

        html = render_to_string("charsheet/partials/_sheet_secondary_page.html", context)
        self.assertIn('Kopf (-6)</span><span class="pill">15</span>', html)
        self.assertIn('Gesicht (-8)</span><span class="pill">15</span>', html)
        self.assertIn('Augen (-9 / -14)</span><span class="pill empty"></span>', html)
        self.assertIn('Rechte Hand (-8)</span><span class="pill">15</span>', html)

    def test_grs_sums_six_main_zones_then_divides_once(self):
        zone_values = {
            "head": 10,
            "torso": 14,
            "arm_left": 11,
            "arm_right": 11,
            "leg_left": 13,
            "leg_right": 13,
        }
        for zone, rs in zone_values.items():
            item = self._item(f"Teil {zone}")
            ArmorStats.objects.create(
                item=item,
                rs_total=rs,
                **{f"covers_{zone}": True},
            )
            CharacterItem.objects.create(owner=self.character, item=item, equipped=True)

        self.assertEqual(sum(zone_values.values()), 72)
        self.assertEqual(self.character.engine.armor_zone_protection(), {
            "head": 10,
            "face": 0,
            "eyes": 0,
            "neck": 0,
            "torso": 14,
            "organs": 0,
            "soft_tissue": 0,
            "arm_left": 11,
            "hand_left": 0,
            "leg_left": 13,
            "foot_left": 0,
            "arm_right": 11,
            "hand_right": 0,
            "leg_right": 13,
            "foot_right": 0,
        })
        self.assertEqual(self.character.engine.get_grs(), 12)

    def test_set_generation_creates_named_physical_items_with_grw_distribution(self):
        armor = self._item("Vollplatte", price=8000, weight=Decimal("35"))

        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=12,
            encumbrance=4,
            min_st=6,
            **FULL_ARMOR_COVERAGE,
        )

        components = {
            component.component_type: component
            for component in stats.components.select_related("item")
        }
        self.assertEqual(len(components), 6)
        self.assertEqual(components["helmet"].item.name, "Vollplatte – Helm")
        self.assertEqual(components["helmet"].item.weight, Decimal("3.500"))
        self.assertEqual(components["helmet"].item.price, 1600)
        self.assertEqual(components["torso"].item.weight, Decimal("12.600"))
        self.assertEqual(components["arm_left"].item.weight, Decimal("3.675"))
        self.assertEqual(components["arm_left"].item.price, 1000)
        self.assertEqual(components["leg_left"].item.weight, Decimal("5.775"))
        self.assertEqual(components["leg_left"].item.price, 1000)
        self.assertEqual(sum(component.item.weight for component in components.values()), Decimal("35.000"))
        self.assertEqual(sum(component.item.price for component in components.values()), 8000)
        self.assertTrue(components["helmet"].covers_head)
        self.assertTrue(components["helmet"].covers_face)
        self.assertFalse(components["helmet"].covers_eyes)
        self.assertTrue(components["helmet"].covers_neck)
        self.assertTrue(components["arm_left"].covers_arm_left)
        self.assertTrue(components["arm_left"].covers_hand_left)
        self.assertTrue(components["leg_right"].covers_leg_right)
        self.assertTrue(components["leg_right"].covers_foot_right)

    def test_partial_armor_uses_literal_rulebook_prices_without_normalizing(self):
        armor = self._item("Bänderpanzer", price=1000, weight=Decimal("12"))
        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=5,
            covers_head=True,
            covers_torso=True,
            covers_arm_left=True,
            covers_arm_right=True,
            covers_leg_left=True,
            covers_leg_right=True,
        )

        components = {
            component.component_type: component.item
            for component in stats.components.select_related("item")
        }

        self.assertEqual(
            {component_type: item.price for component_type, item in components.items()},
            {
                "helmet": 200,
                "torso": 300,
                "arm_left": 75,
                "arm_right": 75,
                "leg_left": 75,
                "leg_right": 75,
            },
        )
        self.assertEqual(sum(item.price for item in components.values()), 800)
        self.assertEqual(sum(item.weight for item in components.values()), Decimal("12.000"))

    def test_special_armor_can_use_literal_component_prices_and_zone_rs(self):
        armor = self._item("Bestiarius", price=1780, weight=Decimal("7.75"))
        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=3,
            zone_rs_overrides={"head": 11, "face": 11, "torso": 5},
            component_price_helmet_override=1600,
            component_price_torso_override=180,
            covers_head=True,
            covers_face=True,
            covers_torso=True,
        )

        helmet = stats.components.get(component_type="helmet")
        torso = stats.components.get(component_type="torso")

        self.assertEqual(helmet.item.price, 1600)
        self.assertEqual(torso.item.price, 180)
        self.assertEqual(helmet.zone_rs_overrides, {"head": 11, "face": 11})
        self.assertEqual(torso.zone_rs_overrides, {"torso": 5})

    def test_rulebook_price_row_is_combined_into_six_physical_items(self):
        armor = self._item("Tabellenrüstung", price=9999, weight=Decimal("20"))
        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=6,
            component_price_helmet_override=200,
            component_price_arms_override=150,
            component_price_legs_override=150,
            component_price_hands_override=100,
            component_price_feet_override=100,
            component_price_torso_override=300,
            **FULL_ARMOR_COVERAGE,
        )

        prices = {
            component.component_type: component.item.price
            for component in stats.components.select_related("item")
        }

        self.assertEqual(
            prices,
            {
                "helmet": 200,
                "torso": 300,
                "arm_left": 125,
                "arm_right": 125,
                "leg_left": 125,
                "leg_right": 125,
            },
        )
        self.assertEqual(sum(prices.values()), 1000)

    def test_magic_armor_still_generates_components_because_only_item_type_matters(self):
        armor = self._item("Arkane Vollplatte", price=8000, weight=35, is_magic=True)

        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=12,
            **FULL_ARMOR_COVERAGE,
        )

        self.assertEqual(stats.components.count(), 6)

    def test_generation_can_be_suppressed_explicitly(self):
        armor = self._item("Unteilbare Rüstung", price=8000, weight=35)

        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=12,
            suppress_component_generation=True,
            **FULL_ARMOR_COVERAGE,
        )

        self.assertFalse(stats.components.exists())

    def test_enabling_suppression_removes_existing_generated_components(self):
        armor = self._item("Versiegelte Rüstung", price=8000, weight=35)
        stats = ArmorStats.objects.create(item=armor, rs_total=12, **FULL_ARMOR_COVERAGE)
        component_item_ids = list(stats.components.values_list("item_id", flat=True))
        self.assertEqual(len(component_item_ids), 6)

        stats.suppress_component_generation = True
        stats.save()

        self.assertFalse(stats.components.exists())
        self.assertFalse(Item.objects.filter(pk__in=component_item_ids).exists())

    def test_hit_zone_booleans_are_unselected_by_default(self):
        armor = self._item("Leere Rüstungsvorlage")
        stats = ArmorStats(item=armor, rs_total=1)

        self.assertTrue(
            all(not getattr(stats, f"covers_{zone}") for zone in ArmorStats.ZONE_FIELDS)
        )

    def test_shop_groups_generated_components_as_armor_parts(self):
        armor = self._item("Shopplatte", price=8000, weight=35)
        stats = ArmorStats.objects.create(item=armor, rs_total=12, **FULL_ARMOR_COVERAGE)
        component = stats.components.select_related("item").get(component_type="helmet").item
        CharacterItem.objects.create(owner=self.character, item=armor)
        CharacterItem.objects.create(owner=self.character, item=component)

        buy_groups = {group["key"]: group for group in _build_shop_item_groups()}
        sell_groups = {
            group["key"]: group
            for group in _build_shop_sell_item_groups(self.character)
        }

        self.assertIn(armor.name, {row["name"] for row in buy_groups["armor"]["items"]})
        self.assertNotIn(component.name, {row["name"] for row in buy_groups["armor"]["items"]})
        self.assertEqual(buy_groups["armor_component"]["label"], "Rüstungsteile")
        self.assertIn(
            component.name,
            {row["name"] for row in buy_groups["armor_component"]["items"]},
        )
        self.assertIn(
            component.name,
            {row["name"] for row in sell_groups["armor_component"]["items"]},
        )
        shop_html = render_to_string(
            "charsheet/partials/_shop_panel.html",
            build_character_sheet_context(self.character, read_only=True),
        )
        self.assertIn("<span>Rüstungsteile</span>", shop_html)
        self.assertIn(component.name, shop_html)

    def test_component_sync_keeps_group_and_recalculates_it_when_subzone_is_removed(self):
        armor = self._item("Wandelplatte", price=8000, weight=35)
        stats = ArmorStats.objects.create(item=armor, rs_total=12, **FULL_ARMOR_COVERAGE)
        leg_item_id = stats.components.get(component_type="leg_right").item_id

        stats.covers_foot_right = False
        stats.save()

        leg = stats.components.get(component_type="leg_right")
        self.assertEqual(leg.item_id, leg_item_id)
        self.assertTrue(leg.covers_leg_right)
        self.assertFalse(leg.covers_foot_right)
        self.assertEqual(leg.item.price, 600)
        self.assertEqual(stats.components.count(), 6)
        self.assertFalse(
            stats.components.filter(
                component_type__in=("hand_left", "hand_right", "foot_left", "foot_right")
            ).exists()
        )

    def test_quality_and_armor_rune_modify_each_covered_hit_zone(self):
        armor = self._item("Runenhelm")
        ArmorStats.objects.create(
            item=armor,
            rs_total=10,
            suppress_component_generation=True,
            covers_head=True,
            covers_face=True,
        )
        character_item = CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            quality_id=QUALITY_EXCELLENT,
            equipped=True,
        )
        rune = Rune.objects.create(name="Schutzrune", slug="schutzrune")
        rune.modifier_templates.create(
            target_kind=Modifier.TargetKind.STAT,
            target_slug=DEFENSE_RS,
            value=2,
        )
        ItemRune.objects.create(item=character_item, rune=rune)

        protection = self.character.engine.armor_zone_protection()

        self.assertEqual(protection["head"], 13)
        self.assertEqual(protection["face"], 13)
        self.assertEqual(protection["neck"], 0)
        self.assertEqual(self.character.engine.get_grs(), 2)

    def test_full_armor_rune_is_not_added_again_to_grs(self):
        armor = self._item("Runenvollplatte")
        ArmorStats.objects.create(
            item=armor,
            rs_total=10,
            suppress_component_generation=True,
            **FULL_ARMOR_COVERAGE,
        )
        character_item = CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            quality_id=QUALITY_EXCELLENT,
            equipped=True,
        )
        rune = Rune.objects.create(name="Vollschutzrune", slug="vollschutzrune")
        rune.modifier_templates.create(
            target_kind=Modifier.TargetKind.STAT,
            target_slug=DEFENSE_RS,
            value=2,
        )
        ItemRune.objects.create(item=character_item, rune=rune)

        protection = self.character.engine.armor_zone_protection()

        self.assertEqual(protection["head"], 13)
        self.assertEqual(protection["torso"], 13)
        self.assertEqual(protection["arm_left"], 13)
        self.assertEqual(protection["leg_right"], 13)
        self.assertEqual(self.character.engine.get_grs(), 13)
        context = build_character_sheet_context(self.character, read_only=True)
        armor_row = context["armor_rows"][0]
        self.assertIn("(RS 13 |", armor_row["summary"])
        self.assertIn("| RS | 13 |", armor_row["tooltip_text"])

    def test_complete_armor_uses_stored_minimum_strength_instead_of_half_grs(self):
        armor = self._item("Starke Gesamtrüstung")
        ArmorStats.objects.create(
            item=armor,
            rs_total=16,
            min_st=6,
            suppress_component_generation=True,
            **FULL_ARMOR_COVERAGE,
        )
        CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            equipped=True,
        )

        context = build_character_sheet_context(self.character, read_only=True)

        self.assertEqual(self.character.engine.get_grs(), 16)
        self.assertEqual(self.character.engine.get_ms(), 6)
        self.assertEqual(context["armor_summary"]["minimum_strength"], 6)
        self.assertIn("Gesamtrüstung", context["armor_summary"]["minimum_strength_tooltip"])

    def test_generated_armor_parts_derive_minimum_strength_from_grs(self):
        armor = self._item("Teilrüstung")
        stats = ArmorStats.objects.create(
            item=armor,
            rs_total=12,
            min_st=6,
            covers_head=True,
            covers_torso=True,
        )
        for component in stats.components.select_related("item"):
            CharacterItem.objects.create(
                owner=self.character,
                item=component.item,
                equipped=True,
            )

        self.assertEqual(self.character.engine.get_grs(), 4)
        self.assertEqual(self.character.engine.get_ms(), 2)
        context = build_character_sheet_context(self.character, read_only=True)
        self.assertIn(
            "Einzelteile: RS / 2, aufrunden",
            context["armor_summary"]["minimum_strength_tooltip"],
        )

    def test_shield_and_equipping_refresh_the_secondary_page_partial(self):
        armor = self._item("Helm")
        ArmorStats.objects.create(item=armor, rs_total=3, covers_head=True)
        character_item = CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            equipped=False,
        )
        shield = self._item("Turmschild", item_type=Item.ItemType.SHIELD)
        ShieldStats.objects.create(item=shield, rs=4)
        CharacterItem.objects.create(owner=self.character, item=shield, equipped=True)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("toggle_equip", args=[character_item.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        secondary_page = next(
            partial["html"]
            for partial in response.json()["partials"]
            if partial["target"] == "sheetSecondaryPage"
        )
        self.assertIn('Schild (-4)</span><span class="pill">4</span>', secondary_page)
        self.assertIn('Kopf (-6)</span><span class="pill">3</span>', secondary_page)
