from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.engine.character_creation_engine import CharacterCreationEngine
from charsheet.models import CharacterCreationDraft, Race, Trait, VampireTrait


class CharacterCreationVampireSelectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="vampire-creation-selection-test",
            password="test-password",
        )
        self.race = Race.objects.create(
            name="Vampire selection test race",
            phase_3_points=20,
        )
        Trait.objects.update_or_create(
            slug="adv_vampire",
            defaults={
                "name": "Vampir",
                "trait_type": Trait.TraitType.ADV,
                "min_level": 1,
                "max_level": 1,
                "points_per_level": 15,
            },
        )
        self.ordinary_disadvantage = Trait.objects.create(
            slug="vampire-selection-test-disadvantage",
            name="Vampire selection test disadvantage",
            trait_type=Trait.TraitType.DIS,
            min_level=1,
            max_level=1,
            points_per_level=20,
        )
        self.vampire_disadvantage = VampireTrait.objects.create(
            slug="automatic-vampire-disadvantage",
            name="Automatic vampire disadvantage",
            trait_type=VampireTrait.TraitType.DISADVANTAGE,
            is_active=True,
        )
        self.vampire_advantage = VampireTrait.objects.create(
            slug="automatic-vampire-advantage",
            name="Automatic vampire advantage",
            trait_type=VampireTrait.TraitType.ADVANTAGE,
            is_active=True,
        )

    def _engine(self, selected_traits=None):
        draft = CharacterCreationDraft.objects.create(
            owner=self.user,
            race=self.race,
            current_phase=4,
            state={
                "phase_3": {
                    "disadvantages": {self.ordinary_disadvantage.slug: 1},
                },
                "phase_4": {
                    "advantages": {"adv_vampire": 1},
                    "vampire": {"traits": selected_traits or {}},
                },
            },
        )
        return CharacterCreationEngine(draft)

    def test_active_traits_are_automatically_granted(self):
        engine = self._engine()

        self.assertEqual(
            engine.phase_4_vampire()["traits"],
            {
                self.vampire_advantage.slug: {},
                self.vampire_disadvantage.slug: {},
            },
        )

    def test_automatic_traits_do_not_change_creation_points(self):
        engine = self._engine()

        self.assertEqual(engine.vampire_creation_cost(), 0)
        self.assertEqual(engine.sum_phase_4_advantages_cost(), 15)
        self.assertEqual(engine.vampire_weakness_refund(), 0)
        self.assertTrue(engine.vampire_configuration_is_valid())
