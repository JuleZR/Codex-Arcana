from django.db import migrations


WEAKNESSES = [
    ("tiererkennung", "Von Tieren erkannt", "Tiere erkennen die wahre Gestalt des Vampirs sofort und greifen ihn an oder fliehen vor ihm."),
    ("blutgier", "Blutgier", "Beim Anblick frischen Blutes ist Beherrschung erschwert; die Augen leuchten rot, solange offenes Blut in der Nähe ist."),
    ("lichtempfindliche-augen", "Lichtempfindliche Augen", "Die Augen schmerzen bei Licht; helles Sonnenlicht blendet vollständig."),
    ("knoblauchempfindlichkeit", "Knoblauchempfindlichkeit", "Knoblauch verursacht Schaden; Knoblauch im Mund versetzt den Vampir bis zur Entfernung in Starre."),
    ("kein-spiegelbild", "Kein Spiegelbild", "Der Vampir besitzt kein Spiegelbild."),
    ("feuerverwundbarkeit", "Feuerverwundbarkeit", "Feuer und feuerbasierte Zauber verursachen doppelten Schaden."),
    ("pflanzenwelke", "Pflanzenwelke", "Kleinere Pflanzen verwelken im Umkreis von einem Meter."),
    ("silberverwundbarkeit", "Silberverwundbarkeit", "Silberne Waffen verursachen doppelten Schaden; bereits die Berührung verbrennt die Haut."),
    ("klerikale-empfindlichkeit", "Klerikale Empfindlichkeit", "Die Widerstandswerte sind gegen klerikale Magie um vier reduziert."),
    ("abstand-heilige-symbole", "Abstand zu heiligen Symbolen", "Der Vampir kann sich sichtbaren heiligen Symbolen nicht freiwillig auf zwei Meter nähern."),
    ("einladung", "Einladung erforderlich", "Der Vampir kann ein Gebäude nur nach ausdrücklicher Einladung eines Bewohners betreten."),
    ("doppelter-klerikaler-schaden", "Doppelter klerikaler Schaden", "Klerikale Zauber verursachen doppelten Schaden."),
    ("mohnsamen", "Mohnsamen", "Frische Mohnsamen über dem Schlafplatz verhindern für 24 Stunden das Erheben aus der Erde."),
    ("tierreaktionen", "Auffällige Tierreaktionen", "Nachtaktive Raubtiere werden zutraulich; Beutetiere geraten in Panik und verursachen einen Malus von sechs beim Umgang."),
    ("fliessendes-wasser", "Fließendes Wasser", "Der Vampir kann freiwillig keine fließenden Gewässer überqueren."),
    ("doppelte-sonne", "Verstärkte Sonnenallergie", "Sonnenlicht verursacht doppelten Schaden."),
    ("fischernetz", "Fischernetz", "Ein benutztes Fischernetz versetzt den Vampir bis zu seiner Entfernung oder seinem Zerfall in Starre."),
    ("verraeterischer-schatten", "Verräterischer Schatten", "Der Schatten stellt die Absichten des Vampirs pantomimisch dar."),
    ("heilige-staetten", "Heilige Stätten", "Der Vampir kann heilige Stätten nicht betreten und muss sie verlassen."),
    ("silber-schwer-heilbar", "Silber als schwer heilbarer Schaden", "Silberne oder versilberte Waffen verursachen schwer heilbaren Schaden."),
    ("wahre-monstergestalt", "Wahre Monstergestalt", "Ohne die Kraftwirkung oder bei Berührung durch ein heiliges Symbol erscheint die hässliche wahre Gestalt."),
    ("kein-schatten", "Kein Schatten", "Der Vampir wirft keinen Schatten."),
    ("sanctum-erde", "Erde des Sanctums", "Der Vampir muss mit Erde aus einem Sanctum schlafen oder fällt bis zu entsprechender Ruhe in Starre."),
    ("durchscheinende-haut", "Durchscheinende Haut", "Die Haut bleibt bleich und durchscheinend; geweihtes Wasser verursacht schwer heilbaren Schaden."),
    ("silberzunge", "Silberzunge", "Silber auf der Zunge verursacht Schaden und Starre, bis es entfernt wird."),
]


POWERS = [
    ("aura-sehen", "Aura sehen", 1, False, "manual_activation", "Bestimmt mit einer Alterszyklusprobe gegen den GW Stimmung und Wesen eines Gegenübers.", "tiererkennung"),
    ("blutraub", "Blutraub", 1, False, "blood_theft", "Entzieht nach einer Alterszyklusprobe gegen die SR einem sichtbaren Ziel Blut; kostet eine Aktion und einen Blutpunkt.", "blutgier"),
    ("blutsakrament", "Blutsakrament", None, False, "blood_sacrament", "Erhöht den Alterszyklus vorübergehend bis maximal zum Potential; die Wirkung hält mehrere Runden und ist nicht kumulativ.", "lichtempfindliche-augen"),
    ("blutsinn", "Blutsinn", None, False, "manual_activation", "Spürt ein Opfer anhand seines Geruchs auf und verfolgt dessen Blutquelle in altersabhängiger Reichweite.", "knoblauchempfindlichkeit"),
    ("die-macht-des-blutes", "Die Macht des Blutes", None, False, "attribute_boost", "Erhöht für eine Szene eine Eigenschaft um einen Punkt je eingesetztem Blutpunkt, begrenzt durch den Alterszyklus.", "kein-spiegelbild"),
    ("fliegen", "Fliegen", None, False, "", "Erlaubt schwebende Bewegung mit der normalen Bewegungsweite.", "feuerverwundbarkeit"),
    ("furchtbare-praesenz", "Furchtbare Präsenz", 1, False, "manual_activation", "Strahlt für eine Szene Furcht in Höhe des Alterszyklus aus.", "pflanzenwelke"),
    ("gefaehrliche-klauen", "Gefährliche Klauen", 1, False, "manual_activation", "Verwandelt die Fingernägel in Klauen mit 2w10 T Schaden; Einfahren ist kostenlos.", "silberverwundbarkeit"),
    ("geistkontrolle", "Geistkontrolle", 1, False, "manual_activation", "Beherrscht nach einer Alterszyklusprobe gegen den GW ein intelligentes Wesen; Zielwirkungen werden manuell bestätigt.", "klerikale-empfindlichkeit"),
    ("geistreise", "Geistreise", None, False, "", "Der Geist kann im Schlaf bekannte Orte oder den Aufenthaltsort eines Dieners in altersabhängiger Reichweite wahrnehmen.", "abstand-heilige-symbole"),
    ("gestaltwandel", "Gestaltwandel", 1, False, "manual_activation", "Verwandelt den Vampir innerhalb einer Runde in Fledermaus oder Wolf; Rückverwandlung ist kostenlos.", "einladung"),
    ("ghulmeister", "Ghulmeister", None, False, "manual_activation", "Kann durch eigenes Blut und eine Alterszyklusprobe Ghule erschaffen und bis zum Alterszyklus viele kontrollieren.", "doppelter-klerikaler-schaden"),
    ("in-der-erde-versinken", "In der Erde versinken", 1, False, "manual_activation", "Lässt den Vampir drei Meter in geeignetem Boden versinken und später wieder aufsteigen.", "mohnsamen"),
    ("kinder-der-nacht-befehligen", "Kinder der Nacht befehligen", None, False, "manual_activation", "Ruft und kontrolliert je Alterszyklus einen Schwarm Ratten oder Fledermäuse oder einen Wolf.", "tierreaktionen"),
    ("nebelgestalt", "Nebelgestalt", 3, False, "manual_activation", "Verwandelt den Vampir in ätherischen Nebel mit drei Metern Bewegung pro Runde.", "fliessendes-wasser"),
    ("prinz-der-finsternis", "Prinz der Finsternis", 1, False, "manual_activation", "Verwandelt den Vampir in ein flugfähiges Monster, erhöht Stärke um fünf und verändert Fänge und Klauen.", "doppelte-sonne"),
    ("rufen", "Rufen", None, False, "manual_activation", "Ruft nach Alterszyklusprobe gegen den GW ein bekanntes intelligentes Wesen in altersabhängiger Reichweite.", "fischernetz"),
    ("schatten-befehligen", "Schatten befehligen", 1, False, "manual_activation", "Löscht kleinere Lichtquellen und erlaubt das Formen von Schatten; im Sanctum ist das Löschen kostenlos.", "verraeterischer-schatten"),
    ("schattengestalt", "Schattengestalt", 2, False, "manual_activation", "Macht den Vampir bei Dunkelheit unsichtbar und bei Licht schwer erkennbar; endet spätestens bei Sonnenaufgang.", "heilige-staetten"),
    ("schattenwandeln", "Schattenwandeln", None, False, "manual_activation", "Versetzt den Vampir einmal pro Runde zwischen ausreichend großen Schatten innerhalb altersabhängiger Reichweite.", "silber-schwer-heilbar"),
    ("sterbliche-erscheinung", "Sterbliche Erscheinung", None, False, "manual_activation", "Unterdrückt kraftbedingte Schwächen für eine Minute je eingesetztem Blutpunkt.", None),
    ("uebernatuerliche-schoenheit", "Übernatürliche Schönheit", 1, False, "manual_activation", "Gewährt für eine Szene einen Bonus von sechs auf sichtbasierte soziale Interaktionen.", "wahre-monstergestalt"),
    ("unheilige-geschwindigkeit", "Unheilige Geschwindigkeit", 1, True, "manual_activation", "Gewährt für einen Blutpunkt je gewähltem Rang eine zusätzliche freie Aktion in der Runde.", "kein-schatten"),
    ("unheiliges-sanctum", "Unheiliges Sanctum", None, True, "manual_activation", "Erschafft eine Domäne um eine Ruhestätte; weitere Ränge schaffen weitere Sancta oder verdoppeln den Radius.", "sanctum-erde"),
    ("unverwundbarkeit", "Unverwundbarkeit", None, False, "", "Gewährt natürlichen RS in Höhe des doppelten Alterszyklus.", "durchscheinende-haut"),
    ("zone-der-stille", "Zone der Stille", 1, False, "manual_activation", "Erzeugt für eine Szene eine geräuschdichte Zone mit altersabhängigem Radius.", "silberzunge"),
]


def seed_vampire_traits(apps, schema_editor):
    Trait = apps.get_model("charsheet", "Trait")
    VampireTrait = apps.get_model("charsheet", "VampireTrait")
    Effect = apps.get_model("charsheet", "VampireTraitSemanticEffect")

    Trait.objects.update_or_create(
        slug="adv_vampire",
        defaults={
            "name": "Vampir",
            "trait_type": "advantage",
            "min_level": 1,
            "max_level": 1,
            "points_per_level": 15,
            "points_by_level": "",
        },
    )

    weakness_by_slug = {}
    for order, (slug, name, rules_text) in enumerate(WEAKNESSES, start=100):
        weakness, _created = VampireTrait.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "trait_type": "weakness",
                "description": rules_text,
                "rules_text": rules_text,
                "point_value": 5,
                "blood_cost": None,
                "rankable": False,
                "max_rank": None,
                "handler": "",
                "associated_weakness": None,
                "sort_order": order,
                "is_active": True,
            },
        )
        weakness_by_slug[slug] = weakness

    for order, (slug, name, blood_cost, rankable, handler, rules_text, weakness_slug) in enumerate(POWERS, start=10):
        VampireTrait.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "trait_type": "power",
                "description": rules_text,
                "rules_text": rules_text,
                "point_value": 15,
                "blood_cost": blood_cost,
                "rankable": rankable,
                "max_rank": None,
                "handler": handler,
                "associated_weakness": weakness_by_slug.get(weakness_slug),
                "sort_order": order,
                "is_active": True,
            },
        )

    unverwundbarkeit = VampireTrait.objects.get(slug="unverwundbarkeit")
    Effect.objects.update_or_create(
        trait=unverwundbarkeit,
        target_domain="derived_stat",
        target_key="rs",
        sort_order=0,
        defaults={
            "application_scope": "both",
            "operator": "flat_add",
            "mode": "scaled",
            "value": "2",
            "scaling": {"scale_source": "vampire_age_cycle"},
            "active_flag": True,
            "rules_text": unverwundbarkeit.rules_text,
        },
    )



def unseed_vampire_traits(apps, schema_editor):
    VampireTrait = apps.get_model("charsheet", "VampireTrait")
    VampireTrait.objects.filter(
        slug__in=[row[0] for row in WEAKNESSES]
        + [row[0] for row in POWERS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0307_charactercreaturevampiretrait_charactervampiretrait_and_more")]

    operations = [migrations.RunPython(seed_vampire_traits, unseed_vampire_traits)]
