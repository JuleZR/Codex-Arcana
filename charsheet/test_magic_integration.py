from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from charsheet.constants import SCHOOL_ARCANE, SCHOOL_DIVINE
from charsheet.learning import process_learning_submission
from charsheet.models import (
    Aspect,
    Character,
    CharacterDivineEntity,
    CharacterSchool,
    CharacterSpell,
    DivineEntity,
    DivineEntityAspect,
    Race,
    School,
    SchoolType,
    Spell,
)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class MagicIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mage", password="secret")
        self.race = Race.objects.create(name="Human")
        self.character = Character.objects.create(
            owner=self.user,
            name="Aria",
            race=self.race,
            current_experience=50,
            overall_experience=50,
        )

        self.arcane_type = SchoolType.objects.filter(slug=SCHOOL_ARCANE).first() or SchoolType.objects.filter(name="Magieschule").first()
        if self.arcane_type is None:
            self.arcane_type = SchoolType.objects.create(name="Magieschule", slug=SCHOOL_ARCANE)
        elif self.arcane_type.slug != SCHOOL_ARCANE:
            self.arcane_type.slug = SCHOOL_ARCANE
            self.arcane_type.save(update_fields=["slug"])

        self.divine_type = SchoolType.objects.filter(slug=SCHOOL_DIVINE).first() or SchoolType.objects.filter(name="Klerikale Schule").first()
        if self.divine_type is None:
            self.divine_type = SchoolType.objects.create(name="Klerikale Schule", slug=SCHOOL_DIVINE)
        elif self.divine_type.slug != SCHOOL_DIVINE:
            self.divine_type.slug = SCHOOL_DIVINE
            self.divine_type.save(update_fields=["slug"])
        self.arcane_school = School.objects.create(name="Pyromantie", type=self.arcane_type)
        self.divine_school = School.objects.create(name="Priesterschaft", type=self.divine_type)

    def test_sync_character_magic_grants_base_and_divine_spells(self):
        CharacterSchool.objects.create(character=self.character, school=self.arcane_school, level=2)
        CharacterSchool.objects.create(character=self.character, school=self.divine_school, level=2)

        aspect = Aspect.objects.create(name="Feuer", slug="feuer")
        entity = DivineEntity.objects.create(
            name="Sol",
            slug="sol",
            school=self.divine_school,
            entity_kind=DivineEntity.EntityKind.GOD,
        )
        DivineEntityAspect.objects.create(entity=entity, aspect=aspect, is_starting_aspect=True)
        CharacterDivineEntity.objects.create(character=self.character, entity=entity)

        arcane_base = Spell.objects.create(
            name="Funke",
            slug="funke",
            school=self.arcane_school,
            level=1,
            is_base_spell=True,
            kp_cost=1,
        )
        divine_spell = Spell.objects.create(
            name="Flammensegen",
            slug="flammensegen",
            aspect=aspect,
            level=2,
            kp_cost=2,
        )

        sync_result = self.character.get_magic_engine(refresh=True).sync_character_magic()

        self.assertGreaterEqual(sync_result["spells_created"], 2)
        self.assertTrue(CharacterSpell.objects.filter(character=self.character, spell=arcane_base, source_kind=CharacterSpell.SourceKind.BASE).exists())
        self.assertTrue(CharacterSpell.objects.filter(character=self.character, spell=divine_spell, source_kind=CharacterSpell.SourceKind.DIVINE_GRANTED).exists())

    def test_cast_spell_view_spends_arcane_power(self):
        CharacterSchool.objects.create(character=self.character, school=self.arcane_school, level=2)
        spell = Spell.objects.create(
            name="Funke",
            slug="funke_cast",
            school=self.arcane_school,
            level=1,
            is_base_spell=True,
            kp_cost=2,
        )
        CharacterSpell.objects.create(
            character=self.character,
            spell=spell,
            source_kind=CharacterSpell.SourceKind.BASE,
        )
        self.character.current_arcane_power = 5
        self.character.save(update_fields=["current_arcane_power"])

        client = Client()
        self.assertTrue(client.login(username="mage", password="secret"))
        response = client.post(
            reverse("cast_spell", args=[self.character.id, spell.id]),
            {"ajax": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.character.refresh_from_db()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["current_arcane_power"], 3)
        self.assertEqual(self.character.current_arcane_power, 3)
        self.assertTrue(any(partial["target"] == "sheetDamagePanel" for partial in payload["partials"]))

    def test_process_learning_submission_learns_paid_magic_spell(self):
        CharacterSchool.objects.create(character=self.character, school=self.arcane_school, level=2)
        learned_free_spells = []
        for index in range(4):
            learned_free_spells.append(
                CharacterSpell.objects.create(
                    character=self.character,
                    spell=Spell.objects.create(
                        name=f"Freizauber {index}",
                        slug=f"freizauber_{index}",
                        school=self.arcane_school,
                        level=1 if index < 2 else 2,
                        kp_cost=1,
                    ),
                    source_kind=CharacterSpell.SourceKind.ARCANE_FREE,
                )
            )
        paid_spell = Spell.objects.create(
            name="Feuerlanze",
            slug="feuerlanze",
            school=self.arcane_school,
            level=2,
            kp_cost=3,
        )

        level, message = process_learning_submission(
            self.character,
            {f"learn_magic_spell_{paid_spell.id}": "1"},
        )

        self.character.refresh_from_db()
        self.assertEqual(level, "success", message)
        self.assertTrue(CharacterSpell.objects.filter(character=self.character, spell=paid_spell, source_kind=CharacterSpell.SourceKind.ARCANE_EXTRA).exists())
        self.assertEqual(self.character.current_experience, 48)
