"""Character-owned models and draft state."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ..constants import QUALITY_CHOICES, QUALITY_COMMON
from .core import Attribute, Language, Race, Skill, Trait


class Character(models.Model):
    """A persisted player character with progression and status data."""

    class Gender(models.TextChoices):
        M = "männlich", "Männlich"
        W = "weiblich", "Weiblich"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    race = models.ForeignKey(Race, on_delete=models.PROTECT)
    gender = models.CharField(max_length=15, choices=Gender, null=True, blank=True)
    age = models.PositiveIntegerField(default=20, null=True, blank=True)
    height = models.IntegerField(default=170)
    skin_color = models.CharField(max_length=25, null=True, blank=True)
    hair_color = models.CharField(max_length=25, null=True, blank=True)
    eye_color = models.CharField(max_length=25, null=True, blank=True)
    country_of_origin = models.CharField(max_length=25, null=True, blank=True)
    weight = models.IntegerField(default=60, null=True, blank=True)
    religion = models.CharField(max_length=25, null=True, blank=True)
    appearance = models.TextField(max_length=100, null=True, blank=True)

    money = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    overall_experience = models.PositiveIntegerField(default=0)
    current_experience = models.PositiveIntegerField(default=0)

    current_damage = models.PositiveIntegerField(default=0)
    is_archived = models.BooleanField(default=False)
    last_opened_at = models.DateTimeField(null=True, blank=True)

    personal_fame_point = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(10)])
    personal_fame_rank = models.PositiveIntegerField(default=0)
    sacrifice_rank = models.PositiveIntegerField(default=0)
    artefact_rank = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="uniq_character_owner_name")
        ]

    def __str__(self):
        return f"{self.name} ({self.race.name})"

    @property
    def engine(self):
        """Return the cached calculation engine for this character instance."""
        return self.get_engine()

    def get_engine(self, *, refresh: bool = False):
        """Return a reusable engine instance for repeated calculations."""
        cache_key = "_character_engine"
        if refresh or cache_key not in self.__dict__:
            from ..engine import CharacterEngine

            self.__dict__[cache_key] = CharacterEngine(self)
        return self.__dict__[cache_key]


class CharacterDiaryEntry(models.Model):
    """One persisted diary segment for a character's parchment-roll journal."""

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="diary_entries",
    )
    order_index = models.PositiveIntegerField(default=0)
    text = models.TextField(blank=True, default="")
    entry_date = models.DateField(null=True, blank=True)
    is_fixed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["character", "order_index", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "order_index"],
                name="uniq_character_diary_entry_order",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character.name} diary #{self.order_index + 1}"

    @property
    def is_empty(self) -> bool:
        """Return whether the entry currently contains no visible text."""
        return not (self.text or "").strip()


class CharacterAttribute(models.Model):
    """Stores the purchased base value of one attribute for a character."""

    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    base_value = models.IntegerField()

    class Meta:
        ordering = ["character", "attribute"]
        constraints = [
            models.UniqueConstraint(fields=["character", "attribute"], name="uniq_character_attribute")
        ]

    def __str__(self):
        return f"{self.character} - {self.attribute}: {self.base_value}"


class CharacterSkill(models.Model):
    """Stores the learned rating of one skill for a character."""

    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    specification = models.CharField(max_length=25, blank=True, default="*")

    class Meta:
        ordering = ["character", "skill"]
        constraints = [
            models.UniqueConstraint(fields=["character", "skill"], name="uniq_character_skill")
        ]

    def __str__(self):
        return f"{self.character} learned {self.skill}: {self.level}"


class CharacterItem(models.Model):
    """Ownership state of one item for one character."""

    item = models.ForeignKey("Item", on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    equip_locked = models.BooleanField(default=False)
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default=QUALITY_COMMON)
    runes = models.ManyToManyField("Rune", blank=True, related_name="character_items")

    def clean(self):
        """Enforce stackability and equipment consistency."""
        super().clean()
        if not self.item.stackable and self.amount != 1:
            raise ValidationError({"amount": "Item is flagged non stackable. amount must be 1"})
        if self.item.stackable and self.equipped:
            raise ValidationError({"equipped": "Stackable Items can't be equipped"})
        if self.equip_locked and not self.equipped:
            raise ValidationError({"equip_locked": "Locked equipment must remain equipped."})

    def __str__(self):
        return f"{self.owner} owns {self.item}"


class CharacterTrait(models.Model):
    """Purchased trait level of a character."""

    trait = models.ForeignKey(Trait, on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    trait_level = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "trait"], name="unique_trait_per_character")
        ]

    def clean(self):
        """Validate the chosen trait level against its allowed range."""
        super().clean()
        if self.trait_level > self.trait.max_level:
            raise ValidationError({"trait_level": "You can't purchase more levels of a trait than max level"})
        if self.trait_level < self.trait.min_level:
            raise ValidationError({"trait_level": f"Level must be at least {self.trait.min_level}."})

    def __str__(self):
        return f"{self.owner}: {self.trait} ({self.trait_level})"


class CharacterLanguage(models.Model):
    """Language proficiency entry for one character."""

    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    owner = models.ForeignKey(Character, on_delete=models.PROTECT)
    levels = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    can_write = models.BooleanField(default=False)
    is_mother_tongue = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "language"], name="unique_language_per_charater")
        ]

    def clean(self):
        """Validate level bounds and mother-tongue requirements."""
        super().clean()
        if self.levels > self.language.max_level:
            raise ValidationError({"levels": "levels can't be greater dan max_level"})
        if self.is_mother_tongue and self.levels != self.language.max_level:
            raise ValidationError({"levels": "Levels of mother tongue must be max_ level"})

    def __str__(self):
        suffix = " (Mother tongue)" if self.is_mother_tongue else ""
        return f"{self.owner} speaks {self.language.name}{suffix}"


class CharacterCreationDraft(models.Model):
    """Persisted in-progress state for the character creation flow."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="character_drafts",
    )
    race = models.ForeignKey(Race, on_delete=models.CASCADE)
    current_phase = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(4)])
    state = models.JSONField(default=dict, blank=True)
