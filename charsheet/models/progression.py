"""School, specialization, and progression models."""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ..constants import SCHOOL_TYPE_CHOICES


class SchoolType(models.Model):
    """High-level classification for schools used by progression rules."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, choices=SCHOOL_TYPE_CHOICES)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class School(models.Model):
    """A combat school or similar progression track."""

    name = models.CharField(max_length=100, unique=True)
    type = models.ForeignKey(SchoolType, on_delete=models.PROTECT)
    panel_symbol = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Optional short symbol shown in spell and school panels, for example a rune or glyph.",
    )
    max_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Max. Stufe",
        help_text="Maximale lernbare Stufe. Überschreibt den automatisch berechneten Wert aus den Techniken.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["type__name", "name"]

    def __str__(self):
        return self.name


class CharacterSchool(models.Model):
    """The learned level of a specific school for one character."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="schools")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="character_entries")
    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["character", "school__type__name", "school__name"]
        constraints = [
            models.UniqueConstraint(fields=["character", "school"], name="uniq_character_school")
        ]

    def __str__(self) -> str:
        return f"{self.character.name} - {self.school.name} (L{self.level})"


class SchoolPath(models.Model):
    """A specialization path that belongs to one school."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="paths")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["school__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_school_path_name")
        ]

    def __str__(self) -> str:
        return f"{self.school.name}: {self.name}"


class CharacterSchoolPath(models.Model):
    """The selected specialization path of a character within a school."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="selected_school_paths")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="character_path_choices")
    path = models.ForeignKey(SchoolPath, on_delete=models.PROTECT, related_name="character_choices")

    class Meta:
        ordering = ["character", "school__type__name", "school__name"]
        constraints = [
            models.UniqueConstraint(fields=["character", "school"], name="uniq_character_school_path")
        ]

    def clean(self):
        """Validate school ownership and that the character knows the school."""
        super().clean()
        if self.path_id and self.school_id and self.path.school_id != self.school_id:
            raise ValidationError({"path": "The selected path must belong to the selected school."})
        if self.character_id and self.school_id and not CharacterSchool.objects.filter(
            character_id=self.character_id,
            school_id=self.school_id,
        ).exists():
            raise ValidationError({"school": "A character can only choose a path for a learned school."})

    def __str__(self) -> str:
        return f"{self.character.name} - {self.school.name}: {self.path.name}"


class Specialization(models.Model):
    """A generic school-bound specialization definition."""

    class SupportLevel(models.TextChoices):
        """Describe how fully the engine can resolve a specialization's rules."""

        COMPUTED = "computed", "Automated"
        STRUCTURED = "structured", "Partially Automated"
        DESCRIPTIVE = "descriptive", "Manual (Rule Text Only)"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="specializations")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    support_level = models.CharField(
        max_length=20,
        choices=SupportLevel.choices,
        default=SupportLevel.STRUCTURED,
        help_text="How far the engine can resolve this specialization beyond basic status tracking.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["school__name", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "slug"], name="uniq_specialization_school_slug"),
        ]

    def __str__(self) -> str:
        return f"{self.school.name}: {self.name}"


class CharacterSpecialization(models.Model):
    """A specialization selected by a character for one learned school."""

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="learned_specializations",
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        related_name="character_specializations",
    )
    source_technique = models.ForeignKey(
        "Technique",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_specializations",
    )
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = [
            "character",
            "specialization__school__name",
            "specialization__sort_order",
            "specialization__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "specialization"],
                name="uniq_character_specialization",
            ),
        ]

    def clean(self):
        """Validate school ownership and an optional source-technique school match."""
        super().clean()
        if (
            self.character_id
            and self.specialization_id
            and not CharacterSchool.objects.filter(
                character_id=self.character_id,
                school_id=self.specialization.school_id,
            ).exists()
        ):
            raise ValidationError(
                {"specialization": "A character can only choose specializations from learned schools."}
            )
        if (
            self.source_technique_id
            and self.specialization_id
            and self.source_technique.school_id != self.specialization.school_id
        ):
            raise ValidationError(
                {"source_technique": "The source technique must belong to the same school as the specialization."}
            )

    def __str__(self) -> str:
        return f"{self.character.name} - {self.specialization.school.name}: {self.specialization.name}"


class CharacterWeaponMastery(models.Model):
    """One mastered concrete weapon choice of a character's Waffenmeister school."""

    class FirstBonusKind(models.TextChoices):
        MANEUVER = "maneuver", "Manoever zuerst"
        DAMAGE = "damage", "Schaden zuerst"

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="weapon_masteries",
    )
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="character_weapon_masteries",
    )
    weapon_item = models.ForeignKey(
        "charsheet.Item",
        on_delete=models.PROTECT,
        related_name="character_weapon_masteries",
    )
    pick_order = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="The order in which this concrete weapon was chosen on school levels 1-10.",
    )
    first_bonus_kind = models.CharField(
        max_length=20,
        choices=FirstBonusKind.choices,
        default=FirstBonusKind.MANEUVER,
        help_text="Whether the first granted point on this weapon went to maneuver or damage.",
    )
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["character", "school__name", "pick_order", "weapon_item__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "school", "pick_order"],
                name="uniq_character_weapon_mastery_pick_order",
            ),
            models.UniqueConstraint(
                fields=["character", "school", "weapon_item"],
                name="uniq_character_weapon_mastery_weapon",
            ),
        ]

    def clean(self):
        """Validate school ownership and weapon-specific item selection."""
        super().clean()
        if self.weapon_item_id and self.weapon_item.item_type != self.weapon_item.ItemType.WEAPON:
            raise ValidationError({"weapon_item": "Weapon mastery entries must point at weapon items."})
        if (
            self.character_id
            and self.school_id
            and not CharacterSchool.objects.filter(character_id=self.character_id, school_id=self.school_id).exists()
        ):
            raise ValidationError({"school": "A character can only track weapon masteries for learned schools."})

    def progression_steps(self, school_level: int) -> int:
        """Return how many school-level grants this mastery currently received."""
        if school_level < self.pick_order:
            return 0
        return school_level - self.pick_order + 1

    def maneuver_damage_bonus(self, school_level: int) -> tuple[int, int]:
        """Resolve current maneuver/damage bonuses from school level and starting side."""
        steps = self.progression_steps(school_level)
        first_half = (steps + 1) // 2
        second_half = steps // 2
        if self.first_bonus_kind == self.FirstBonusKind.MANEUVER:
            return first_half, second_half
        return second_half, first_half

    def quality_step_bonus(self) -> int:
        """All mastered weapon types shift crafting quality up by one category."""
        return 1

    def __str__(self) -> str:
        return f"{self.character.name} - {self.school.name}: #{self.pick_order} {self.weapon_item.name}"


class CharacterWeaponMasteryArcana(models.Model):
    """Persistent rune or bonus-capacity progress for Waffenmeister, also beyond level 10."""

    class ArcanaKind(models.TextChoices):
        RUNE = "rune", "Rune"
        BONUS_CAPACITY = "bonus_capacity", "Bonuskapazitaet"

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="weapon_mastery_arcana_entries",
    )
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="character_weapon_mastery_arcana_entries",
    )
    kind = models.CharField(max_length=30, choices=ArcanaKind.choices)
    rune = models.ForeignKey(
        "charsheet.Rune",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="weapon_mastery_arcana_entries",
    )
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["character", "school__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "school", "rune"],
                condition=models.Q(rune__isnull=False),
                name="uniq_character_weapon_mastery_arcana_rune",
            ),
        ]

    def clean(self):
        """Keep kind/rune combinations and school ownership coherent."""
        super().clean()
        if self.kind == self.ArcanaKind.RUNE and self.rune_id is None:
            raise ValidationError({"rune": "Rune arcana entries must reference a rune."})
        if self.kind != self.ArcanaKind.RUNE and self.rune_id is not None:
            raise ValidationError({"rune": "Only rune arcana entries may reference a rune."})
        if (
            self.character_id
            and self.school_id
            and not CharacterSchool.objects.filter(character_id=self.character_id, school_id=self.school_id).exists()
        ):
            raise ValidationError({"school": "A character can only track weapon arcana for learned schools."})

    def __str__(self) -> str:
        if self.kind == self.ArcanaKind.RUNE and self.rune_id:
            return f"{self.character.name} - {self.school.name}: Rune {self.rune.name}"
        return f"{self.character.name} - {self.school.name}: Bonuskapazitaet"


class ProgressionRule(models.Model):
    """Rule-based grants that unlock from school type and minimum level."""

    school_type = models.ForeignKey(SchoolType, on_delete=models.CASCADE)
    min_level = models.PositiveBigIntegerField(default=1)
    grant_kind = models.CharField(
        max_length=30,
        choices=[
            ("technique_choice", "Technique Choice"),
            ("spell_choice", "Spell Choice"),
            ("aspect_access", "Aspect Access"),
            ("aspect_spell", "Aspect Spell"),
        ],
    )
    amount = models.PositiveBigIntegerField(default=1)
    params = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["school_type", "min_level", "grant_kind", "id"]

    def __str__(self):
        return f"{self.school_type} level {self.min_level}+ grants {self.amount} {self.grant_kind}"
