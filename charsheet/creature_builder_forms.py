"""Forms for the creature template workshop, using existing model relations."""

from django import forms
from django.forms import formset_factory, inlineformset_factory

from charsheet.creature_damage import match_damage_level, validate_formula
from charsheet.creature_abilities import ability_catalog
from charsheet.engine.creature_power import (
    ATTRIBUTE_CODES,
    CATEGORIES,
    CATEGORY_TYPES,
)
from charsheet.models import (
    Attribute,
    Creature,
    CreatureAttack,
    CreatureAttribute,
    CreatureLanguage,
    CreatureSkill,
    CreatureType,
)


class CreatureBuildForm(forms.ModelForm):
    name = forms.CharField(label="Name", max_length=100)
    vw_bonus = forms.IntegerField(
        label="Bonus/Malus zum VW",
        initial=0,
        required=False,
    )
    sr_bonus = forms.IntegerField(
        label="Bonus/Malus zur SR",
        initial=0,
        required=False,
    )
    gw_bonus = forms.IntegerField(
        label="Bonus/Malus zum GW",
        initial=0,
        required=False,
    )
    initiative_bonus = forms.IntegerField(
        label="Bonus/Malus zur Initiative",
        initial=0,
        required=False,
        help_text="Wird zum Wahrnehmungsbonus addiert.",
    )
    category = forms.ChoiceField(
        label="Kategorie",
        choices=[("", "Bitte wählen")]
        + [(key, value[0]) for key, value in CATEGORIES.items()],
        required=False,
        widget=forms.Select(attrs={"required": True}),
    )
    element = forms.ChoiceField(
        label="Element",
        required=False,
        choices=[
            ("", "Keines"),
            ("E", "Erde"),
            ("F", "Feuer"),
            ("W", "Wasser"),
            ("L", "Luft"),
        ],
    )
    magical_strength = forms.BooleanField(
        label="Magische Stärke",
        required=False,
    )
    general_attack = forms.BooleanField(
        label="Ein genereller Angriffswert für alle Angriffsarten",
        required=False,
    )
    school_levels = forms.IntegerField(
        label="Stufen in Kampf- und Magieschulen",
        min_value=0,
        initial=0,
        required=False,
    )
    checked = forms.BooleanField(
        label="Alles erfasst",
        required=False,
    )

    class Meta:
        model = Creature
        fields = [
            "size_class",
            "natural_rs",
            "wound_step_override",
            "wound_thresholds_override",
            "combat_speed",
            "march_speed",
            "sprint_speed",
            "swimming_speed",
            "combat_swimming_speed",
            "march_swimming_speed",
            "sprint_swimming_speed",
            "combat_fly_speed",
            "march_fly_speed",
            "sprint_fly_speed",
            "has_kp",
            "kp_override",
            "potential_override",
            "climate_and_occurrence",
            "organization",
            "description",
            "is_swarm_creature",
        ]
        labels = {
            "name": "Name",
            "size_class": "Größenklasse",
            "natural_rs": "Natürlicher RS",
            "has_kp": "Besitzt Arkane Macht",
            "kp_override": "Arkane Macht (leer: Willenskraft + Schulstufen)",
            "potential_override": "Potential (leer: Willenskraft / 2)",
            "wound_step_override": "LP pro Wundgrad (leer: Konstitution)",
            "wound_thresholds_override": (
                "Kumulative Wundschwellen (sechs Zahlen)"
            ),
            "combat_speed": "Boden: Kampf",
            "march_speed": "Boden: Marsch",
            "sprint_speed": "Boden: Sprint",
            "swimming_speed": "Boden: Schwimmen",
            "combat_swimming_speed": "Schwimmen: Kampf",
            "march_swimming_speed": "Schwimmen: Marsch",
            "sprint_swimming_speed": "Schwimmen: Sprint",
            "combat_fly_speed": "Fliegen: Kampf",
            "march_fly_speed": "Fliegen: Marsch",
            "sprint_fly_speed": "Fliegen: Sprint",
            "climate_and_occurrence": "Klima und Vorkommen",
            "organization": "Organisation",
            "description": "Beschreibung",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "climate_and_occurrence": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_wound_thresholds_override(self):
        value = self.cleaned_data["wound_thresholds_override"]
        if value:
            try:
                thresholds = [int(token.strip()) for token in value.split(",")]
            except ValueError as exc:
                raise forms.ValidationError(
                    "Sechs ganze Zahlen angeben."
                ) from exc
            if (
                len(thresholds) != 6
                or thresholds[0] < 0
                or thresholds != sorted(thresholds)
            ):
                raise forms.ValidationError(
                    "Sechs aufsteigende, nichtnegative Schwellen angeben."
                )
        return value

    def clean(self):
        data = super().clean()
        category = data.get("category")
        if category in CATEGORY_TYPES:
            slug, _label = CATEGORY_TYPES[category]
            creature_type = CreatureType.objects.filter(slug=slug).first()
            self.instance.creature_type = creature_type
            data["creature_type"] = creature_type
            self.instance.has_bp = category == "V"
            self.instance.vampire_default_enabled = category == "V"
            if category == "V":
                data["has_kp"] = False
        if all(
            data.get(key) is not None
            for key in (
                "combat_swimming_speed",
                "march_swimming_speed",
                "sprint_swimming_speed",
            )
        ):
            data["swimming_speed"] = None
        if data.get("category") == "EW" and not data.get("element"):
            self.add_error("element", "Element des Elementarwesens wählen.")
        return data


class AttributeForm(forms.ModelForm):
    absent = forms.BooleanField(
        label="Eigenschaft ist nicht vorhanden (—)",
        required=False,
    )

    class Meta:
        model = CreatureAttribute
        fields = ["attribute", "base_value"]
        labels = {"base_value": "Eigenschaftsbonus (leer: —)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attribute"].queryset = Attribute.objects.filter(
            short_name__in=ATTRIBUTE_CODES
        )
        self.fields["attribute"].disabled = True

    def clean(self):
        data = super().clean()
        if data.get("base_value") is None and not data.get("absent"):
            self.add_error(
                "base_value",
                "Bonus oder ausdrücklich „nicht vorhanden“ wählen.",
            )
        if data.get("base_value") is not None and data.get("absent"):
            self.add_error(
                "absent", "Vorhandene Eigenschaft nicht als fehlend markieren."
            )
        return data


class AttackForm(forms.ModelForm):
    damage_formula_choice = forms.CharField(
        label="Schadensformel",
        required=False,
        max_length=32,
        widget=forms.HiddenInput(),
    )
    damage_editor_active = forms.BooleanField(
        required=False, widget=forms.HiddenInput()
    )
    damage_formula_input = forms.JSONField(
        required=False, widget=forms.HiddenInput()
    )
    damage_level_confirmed = forms.BooleanField(
        label="Schadensstufe ausdrücklich zuordnen", required=False
    )
    automatic_attack = forms.BooleanField(
        label="Angriff aus GE + GK + Bonus ableiten",
        initial=True,
        required=False,
    )
    attack_bonus = forms.IntegerField(
        label="Angriffsbonus", initial=0, required=False
    )
    automatic_damage = forms.BooleanField(
        label="Schadensstufe aus Stärke + Anpassung ableiten",
        initial=True,
        required=False,
    )
    damage_adjustment = forms.IntegerField(
        label="Anpassung der Schadensstufe",
        initial=0,
        required=False,
    )
    damage_level = forms.IntegerField(
        label="Manuelle Schadensstufe",
        min_value=0,
        required=False,
    )
    damage_kind = forms.ChoiceField(
        label="Schadensart für Machtkosten",
        choices=[
            ("physical", "Körperlich / kostenlose Schadensart"),
            ("fire", "Feuer mit Entflammchance"),
            ("energy", "Rüstungsumgehende Energie"),
            ("acid", "Säure"),
        ],
    )
    acid_power = forms.DecimalField(label="Macht der Säure", required=False)
    short_range = forms.DecimalField(
        label="Kurze Reichweite (m)",
        min_value=0,
        initial=0,
        required=False,
    )
    extra_damage_types = forms.IntegerField(
        label="Weitere kostenlose Schadensarten",
        min_value=0,
        initial=0,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attack_value"].required = False

    class Meta:
        model = CreatureAttack
        fields = [
            "name",
            "attack_type",
            "attack_value",
            "damage_dice_amount",
            "damage_dice_faces",
            "damage_flat_operator",
            "damage_flat_bonus",
            "damage_type",
            "notes",
            "show_notes_as_damage",
            "append_notes_to_damage",
            "order",
        ]
        labels = {
            "name": "Angriffsname",
            "attack_value": "Angriffswert (fertig)",
            "damage_dice_amount": "Schadenswürfel: Anzahl",
            "damage_dice_faces": "Schadenswürfel: Seiten",
            "damage_flat_operator": "Schadensoperator",
            "damage_flat_bonus": "Schadensbonus / Divisor",
            "damage_type": "B / T",
            "notes": "Angriffshinweis",
        }
        widgets = {
            key: forms.HiddenInput()
            for key in (
                "damage_dice_amount",
                "damage_dice_faces",
                "damage_flat_operator",
                "damage_flat_bonus",
                "show_notes_as_damage",
                "append_notes_to_damage",
            )
        }

    def clean(self):
        data = super().clean()
        if data.get("damage_editor_active"):
            formula = data.get("damage_formula_input")
            try:
                validate_formula(formula)
                level = match_damage_level(formula)
            except ValueError as exc:
                self.add_error("damage_formula_input", str(exc))
            else:
                if level is not None:
                    data["damage_level"] = level
                elif (
                    not data.get("damage_level_confirmed")
                    or data.get("damage_level") is None
                ):
                    data["damage_level"] = None
                    self.add_error(
                        "damage_level_confirmed",
                        "Keine offizielle Schadensstufe: bitte eine Stufe "
                        "angeben und die manuelle Zuordnung bestätigen.",
                    )
        if data.get("attack_value") is None:
            if data.get("automatic_attack"):
                data["attack_value"] = 0
            else:
                self.add_error("attack_value", "Festen Angriffswert angeben.")
        if (
            not data.get("damage_editor_active")
            and not data.get("automatic_damage")
            and data.get("damage_level") is None
        ):
            self.add_error("damage_level", "Schadensstufe angeben.")
        if (
            not data.get("damage_editor_active")
            and self.instance.pk
            and self.instance.show_notes_as_damage
            and not data.get("damage_formula_choice")
            and not data.get("damage_level_confirmed")
        ):
            self.add_error(
                "damage_level_confirmed",
                "Bisherigen Schaden beibehalten: Schadensstufe manuell "
                "angeben und Zuordnung bestätigen.",
            )
        return data


class SkillForm(forms.ModelForm):
    class Meta:
        model = CreatureSkill
        fields = ["skill", "level", "deviation", "notes"]
        labels = {
            "skill": "Fertigkeit",
            "level": "Fertigkeitsstufen",
            "deviation": "Abweichung",
            "notes": "Hinweis",
        }


class LanguageForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.is_mother_tongue = False

    class Meta:
        model = CreatureLanguage
        fields = ["language", "levels", "can_write"]
        labels = {
            "language": "Sprache",
            "levels": "Stufe",
            "can_write": "Lesen und Schreiben",
        }


LanguageFormSet = inlineformset_factory(
    Creature, CreatureLanguage, form=LanguageForm,
    extra=0, can_delete=True,
)


class AbilityForm(forms.Form):
    rule = forms.ChoiceField(label="Fähigkeit / Nachteil")

    def __init__(self, *args, **kwargs):
        catalog = kwargs.pop("catalog", None)
        super().__init__(*args, **kwargs)
        self.catalog = ability_catalog() if catalog is None else catalog
        groups = {}
        for key, entry in self.catalog.items():
            groups.setdefault(entry["group"], []).append(
                (key, entry["entry"].name)
            )
        self.fields["rule"].choices = [("", "Bitte wählen"), *groups.items()]
        value = str(
            (self.data.get(self.add_prefix("rule")) or "")
            if self.is_bound
            else self.initial.get("catalog_key")
            or self.initial.get("rule", "")
        )
        if value.isdecimal():
            value = next(
                (
                    key
                    for key, entry in self.catalog.items()
                    if entry["rule"] and entry["rule"].pk == int(value)
                ),
                value,
            )
        if self.is_bound:
            self.data = self.data.copy()
            self.data[self.add_prefix("rule")] = value
        else:
            self.initial["rule"] = value
        self.catalog_key = value
        entry = self.catalog.get(value)
        rule = entry["rule"] if entry else None
        if rule:
            values = self.initial.get("parameters", {})
            for name, spec in rule.parameters.items():
                field = (
                    forms.IntegerField
                    if spec.get("integer")
                    else forms.DecimalField
                )
                self.fields[f"param_{name}"] = field(
                    label=spec.get("label", name),
                    initial=values.get(name),
                    min_value=spec.get("min"),
                    max_value=spec.get("max"),
                )

    def clean_rule(self):
        entry = self.catalog[self.cleaned_data["rule"]]
        if not entry["rule"]:
            raise forms.ValidationError(
                f"{entry['entry'].name}: "
                "Es ist noch keine Machtregel verknüpft."
            )
        return entry["rule"]

    def selection(self):
        rule = self.cleaned_data["rule"]
        return {
            "rule": rule.pk,
            "catalog_key": self.catalog_key,
            "parameters": {
                name: str(self.cleaned_data[f"param_{name}"])
                for name in rule.parameters
            },
        }


AttributeFormSet = inlineformset_factory(
    Creature,
    CreatureAttribute,
    form=AttributeForm,
    extra=0,
    can_delete=False,
)
AttackFormSet = inlineformset_factory(
    Creature,
    CreatureAttack,
    form=AttackForm,
    extra=0,
    can_delete=True,
)
SkillFormSet = inlineformset_factory(
    Creature,
    CreatureSkill,
    form=SkillForm,
    extra=0,
    can_delete=True,
)
AbilityFormSet = formset_factory(AbilityForm, extra=0, can_delete=True)
