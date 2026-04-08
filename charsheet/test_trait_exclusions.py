"""Regression tests for trait exclusion rules."""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from charsheet.engine.character_creation_engine import CharacterCreationEngine
from charsheet.learning import process_learning_submission
from charsheet.models import Character, CharacterTrait, Race, Trait, TraitExclusion


class TraitExclusionTests(TestCase):
    """Verify mutually exclusive trait data is enforced consistently."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="trait-user", password="secret")
        self.race = Race.objects.create(name="Human")
        self.character = Character.objects.create(
            owner=self.user,
            name="Lyra",
            race=self.race,
            current_experience=20,
        )

    def test_trait_exclusion_blocks_reverse_duplicate(self):
        """Reverse pairs should be rejected so one exclusion exists only once."""
        left = Trait.objects.create(
            name="Night Vision",
            slug="night_vision",
            trait_type=Trait.TraitType.ADV,
            description="See better at night.",
        )
        right = Trait.objects.create(
            name="Day Blindness",
            slug="day_blindness",
            trait_type=Trait.TraitType.ADV,
            description="Struggles in daylight.",
        )
        TraitExclusion.objects.create(trait=left, excluded_trait=right)

        pair = TraitExclusion(trait=right, excluded_trait=left)
        with self.assertRaises(ValidationError):
            pair.full_clean()

    def test_learning_submission_rejects_mutually_exclusive_advantages(self):
        """EP learning should refuse a trait that excludes an already owned trait."""
        first = Trait.objects.create(
            name="Night Vision",
            slug="night_vision",
            trait_type=Trait.TraitType.ADV,
            description="See better at night.",
            points_per_level=3,
        )
        second = Trait.objects.create(
            name="Sun Blessed",
            slug="sun_blessed",
            trait_type=Trait.TraitType.ADV,
            description="Empowered by sunlight.",
            points_per_level=3,
        )
        TraitExclusion.objects.create(trait=first, excluded_trait=second)
        CharacterTrait.objects.create(owner=self.character, trait=first, trait_level=1)

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_trait_add_{second.slug}": "1",
            },
        )

        self.assertEqual(level, "error")
        self.assertIn("Night Vision", message)
        self.assertIn("Sun Blessed", message)
        self.assertFalse(self.character.charactertrait_set.filter(trait=second).exists())

    def test_creation_engine_rejects_mutually_exclusive_disadvantages(self):
        """Creation validation should reject incompatible disadvantage picks."""
        first = Trait.objects.create(
            name="Blind",
            slug="blind",
            trait_type=Trait.TraitType.DIS,
            description="Cannot see.",
            points_per_level=5,
        )
        second = Trait.objects.create(
            name="One-Eyed",
            slug="one_eyed",
            trait_type=Trait.TraitType.DIS,
            description="Only one functioning eye.",
            points_per_level=2,
        )
        TraitExclusion.objects.create(trait=first, excluded_trait=second)
        draft = SimpleNamespace(
            race=self.race,
            state={"phase_3": {"disadvantages": {first.slug: 1, second.slug: 1}}},
        )

        engine = CharacterCreationEngine(draft)

        self.assertFalse(engine.validate_phase_3())

    def test_cross_type_exclusion_is_allowed_on_model_level(self):
        """Advantages and disadvantages may exclude each other directly."""
        advantage = Trait.objects.create(
            name="Fearless",
            slug="fearless",
            trait_type=Trait.TraitType.ADV,
            description="Unafraid.",
        )
        disadvantage = Trait.objects.create(
            name="Fearful",
            slug="fearful",
            trait_type=Trait.TraitType.DIS,
            description="Easily frightened.",
        )

        pair = TraitExclusion(trait=advantage, excluded_trait=disadvantage)
        pair.full_clean()

    def test_creation_engine_rejects_cross_type_exclusions(self):
        """Creation validation should reject advantage/disadvantage exclusion pairs."""
        advantage = Trait.objects.create(
            name="Fearless",
            slug="fearless",
            trait_type=Trait.TraitType.ADV,
            description="Unafraid.",
            points_per_level=2,
        )
        disadvantage = Trait.objects.create(
            name="Fearful",
            slug="fearful",
            trait_type=Trait.TraitType.DIS,
            description="Easily frightened.",
            points_per_level=2,
        )
        TraitExclusion.objects.create(trait=advantage, excluded_trait=disadvantage)
        draft = SimpleNamespace(
            race=self.race,
            state={
                "phase_3": {"disadvantages": {disadvantage.slug: 1}},
                "phase_4": {"advantages": {advantage.slug: 1}},
            },
        )

        engine = CharacterCreationEngine(draft)

        self.assertFalse(engine.validate_phase_4())

    def test_learning_submission_rejects_cross_type_exclusions(self):
        """EP learning should reject an advantage that excludes an owned disadvantage."""
        advantage = Trait.objects.create(
            name="Fearless",
            slug="fearless",
            trait_type=Trait.TraitType.ADV,
            description="Unafraid.",
            points_per_level=2,
        )
        disadvantage = Trait.objects.create(
            name="Fearful",
            slug="fearful",
            trait_type=Trait.TraitType.DIS,
            description="Easily frightened.",
            points_per_level=2,
        )
        TraitExclusion.objects.create(trait=advantage, excluded_trait=disadvantage)
        CharacterTrait.objects.create(owner=self.character, trait=disadvantage, trait_level=1)

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_trait_add_{advantage.slug}": "1",
            },
        )

        self.assertEqual(level, "error")
        self.assertIn("Fearless", message)
        self.assertIn("Fearful", message)
