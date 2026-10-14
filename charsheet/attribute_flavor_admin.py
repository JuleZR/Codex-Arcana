"""Editable scales, neutral templates and a preview of unsaved narratives."""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from .attribute_flavor import narrative_html
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
    "Eigene Erzähltexte",
    {
        "description": (
            "Diese Texte sind eigene Ergänzungen und keine "
            "offiziellen GRW-Zitate. "
            "Die neutrale Vorlage ersetzt geschlechtsabhängige Texte bei "
            "nicht angegebenem oder anderem Geschlecht."
        ),
        "fields": ("narrative_template", "neutral_template", "template_help"),
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
                "Originalbezeichnung aus dem GRW. Leer lassen, wenn das "
                "Regelwerk für diesen Wert keine eigene Bezeichnung nennt."
            ),
            "official_description": (
                "Wörtlicher Beschreibungstext des Regelwerks, ohne "
                "Platzhalter oder Geschlechtsmarker. Wird separat als "
                "Regelwerk-Referenz angezeigt. Leer ist erlaubt."
            ),
            "official_meaning": (
                "Originaleintrag der allgemeinen GRW-Bedeutungstabelle. "
                "Bei einem rein eigenen Ersatztext leer lassen."
            ),
            "source_reference": (
                "Name und Edition des Regelwerks sowie Kapitel und Seite. "
                "Pflicht bei offiziellen Angaben; bei eigenen Texten "
                "optional. Dies ist keine Vorlage und wird nicht ersetzt."
            ),
            "narrative_template": (
                "Eigene kurze Sätze für die Karte. Platzhalter setzen "
                "Charakterdaten ein; ^Text^ erscheint männlich, ~~Text~~ "
                "weiblich. Markdown ist möglich, HTML wird nicht ausgeführt. "
                "Leer: stattdessen die allgemeine Ersatzbeschreibung suchen."
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
                "Testwert für {rating}. Hier eine offizielle Bezeichnung "
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
                "Eigene allgemeine Ersatzbeschreibung, wenn kein passender "
                "Eigenschaftstext gerendert werden kann. Platzhalter und "
                "Geschlechtsmarker sind erlaubt. Leer: keine eigene "
                "Erzählung; die offizielle Bedeutung bleibt als Referenz."
            )
        if isinstance(self.instance, RaceAttributeFlavor):
            self.fields["attribute"].empty_label = "Alle Eigenschaften"
            help_texts.update(
                {
                    "attribute": (
                        "Optional auf eine Eigenschaft begrenzen. Leer: alle "
                        "Eigenschaften. Eine passende spezifische Regel "
                        "hat Vorrang vor allgemeinen Vergleichsregeln."
                    ),
                    "min_value": (
                        "Kleinster erlaubter Abstand zum Rassenmaximum, "
                        "einschließlich der Grenze. Abstand = aktueller Wert "
                        "minus vorhandenes Rassenmaximum. 0 heißt am Maximum, "
                        "negative Zahlen darunter, positive darüber. "
                        "Leer: keine untere Grenze."
                    ),
                    "max_value": (
                        "Größter erlaubter Abstand zum Rassenmaximum, "
                        "einschließlich der Grenze. Leer: keine obere Grenze. "
                        "Gleiche Unter- und Obergrenze bedeutet genau "
                        "diesen Abstand."
                    ),
                    "priority": (
                        "Höhere Zahlen gewinnen unter mehreren passenden "
                        "Vergleichsregeln. Eine spezifische Eigenschaftsregel "
                        "hat unabhängig davon Vorrang vor einer allgemeinen."
                    ),
                    "narrative_template": (
                        "Zusätzlicher Satz zum Vergleich "
                        "mit dem Rassenmaximum. "
                        "Platzhalter und Geschlechtsmarker sind erlaubt. "
                        "Pflichtfeld; ohne passende Regel erscheint kein "
                        "zusätzlicher Vergleichstext."
                    ),
                }
            )
        for name, field in self.fields.items():
            if name in help_texts:
                field.help_text = help_texts[name]


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
            ("{attribute}", "Name der angeklickten Eigenschaft."),
            ("{value}", "Aktuell angezeigter Eigenschaftswert."),
            (
                "{meaning}",
                "Passende offizielle Bezeichnung, sonst allgemeine Bedeutung.",
            ),
            (
                "{rating}",
                "Passende offizielle Bezeichnung; ohne Bezeichnung leer.",
            ),
        )
        return format_html(
            "<dl>{}</dl><p>^Text^: nur männlich; ~~Text~~: nur weiblich. "
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
            "race": race.name if race else "",
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
        "official_designation",
        *FlavorAdmin.list_display,
    )
    search_fields = (
        *FlavorAdmin.search_fields,
        "official_designation",
        "official_description",
    )
    ordering = ("attribute__name", "min_value", "-priority")
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
                    ("active", "priority"),
                ),
            },
        ),
        (
            "Offizielle Regelwerk-Referenz (optional)",
            {
                "description": (
                    "Nur belegte Originalangaben eintragen, "
                    "mit Quellenangabe. "
                    "Die dokumentierten Werte mit einer Obergrenze begrenzen. "
                    "Eigene Formulierungen gehören in die Erzähltexte."
                ),
                "fields": (
                    "official_designation",
                    "official_description",
                    "source_reference",
                ),
            },
        ),
        NARRATIVE_SECTION,
        PREVIEW_SECTION,
    )


@admin.register(GeneralAttributeMeaning)
class GeneralAttributeMeaningAdmin(FlavorAdmin):
    list_display = ("official_meaning", *FlavorAdmin.list_display)
    ordering = ("min_value", "-priority")
    fieldsets = (
        (
            "Geltungsbereich und Ersatzbeschreibung",
            {
                "description": (
                    "Wird verwendet, wenn kein passender Eigenschaftstext "
                    "vorhanden ist. Offene Bereiche können auch Werte über "
                    "den dokumentierten GRW-Tabellen abdecken."
                ),
                "fields": (("min_value", "max_value"), ("active", "priority")),
            },
        ),
        (
            "Offizielle allgemeine Bedeutung (optional)",
            {
                "description": (
                    "Originalbedeutung und Quelle getrennt von eigenen Texten "
                    "pflegen. Keine eigenen Einstufungen "
                    "als GRW-Angaben ausgeben."
                ),
                "fields": ("official_meaning", "source_reference"),
            },
        ),
        NARRATIVE_SECTION,
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
                    "Abstand = aktueller Wert minus "
                    "vorhandenes Rassenmaximum. "
                    "0 bedeutet genau am Maximum, negative Werte darunter, "
                    "positive Werte darüber. Leere Grenzen sind offen. "
                    "Ohne Eigenschaft gilt die Regel allgemein; eine passende "
                    "eigenschaftsspezifische Regel hat Vorrang."
                ),
                "fields": (
                    "attribute",
                    ("min_value", "max_value"),
                    ("active", "priority"),
                    "source_reference",
                ),
            },
        ),
        NARRATIVE_SECTION,
        PREVIEW_SECTION,
    )

    @admin.display(description="Gilt für", ordering="attribute__name")
    def comparison_scope(self, obj):
        return obj.attribute.name if obj.attribute_id else "Alle Eigenschaften"
