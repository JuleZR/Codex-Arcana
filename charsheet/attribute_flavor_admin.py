"""Editable scales, neutral templates and a preview of unsaved narratives."""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from .attribute_flavor import (
    description_template,
    narrative_html,
    race_narrative_values,
)
from .models import (
    Attribute,
    AttributeRating,
    Character,
    GeneralAttributeMeaning,
    Race,
    RaceAttributeFlavor,
)
from .narrative_templates import validate_narrative

NARRATIVE_SECTION = (
    "Beschreibung",
    {
        "fields": ("narrative_template",),
    },
)
OPTIONS_SECTION = (
    "Weitere Optionen und Platzhalter",
    {
        "fields": (
            ("active", "priority"),
            "neutral_template",
            "source_reference",
            "template_help",
        ),
        "classes": ("collapse",),
    },
)
PREVIEW_SECTION = (
    "Vorlage testen – ohne Speichern",
    {
        "description": (
            "Optional einen vorhandenen Charakter wählen oder "
            "eigene Testdaten "
            "eingeben. Name und Rasse lassen sich überschreiben. Das gewählte "
            "Geschlecht bestimmt die Vorschau; Neutral testet den Ersatztext."
        ),
        "fields": (
            "preview_character",
            ("preview_name", "preview_race"),
            ("preview_gender", "preview_attribute", "preview_value"),
            ("preview_meaning", "preview_rating"),
            "template_preview",
        ),
        "classes": ("collapse",),
    },
)


class PreviewInputs(forms.Form):
    preview_character = forms.ModelChoiceField(
        Character.objects.select_related("race"),
        required=False,
        label="Vorhandener Charakter (optional)",
    )
    preview_name = forms.CharField(required=False, label="Charaktername")
    preview_race = forms.ModelChoiceField(
        Race.objects.all(), required=False, label="Rasse"
    )
    preview_gender = forms.ChoiceField(
        choices=[
            ("", "Neutral / nicht angegeben"),
            (Character.Gender.M, "Männlich"),
            (Character.Gender.W, "Weiblich"),
        ],
        required=False,
        label="Geschlecht",
    )
    preview_attribute = forms.ModelChoiceField(
        Attribute.objects.all(),
        required=False,
        label="Eigenschaft",
    )
    preview_value = forms.IntegerField(
        required=False, label="Eigenschaftswert"
    )
    preview_meaning = forms.CharField(required=False, label="Bedeutung")
    preview_rating = forms.CharField(required=False, label="Bezeichnung")


class FlavorAdminForm(forms.ModelForm, PreviewInputs):
    class Meta:
        fields = "__all__"
        labels = {
            "official_designation": "Bezeichnung",
            "official_meaning": "Bedeutung",
            "narrative_template": "Beschreibung",
            "neutral_template": "Neutrale Variante (optional)",
        }
        widgets = {
            "narrative_template": forms.Textarea(attrs={"rows": 3}),
            "neutral_template": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        help_texts = {
            "attribute": (
                "Die Eigenschaft, deren aktueller Wert diesen Text auswählt. "
                "Die vorhandene Eigenschaftsdefinition wird wiederverwendet."
            ),
            "min_value": (
                "Kleinster Eigenschaftswert, für den der Eintrag gilt, "
                "einschließlich dieser Grenze. Es gewinnt die höchste "
                "passende Untergrenze. Leer bedeutet keine Untergrenze."
            ),
            "max_value": (
                "Größter Eigenschaftswert, für den der Eintrag gilt, "
                "einschließlich dieser Grenze. Leer bedeutet: auch höhere "
                "Werte sind erlaubt, bis eine höhere Untergrenze greift."
            ),
            "active": (
                "Nur aktive Einträge werden für die Karten ausgewählt. "
                "Deaktivieren behält den Eintrag zum späteren Bearbeiten."
            ),
            "priority": (
                "Höhere Zahlen gewinnen bei gleicher passender Untergrenze. "
                "Eine höhere Untergrenze hat immer Vorrang."
            ),
            "official_designation": (
                "Kurze Bezeichnung für diesen Wertebereich, optional."
            ),
            "official_description": (
                "Wörtlicher Beschreibungstext des Regelwerks, ohne "
                "Platzhalter oder Geschlechtsmarker. Wird separat als "
                "Regelwerk-Referenz angezeigt. Leer ist erlaubt."
            ),
            "official_meaning": (
                "Kurze Bedeutung für diesen Wertebereich, optional."
            ),
            "source_reference": (
                "Optionale Notiz zur Herkunft des Textes."
            ),
            "narrative_template": (
                "Text für die Karte; Markdown und Platzhalter sind möglich. "
                "{scale:11,50,200}: ab Wert 11 je Stufe 50 zusätzlich zu 200. "
                "Leer: allgemeine Ersatzbeschreibung verwenden."
            ),
            "neutral_template": (
                "Vollständiger Ersatz für einen Erzähltext mit "
                "Geschlechtsmarkern, wenn das Geschlecht fehlt oder weder "
                "männlich noch weiblich ist. Platzhalter sind erlaubt, "
                "Geschlechtsmarker nicht. Leer: allgemeine Beschreibung "
                "suchen; beim Rassenvergleich eine allgemeine Regel versuchen."
            ),
            "preview_character": (
                "Optional vorhandene Daten für Name, Rasse und "
                "Eigenschaftswert verwenden. Die folgenden Testfelder "
                "können diese Daten überschreiben. Der Charakter wird "
                "durch die Vorschau nicht geändert."
            ),
            "preview_name": (
                "Testwert für {character_name}. Leer: Name des ausgewählten "
                "Charakters; ohne Charakter bleibt der Platzhalter leer."
            ),
            "preview_race": (
                "Testwert für {race}: der gespeicherte Anzeigename der Rasse. "
                "Leer: Rasse des ausgewählten Charakters, sonst leer."
            ),
            "preview_gender": (
                "Bestimmt ausschließlich die Geschlechtsform der Vorschau. "
                "Neutral prüft den neutralen Ersatztext. Diese Auswahl "
                "überschreibt auch das Geschlecht eines Testcharakters."
            ),
            "preview_attribute": (
                "Testwert für {attribute}. Zusammen mit einem Testcharakter "
                "kann dessen aktueller Eigenschaftswert übernommen werden. "
                "Leer: der Platzhalter bleibt leer."
            ),
            "preview_value": (
                "Testwert für {value}. Leer: aktueller Wert des "
                "Testcharakters für die gewählte Testeigenschaft, sonst leer. "
                "Die Vorschau rendert diese Vorlage unabhängig von "
                "deren Geltungsbereich."
            ),
            "preview_meaning": (
                "Testwert für {meaning}. Hier die gewünschte Bedeutung "
                "eingeben; leer lässt den Platzhalter leer."
            ),
            "preview_rating": (
                "Testwert für {rating}. Hier eine Bezeichnung "
                "eingeben; leer lässt den Platzhalter leer."
            ),
        }
        if isinstance(self.instance, AttributeRating):
            help_texts["min_value"] = help_texts["min_value"].replace(
                "Leer bedeutet keine Untergrenze.",
                "Dieses Feld ist Pflicht.",
            )
        if isinstance(self.instance, GeneralAttributeMeaning):
            help_texts["narrative_template"] = (
                "Ersatzbeschreibung, wenn kein passender Attributtext "
                "vorliegt."
            )
        if isinstance(self.instance, RaceAttributeFlavor):
            if "attribute" in self.fields:
                self.fields["attribute"].empty_label = "Alle Eigenschaften"
            help_texts.update(
                {
                    "attribute": (
                        "Optional auf eine Eigenschaft begrenzen. Leer: alle "
                        "Eigenschaften. Eine passende spezifische Regel "
                        "hat Vorrang vor allgemeinen Vergleichsregeln."
                    ),
                    "min_value": (
                        "Ab diesem Abstand, einschließlich. Leer: unbegrenzt."
                    ),
                    "max_value": (
                        "Bis zu diesem Abstand, einschließlich. "
                        "Leer: unbegrenzt."
                    ),
                    "priority": (
                        "Höhere Zahlen gewinnen unter mehreren passenden "
                        "Vergleichsregeln. Eine spezifische Eigenschaftsregel "
                        "hat unabhängig davon Vorrang vor einer allgemeinen."
                    ),
                    "narrative_template": (
                        "Text, der bei diesem Abstand auf der Karte "
                        "erscheint. {scale:11,50,200} berechnet eine Zahl "
                        "aus dem aktuellen Attributwert."
                    ),
                }
            )
        for name, field in self.fields.items():
            if name in help_texts:
                field.help_text = help_texts[name]
        if isinstance(self.instance, RaceAttributeFlavor):
            self.fields["min_value"].label = "Abstand ab"
            self.fields["max_value"].label = "Abstand bis"
        if "official_description" not in self.fields:
            self.initial["narrative_template"] = description_template(
                self.instance
            )
            self.initial["neutral_template"] = description_template(
                self.instance, neutral=True
            )

    def clean(self):
        cleaned = super().clean()
        if "official_description" not in self.fields and isinstance(
            self.instance, AttributeRating
        ):
            self.instance.official_description = ""
        return cleaned


class FlavorAdmin(admin.ModelAdmin):
    form = FlavorAdminForm
    list_display = ("min_value", "max_value", "priority", "active")
    list_filter = ("active",)
    search_fields = ("narrative_template", "source_reference")
    readonly_fields = ("template_help", "template_preview")

    class Media:
        js = ("js/charsheet/attribute_flavor_preview.js",)

    def get_urls(self):
        return [
            path(
                "preview/",
                self.admin_site.admin_view(self.preview),
                name=(
                    f"{self.model._meta.app_label}_"
                    f"{self.model._meta.model_name}_preview"
                ),
            ),
            *super().get_urls(),
        ]

    @admin.display(description="Vorlagensprache")
    def template_help(self, obj):
        placeholders = (
            ("{character_name}", "Name des Charakters."),
            ("{race}", "Gespeicherter Anzeigename der Rasse."),
            (
                "{race_accusative}",
                "Akkusativ ohne Artikel: für einen Menschen / Sidhe. "
                "Im Rassen-Admin pflegen; leer verwendet den Namen.",
            ),
            (
                "{race_plural}",
                "Plural ohne Artikel, im Rassen-Admin gepflegt. "
                "Leer verwendet den Namen.",
            ),
            ("{attribute}", "Name der angeklickten Eigenschaft."),
            ("{value}", "Aktuell angezeigter Eigenschaftswert."),
            (
                "{meaning}",
                "Passende Bezeichnung, sonst allgemeine Bedeutung.",
            ),
            (
                "{rating}",
                "Passende Bezeichnung; ohne Bezeichnung leer.",
            ),
        )
        return format_html(
            "<dl>{}</dl><p>Berechnete Zahl: "
            "<code>{{scale:11,50,200}}</code> = ab Attributwert 11 "
            "pro Stufe 50 zusätzlich zur Grundmenge 200. "
            "Wert 10 → 200, Wert 11 → 250, Wert 12 → 300. "
            "Ohne Grundmenge: <code>{{scale:11,50}}</code> "
            "ergibt 0, 50, 100. Nur ganze Zahlen; mehrere berechnete "
            "Zahlen im selben Text sind möglich.</p>"
            "<p>^Text^: nur männlich; ~~Text~~: nur weiblich. "
            "Normaler Text erscheint immer. Für literale Marker einen "
            "Backslash voranstellen: <code>\\^</code>, <code>\\~</code>. "
            "Literale Klammern doppeln: <code>{{{{</code> und "
            "<code>}}}}</code>. Marker nicht verschachteln.</p>",
            format_html_join(
                "",
                "<dt><code>{}</code></dt><dd>{}</dd>",
                placeholders,
            ),
        )

    @admin.display(description="Vorschau (ohne Speichern)")
    def template_preview(self, obj):
        url = reverse(
            f"admin:{self.model._meta.app_label}_"
            f"{self.model._meta.model_name}_preview",
        )
        return format_html(
            '<button type="button" data-flavor-preview-url="{}">'
            "Vorlage prüfen</button><div data-flavor-preview-result "
            'aria-live="polite"></div>',
            url,
        )

    def preview(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        if request.method != "POST":
            return JsonResponse({"error": "POST erforderlich."}, status=405)
        form = PreviewInputs(request.POST)
        if not form.is_valid():
            return JsonResponse({"error": str(form.errors)}, status=400)
        template = request.POST.get("narrative_template", "")
        neutral = request.POST.get("neutral_template", "")
        try:
            validate_narrative(template)
            validate_narrative(neutral, neutral=True)
        except ValidationError as exc:
            return JsonResponse({"error": " ".join(exc.messages)}, status=400)
        data = form.cleaned_data
        character = data["preview_character"]
        attribute = data["preview_attribute"]
        race = data["preview_race"] or (character.race if character else None)
        values = {
            "character_name": data["preview_name"]
            or (character.name if character else ""),
            **race_narrative_values(race),
            "attribute": attribute.name if attribute else "",
            "value": (
                data["preview_value"]
                if data["preview_value"] is not None
                else ""
            ),
            "meaning": data["preview_meaning"],
            "rating": data["preview_rating"],
        }
        if character and attribute and data["preview_value"] is None:
            values["value"] = character.engine.attributes().get(
                attribute.short_name, 0
            )
        rule = self.model(
            narrative_template=template, neutral_template=neutral
        )
        return JsonResponse(
            {
                "html": narrative_html(
                    rule,
                    values,
                    data["preview_gender"],
                )
            }
        )


@admin.register(AttributeRating)
class AttributeRatingAdmin(FlavorAdmin):
    list_filter = ("attribute", "active")
    list_display = (
        "attribute",
        "designation",
        *FlavorAdmin.list_display,
    )
    search_fields = (
        *FlavorAdmin.search_fields,
        "official_designation",
        "official_description",
    )
    ordering = ("attribute__name", "min_value", "-priority")

    @admin.display(description="Bezeichnung", ordering="official_designation")
    def designation(self, obj):
        return obj.official_designation

    fieldsets = (
        (
            "Eigenschaft und Geltungsbereich",
            {
                "description": (
                    "Es gilt die höchste Untergrenze, die den aktuellen Wert "
                    "nicht übersteigt. Eine Obergrenze ist optional."
                ),
                "fields": (
                    "attribute",
                    ("min_value", "max_value"),
                    "official_designation",
                ),
            },
        ),
        NARRATIVE_SECTION,
        OPTIONS_SECTION,
        PREVIEW_SECTION,
    )


@admin.register(GeneralAttributeMeaning)
class GeneralAttributeMeaningAdmin(FlavorAdmin):
    list_display = ("meaning", *FlavorAdmin.list_display)
    ordering = ("min_value", "-priority")

    @admin.display(description="Bedeutung", ordering="official_meaning")
    def meaning(self, obj):
        return obj.official_meaning

    fieldsets = (
        (
            "Geltungsbereich und Ersatzbeschreibung",
            {
                "description": (
                    "Wird verwendet, wenn kein passender Eigenschaftstext "
                    "vorhanden ist. Offene Bereiche können auch Werte über "
                    "den dokumentierten GRW-Tabellen abdecken."
                ),
                "fields": (("min_value", "max_value"), "official_meaning"),
            },
        ),
        NARRATIVE_SECTION,
        OPTIONS_SECTION,
        PREVIEW_SECTION,
    )


@admin.register(RaceAttributeFlavor)
class RaceAttributeFlavorAdmin(FlavorAdmin):
    list_filter = ("attribute", "active")
    list_display = ("comparison_scope", *FlavorAdmin.list_display)
    ordering = ("attribute__name", "min_value", "-priority")
    fieldsets = (
        (
            "Vergleich mit dem Rassenmaximum",
            {
                "description": (
                    "Wann erscheint der Text? Der Abstand zählt vom "
                    "Rassenmaximum: −2 = zwei Punkte darunter, "
                    "0 = genau am Maximum, +1 = ein Punkt darüber. "
                    "Beispiel: ab −2 bis 0 gilt für die letzten zwei "
                    "Punkte unter dem Maximum und das Maximum selbst. "
                    "Leere Grenzen sind unbegrenzt."
                ),
                "fields": (
                    "attribute",
                    ("min_value", "max_value"),
                ),
            },
        ),
        NARRATIVE_SECTION,
        OPTIONS_SECTION,
        PREVIEW_SECTION,
    )

    @admin.display(description="Gilt für", ordering="attribute__name")
    def comparison_scope(self, obj):
        return obj.attribute.name if obj.attribute_id else "Alle Eigenschaften"


class AttributeRatingInline(admin.StackedInline):
    model = AttributeRating
    form = FlavorAdminForm
    extra = 0
    show_change_link = True
    ordering = ("min_value", "-priority")
    readonly_fields = ("template_help",)
    template_help = FlavorAdmin.template_help
    fieldsets = (
        (
            AttributeRatingAdmin.fieldsets[0][0],
            {
                **AttributeRatingAdmin.fieldsets[0][1],
                "fields": (
                    ("min_value", "max_value"), "official_designation",
                ),
            },
        ),
        *AttributeRatingAdmin.fieldsets[1:-1],
    )


class RaceAttributeFlavorInline(admin.StackedInline):
    model = RaceAttributeFlavor
    form = FlavorAdminForm
    extra = 0
    show_change_link = True
    ordering = ("min_value", "-priority")
    readonly_fields = ("template_help",)
    template_help = FlavorAdmin.template_help
    fieldsets = (
        (
            RaceAttributeFlavorAdmin.fieldsets[0][0],
            {
                **RaceAttributeFlavorAdmin.fieldsets[0][1],
                "fields": (
                    ("min_value", "max_value"),
                ),
            },
        ),
        NARRATIVE_SECTION,
        OPTIONS_SECTION,
    )
