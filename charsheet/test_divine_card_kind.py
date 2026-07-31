from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase

from charsheet.constants import SCHOOL_DIVINE
from charsheet.models import (
    Character,
    CharacterDivineEntity,
    DivineEntity,
    Race,
    School,
    SchoolType,
)
from charsheet.sheet_context import build_character_sheet_context
from charsheet.views import _debug_god_card_context


class DivineCardKindTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="divine-card-kind-user",
            password="test12345",
        )
        race = Race.objects.create(name="Divine Card Kind Race")
        self.character = Character.objects.create(
            owner=user,
            name="Malphas",
            race=race,
        )

    def _bind_entity(self, *, school_name: str, type_name: str, type_slug: str):
        school_type, _ = SchoolType.objects.get_or_create(
            slug=type_slug,
            defaults={"name": type_name},
        )
        school = School.objects.create(name=school_name, type=school_type)
        entity = DivineEntity.objects.create(
            name=f"Entity {school_name} {type_name}",
            slug=f"entity-{school.pk}",
            school=school,
            pantheon="Dämonenfürsten",
        )
        CharacterDivineEntity.objects.create(
            character=self.character,
            entity=entity,
        )
        return entity

    def test_cultist_school_renders_daemon_instead_of_deity(self):
        entity = self._bind_entity(
            school_name="Kultist",
            type_name="Klerikale Schule",
            type_slug=SCHOOL_DIVINE,
        )

        context = build_character_sheet_context(self.character)

        self.assertEqual(context["selected_divine_card_kind_label"], "Dämon")
        html = render_to_string(
            "charsheet/partials/_god_card.html",
            {
                "divine_entity": entity,
                "selected_divine_card_title": entity.name,
                "selected_divine_card_kind_label": context[
                    "selected_divine_card_kind_label"
                ],
                "selected_divine_card_typebar": context[
                    "selected_divine_card_typebar"
                ],
            },
        )
        self.assertIn("Dämon", html)
        self.assertIn("Dämonenfürsten", html)
        self.assertIn("card--daemon", html)
        debug_context = _debug_god_card_context(entity, "divine")
        self.assertEqual(
            debug_context["selected_divine_card_kind_label"],
            "Dämon",
        )
        self.assertIn(
            "card--daemon",
            render_to_string(
                "charsheet/partials/_god_card.html",
                debug_context,
            ),
        )

    def test_cult_school_type_renders_daemon(self):
        self._bind_entity(
            school_name="Dunkler Pakt",
            type_name="Kult",
            type_slug="cult",
        )

        context = build_character_sheet_context(self.character)

        self.assertEqual(context["selected_divine_card_kind_label"], "Dämon")

    def test_regular_divine_school_keeps_deity_label(self):
        entity = self._bind_entity(
            school_name="Priestertum",
            type_name="Klerikale Schule",
            type_slug=SCHOOL_DIVINE,
        )

        context = build_character_sheet_context(self.character)

        self.assertEqual(context["selected_divine_card_kind_label"], "Gottheit")
        html = render_to_string(
            "charsheet/partials/_god_card.html",
            {
                "divine_entity": entity,
                "selected_divine_card_kind_label": context[
                    "selected_divine_card_kind_label"
                ],
            },
        )
        self.assertNotIn("card--daemon", html)
