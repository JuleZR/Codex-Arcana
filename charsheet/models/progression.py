"""School, specialization, and progression models."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction

from ..constants import SCHOOL_ARCANE, SCHOOL_TYPE_CHOICES
from .semantic_effects import SemanticEffectFields


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
    opposite = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opposed_by",
        limit_choices_to={"type__slug": SCHOOL_ARCANE},
        help_text="Optional opposite school, primarily for opposed elemental magic schools.",
    )
    panel_symbol = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Optional short symbol shown in spell and school panels, for example a rune or glyph.",
    )
    symbol_image = models.ImageField(
        upload_to="schools/",
        blank=True,
        null=True,
        help_text="Optionales Symbolbild fuer diese Schule. Wird im Charsheet bevorzugt vor dem Textsymbol angezeigt.",
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

    def clean(self):
        super().clean()
        if self.opposite_id and self.opposite_id == self.id:
            raise ValidationError({"opposite": "A school cannot oppose itself."})
        if self.opposite_id:
            if self.type_id and self.type.slug != SCHOOL_ARCANE:
                raise ValidationError({"opposite": "Only magic schools can define an opposite school."})
            if self.opposite.type.slug != SCHOOL_ARCANE:
                raise ValidationError({"opposite": "Only magic schools can be selected as opposite schools."})

    def __str__(self):
        return self.name


class SchoolSemanticEffect(SemanticEffectFields):
    """Persisted semantic effect attached directly to one school."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="semantic_effects")

    class Meta:
        ordering = ["school", "sort_order", "id"]

    def __str__(self):
        return f"{self.school.name}: {self.target_domain}/{self.target_key} ({self.operator})"

    def semantic_source_type(self) -> str:
        return "school"

    def semantic_source_id(self) -> str:
        return str(self.school_id)

    def semantic_source_label(self) -> str:
        return str(self.school)

    def semantic_effect_key_prefix(self) -> str:
        return "school_effect"


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
    additional_progression = models.BooleanField(default=False)
    additional_only = models.BooleanField(default=False)
    required_school_level = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1)]
    )
    completion_purchase = models.BooleanField(default=False)
    ep_cost = models.PositiveSmallIntegerField(default=20)
    arcane_power_increase = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["school__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"], name="uniq_school_path_name"
            )
        ]

    def __str__(self) -> str:
        return f"{self.school.name}: {self.name}"


class CareerPathTechnique(models.Model):
    """An ordered career step reusing normal technique prerequisites."""

    path = models.ForeignKey(
        SchoolPath, on_delete=models.CASCADE, related_name="career_steps"
    )
    technique = models.OneToOneField(
        "Technique", on_delete=models.PROTECT, related_name="career_step"
    )
    order = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    effective_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ["path", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["path", "order"], name="uniq_career_step_order"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_level__lte=10),
                name="career_level_at_most_ten",
            ),
        ]

    def clean(self):
        super().clean()
        if self.path_id and self.technique_id:
            if self.path.school_id != self.technique.school_id:
                raise ValidationError(
                    {"technique": "Die Technik muss zur Basisschule gehören."}
                )
            if (
                self.technique.path_id
                and self.technique.path_id != self.path_id
            ):
                raise ValidationError(
                    {
                        "technique": "Technik gehört zu einer anderen Laufbahn."
                    }
                )
            others = (
                type(self)
                .objects.filter(path_id=self.path_id)
                .exclude(pk=self.pk)
            )
            if (
                others.filter(
                    order__lt=self.order,
                    effective_level__gt=self.effective_level,
                ).exists()
                or others.filter(
                    order__gt=self.order,
                    effective_level__lt=self.effective_level,
                ).exists()
            ):
                raise ValidationError(
                    {
                        "effective_level": "Stufen müssen aufsteigend sein."
                    }
                )

    def __str__(self):
        return (
            f"{self.path}: {self.technique.name} "
            f"(Stufe {self.effective_level})"
        )


class CharacterCareerPathPurchase(models.Model):
    """A null step records the final mastery purchase."""

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="career_path_purchases",
    )
    path = models.ForeignKey(
        SchoolPath, on_delete=models.PROTECT, related_name="purchases"
    )
    step = models.ForeignKey(
        CareerPathTechnique, on_delete=models.PROTECT, null=True, blank=True
    )
    paid_ep = models.PositiveSmallIntegerField(default=20)
    arcane_power_increase = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character", "step"], name="uniq_character_career_step"
            ),
            models.UniqueConstraint(
                fields=["character", "path"],
                condition=models.Q(step__isnull=True),
                name="uniq_character_career_completion",
            ),
        ]

    def clean(self):
        super().clean()
        if self.step_id and self.step.path_id != self.path_id:
            raise ValidationError(
                {"step": "Die Technik muss zur Laufbahn gehören."}
            )


class CharacterSchoolPath(models.Model):
    """The selected specialization path of a character within a school."""

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="selected_school_paths",
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="character_path_choices"
    )
    path = models.ForeignKey(
        SchoolPath, on_delete=models.PROTECT, related_name="character_choices"
    )

    class Meta:
        ordering = ["character", "school__type__name", "school__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "school"],
                name="uniq_character_school_path",
            )
        ]

    def clean(self):
        """Validate school ownership and that the character knows the school."""
        super().clean()
        if self.path_id and self.path.additional_only:
            raise ValidationError({"path": "Diese Laufbahn wird als zusätzlicher Fortschritt gelernt."})
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
    allow_multiple = models.BooleanField(default=False)
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

    def clean(self):
        super().clean()
        if self.pk and not self.allow_multiple:
            duplicates = (
                self.character_specializations.values("character_id")
                .annotate(
                    count=models.Count("pk"),
                )
                .filter(count__gt=1)
            )
            if duplicates.exists():
                raise ValidationError(
                    {
                        "allow_multiple": (
                            "Existing instances require multiple selection."
                        ),
                    }
                )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                type(self).objects.select_for_update().get(pk=self.pk)
            self.clean()
            return super().save(*args, **kwargs)


class SpecializationSemanticEffect(SemanticEffectFields):
    """Persisted semantic effect attached directly to one specialization."""

    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE,
        related_name="semantic_effects",
    )
    target_choice_definition = models.ForeignKey(
        "SpecializationChoiceDefinition", on_delete=models.PROTECT,
        null=True, blank=True, related_name="semantic_effects",
    )

    def clean(self):
        super().clean()
        if (
            self.target_choice_definition_id
            and self.target_choice_definition.specialization_id
            != self.specialization_id
        ):
            raise ValidationError(
                {
                    "target_choice_definition": (
                        "Choice must belong to this specialization."
                    ),
                }
            )

    def to_modifier(self):
        modifier = super().to_modifier()
        if self.target_choice_definition_id:
            modifier.metadata["choice_binding"] = {
                "kind": "specialization_choice_definition",
                "id": self.target_choice_definition_id,
            }
        return modifier

    class Meta:
        ordering = ["specialization", "sort_order", "id"]

    def __str__(self) -> str:
        return (
            f"{self.specialization}: "
            f"{self.target_domain}/{self.target_key} ({self.operator})"
        )

    def semantic_source_type(self) -> str:
        return "specialization"

    def semantic_source_id(self) -> str:
        return str(self.specialization_id)

    def semantic_source_label(self) -> str:
        return str(self.specialization)

    def semantic_effect_key_prefix(self) -> str:
        return "specialization_effect"


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
    source_choice = models.OneToOneField(
        "CharacterTechniqueChoice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="specialization_instance",
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

    def clean(self):
        """Validate school ownership and an optional source-technique school match."""
        super().clean()
        if (
            self.character_id
            and self.specialization_id
            and not self.specialization.allow_multiple
            and type(self)
            .objects.filter(
                character_id=self.character_id,
                specialization_id=self.specialization_id,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {
                    "specialization": (
                        "This specialization has already been chosen."
                    ),
                }
            )
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

    def save(self, *args, **kwargs):
        Character = self._meta.get_field("character").remote_field.model
        with transaction.atomic():
            Character.objects.select_for_update().get(pk=self.character_id)
            self.specialization = (
                Specialization.objects.select_for_update().get(
                    pk=self.specialization_id
                )
            )
            self.full_clean()
            return super().save(*args, **kwargs)

    def choices_complete(self):
        if not self.pk:
            return not self.specialization.choice_definitions.filter(
                is_active=True, is_required=True
            ).exists()
        for definition in self.specialization.choice_definitions.filter(
            is_active=True
        ):
            choices = list(self.choices.filter(definition=definition))
            if len(choices) > definition.max_choices:
                return False
            if (
                definition.is_required
                and len(choices) < definition.min_choices
            ):
                return False
            try:
                for choice in choices:
                    choice.full_clean()
            except ValidationError:
                return False
        return True

    def __str__(self) -> str:
        return f"{self.character.name} - {self.specialization.school.name}: {self.specialization.name}"


class CharacterWeaponMastery(models.Model):
    """One mastered weapon type choice of a character's Waffenmeister school."""

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
    weapon_type = models.ForeignKey(
        "charsheet.WeaponType",
        on_delete=models.PROTECT,
        related_name="character_masteries",
        null=True,
        blank=True,
        help_text="Der regeltechnische Waffentyp, auf den diese Meisterschaft wirkt.",
    )
    weapon_item = models.ForeignKey(
        "charsheet.Item",
        on_delete=models.PROTECT,
        related_name="character_weapon_masteries",
        null=True,
        blank=True,
    )
    pick_order = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="The order in which this concrete weapon was chosen on school levels 1-10.",
    )
    first_bonus_kind = models.CharField(
        max_length=20,
        choices=FirstBonusKind.choices,
        default=FirstBonusKind.MANEUVER,
        help_text="Whether the first granted point on this weapon went to maneuver or damage.",
    )
    purchased_steps = models.PositiveSmallIntegerField(default=0)
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["character", "school__name", "pick_order", "weapon_type__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "school", "pick_order"],
                name="uniq_character_weapon_mastery_pick_order",
            ),
            models.UniqueConstraint(
                fields=["character", "school", "weapon_type"],
                name="uniq_character_weapon_mastery_weapon_type",
            ),
        ]

    def clean(self):
        """Validate school ownership and weapon-type specific item selection."""
        super().clean()
        normal_steps = max(0, 11 - self.pick_order)
        if normal_steps + self.purchased_steps > 10:
            raise ValidationError({
                "purchased_steps": "Weapon bonuses cannot exceed +5/+5.",
            })
        if (
            self.weapon_item_id
            and not self.weapon_item.item_type.supports_weapon_mastery
        ):
            raise ValidationError({"weapon_item": "Weapon mastery entries must point at weapon items."})
        if self.weapon_type_id is None and not self.weapon_item_id:
            raise ValidationError({"weapon_type": "Weapon mastery entries need a concrete weapon type."})
        if (
            self.character_id
            and self.school_id
            and not CharacterSchool.objects.filter(character_id=self.character_id, school_id=self.school_id).exists()
        ):
            raise ValidationError({"school": "A character can only track weapon masteries for learned schools."})

    def effective_weapon_type(self) -> str:
        """Return the stored weapon type, falling back to one linked legacy item when needed."""
        if self.weapon_type_id:
            return str(self.weapon_type.slug)
        weapon_stats = getattr(self.weapon_item, "weaponstats", None)
        if weapon_stats and weapon_stats.weapon_type_id:
            return str(weapon_stats.weapon_type.slug)
        return ""

    def weapon_type_label(self) -> str:
        """Return the display label for this mastery's weapon type."""
        if self.weapon_type_id:
            return str(self.weapon_type.name)
        weapon_stats = getattr(self.weapon_item, "weaponstats", None)
        if weapon_stats and weapon_stats.weapon_type_id:
            return str(weapon_stats.weapon_type.name)
        if self.weapon_item_id:
            return self.weapon_item.name
        return "Nicht festgelegt"

    def progression_steps(self, school_level: int) -> int:
        """Return how many school-level grants this mastery currently received."""
        normal_steps = max(0, min(school_level, 10) - self.pick_order + 1)
        advanced_steps = self.purchased_steps if school_level >= 10 else 0
        return min(10, normal_steps + advanced_steps)

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
        return f"{self.character.name} - {self.school.name}: #{self.pick_order} {self.weapon_type_label()}"


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
    paid_ep = models.PositiveSmallIntegerField(default=0)
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
            ("advanced_simple", "Zusätzliche einfache Spezialisierung"),
            ("advanced_bonus", "Bonus-Spezialisierung steigern"),
        ],
    )
    amount = models.PositiveBigIntegerField(default=1)
    params = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["school_type", "min_level", "grant_kind", "id"]

    def __str__(self):
        return f"{self.school_type} level {self.min_level}+ grants {self.amount} {self.grant_kind}"


class CharacterAdvancedBonus(models.Model):
    """Paid progress for exactly one target of a configured technique."""

    character = models.ForeignKey(
        "Character", on_delete=models.CASCADE, related_name="advanced_bonuses",
    )
    technique = models.ForeignKey("Technique", on_delete=models.PROTECT)
    target = models.CharField(max_length=255)
    label = models.CharField(max_length=255)
    value = models.PositiveSmallIntegerField()
    base_value = models.PositiveSmallIntegerField(default=0)
    purchases = models.JSONField(default=list)
    configuration = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character", "technique", "target"],
                name="uniq_character_advanced_bonus_target",
            ),
        ]
