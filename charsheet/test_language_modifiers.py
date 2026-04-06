"""Regression tests for language-targeted modifiers."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import Character, CharacterLanguage, Language, Race, Trait, TraitSemanticEffect
from charsheet.modifiers import ModifierOperator, TargetDomain


class LanguageModifierTests(TestCase):
    """Ensure language modifiers affect effective language levels."""

    def test_foreign_language_modifier_does_not_reduce_mother_tongue(self):
        user = get_user_model().objects.create_user(username="linguist", password="secret")
        race = Race.objects.create(name="Mensch")
        character = Character.objects.create(owner=user, name="Leya", race=race)
        mother = Language.objects.create(name="Muttersprache", slug="mother", max_level=3)
        foreign = Language.objects.create(name="Albisch", slug="albisch", max_level=3)
        CharacterLanguage.objects.create(owner=character, language=mother, levels=3, is_mother_tongue=True)
        CharacterLanguage.objects.create(owner=character, language=foreign, levels=3, is_mother_tongue=False)

        trait = Trait.objects.create(
            name="Unvermoegen Sprachen",
            slug="unvermoegen_sprachen",
            trait_type=Trait.TraitType.DIS,
            description="",
        )
        TraitSemanticEffect.objects.create(
            trait=trait,
            target_domain=TargetDomain.LANGUAGE,
            target_key="foreign_languages",
            operator=ModifierOperator.FLAT_SUB,
            value="3",
        )
        character.charactertrait_set.create(trait=trait, trait_level=1)

        engine = CharacterEngine(character)

        self.assertEqual(engine.resolve_language_level("mother"), 3)
        self.assertEqual(engine.resolve_language_level("albisch"), 0)
