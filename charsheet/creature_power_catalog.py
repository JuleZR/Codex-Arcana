"""Official creation cost definitions; MP are unrelated to training points.

Detailed descriptions take precedence over the overview where they differ:
Ätherisch p. 483, Würgen p. 481, Untotenfäule and Wyldwuchs p. 493.
"""

from django.utils.text import slugify


def official_rules():
    rows = []
    all_categories = "T PF B NG DR EW K D U"
    organic = "T PF B NG DR"
    magical = "PF B NG DR EW K D U"

    def add(
        name,
        formula,
        categories=all_categories,
        params=None,
        page=469,
        requirements=None,
        description="",
    ):
        rows.append(
            {
                "key": slugify(name),
                "name": name,
                "formula": str(formula),
                "categories": categories.split(),
                "parameters": params or {},
                "requirements": requirements or {},
                "official": True,
                "cost_kind": "composite" if params else "fixed",
                "source": f"Kompendium, S. {page}",
                "description": description
                or f"{name} (Kompendium, S. {page}).",
            }
        )

    def param(label="Stufe", minimum=1, maximum=None, choices=None):
        value = {"label": label, "min": minimum, "integer": True}
        if maximum is not None:
            value["max"] = maximum
        if choices is not None:
            value["choices"] = choices
        return value

    def level(
        name,
        formula,
        categories=all_categories,
        maximum=None,
        page=469,
        label="Stufe",
    ):
        add(
            name,
            formula,
            categories,
            {"level": param(label, 1, maximum)},
            page,
        )

    fixed = [
        ("Auf dem Wasser treibend schlafen", 3, "T B NG DR EW_W EW_L D"),
        ("Festbeißen", 4, all_categories),
        ("Fliegen (mit Flügeln)", 25, all_categories),
        ("Genügsamkeit beim Futter", 5, organic),
        ("Gleitflug", 12, all_categories),
        ("Greift auf Befehl des Reiters/Besitzers an", 8, all_categories),
        ("Mimikry", 12, all_categories),
        ("Nachtsicht", 16, "T B NG DR EW K D U"),
        ("Nestbauer", 3, "T B NG DR"),
        ("Opfer unter Wasser ziehen", 6, "T B NG DR EW K D U"),
        ("Restlichtverstärker", 10, "T B NG DR EW K D U"),
        ("Schlafen im Stehen", 2, "T B NG DR D"),
        ("Sehr lernfähig", 4, "T B NG EW K"),
        ("Sommerschlaf", 6, "T B NG DR"),
        ("Sonar", 15, "T B NG DR K D U"),
        ("Sprungattacke", 6, "T B NG DR EW K D U"),
        ("Staudamm bauen", 3, "T B NG DR EW_E K D"),
        ("Umklammerung", 10, "T B NG DR EW K D U"),
        ("Unechter Winterschlaf", 2, "T B NG DR"),
        ("Unter Wasser atmen", 18, "T B NG DR EW K D"),
        ("Verschlingen", 5, "T B NG DR EW K D U"),
        ("Wasserabstoßendes Fell", 2, "T B NG K"),
        ("Winterschlaf", 6, "T B NG DR"),
    ]
    for name, cost, cats in fixed:
        add(name, cost, cats)
    for name, formula, cats, maximum, label in (
        ("Blutgeruch", "level", "T B NG DR D U", None, "Bonus"),
        (
            "Durst ertragen",
            "level / 4",
            "T B NG DR D",
            None,
            "Zusätzliche Stunden",
        ),
        (
            "Eingraben",
            "3 * level",
            "T PF B NG DR D U K EW_E",
            None,
            "Meter pro Runde",
        ),
        ("Verbesserter Geruchssinn", "level", "T B NG DR D U EW", 15, "Bonus"),
        ("Furchtlos", "level", all_categories, 20, "Bonus gegen Furcht"),
        ("Hitzeunempfindlichkeit", "level / 2", all_categories, 20, "Bonus"),
        (
            "Hunger ertragen",
            "level / 12",
            organic,
            None,
            "Zusätzliche Stunden",
        ),
        ("Kälteunempfindlichkeit", "level", all_categories, 20, "Bonus"),
        ("Katzenfall", "level", all_categories, None, "Meter"),
        (
            "Krankheitsresistenz",
            "level / 2",
            organic,
            20,
            "SR-Bonus gegen Krankheiten",
        ),
        (
            "Luft anhalten",
            "level / 6",
            "T PF B NG DR D",
            None,
            "Zusätzliche Runden",
        ),
        ("Nagen", "level", "T B NG K U", None, "Stufe"),
        ("Schlafentzug ertragen", "3 * level", "T B NG DR D", None, "Tage"),
        ("Schmerztoleranz", "5 * level", "T PF B NG DR D EW K", None, "Stufe"),
        (
            "Schützende Stacheln",
            "6 * level",
            "T B NG DR EW K D U",
            None,
            "Stufe",
        ),
        ("Stinken", "2 + 2 * level", "T B NG DR K D U", None, "Stärke"),
        (
            "Verbesserte Traglast",
            "3 * level",
            "T B NG DR EW K D U",
            None,
            "Stufe",
        ),
        ("Vibrationen wahrnehmen", "level", "T B NG DR EW K D", None, "Bonus"),
        ("Witterung", "level", "T B NG DR EW K D", 8, "Bonus"),
    ):
        level(name, formula, cats, maximum, label=label)
    add("Würgen", 7, "T B NG DR EW K D U", page=481)
    level("Freies Angriffsmanöver", "25 * level + 5 * level * (level - 1) / 2")
    level("Freies Ausweichmanöver", "20 * level + 5 * level * (level - 1) / 2")
    add(
        "Feinere Manipulationsfähigkeit",
        "arms * mode",
        "T B",
        {
            "arms": param("Arme", 1),
            "mode": param("Greifen: 3; Feinmanipulation: 6", 3, 6, [3, 6]),
        },
    )
    add(
        "Gift / Gift injizieren",
        "power / 2",
        params={
            "power": {"label": "Berechnete Macht des Giftes", "min": 0},
        },
    )
    for name, factor in (
        ("Beweglich", 1),
        ("Manipulation", 2),
        ("Feinmanipulation", 3),
    ):
        add(
            f"Zusätzliche Arme: {name}",
            f"arms * {factor} * capacity",
            "T PF B NG DR EW K U",
            {
                "arms": param("Zusätzliche Arme", 1),
                "capacity": param(
                    "Beide Werte halbiert: 1; einer: 2; volle Werte: 3", 1, 3
                ),
            },
            page=481,
        )
    level(
        "Zusätzliche Beine",
        "3 * level",
        "T PF B NG DR EW K U",
        label="Zusätzliche Beine",
    )
    level("Altern", "25 + 5 * (level - 1)", "NG D DR U", 15, page=483)
    spells = {
        "Bezauberung": "NG DR",
        "Erdmagie": "EW_E NG DR",
        "Feuermagie": "EW_F NG DR",
        "Finsternis": "NG DR D",
        "Heilung": "NG B DR",
        "Hexerei": "NG DR",
        "Illusionsmagie": "NG DR",
        "Kampf": "NG DR B",
        "Licht": "NG DR",
        "Luftmagie": "EW_L NG DR",
        "Natur": "NG DR B PF",
        "Nekromantie": "NG DR U",
        "Reise und Bewegung": "NG DR EW_L",
        "Schutz": "NG DR",
        "Tod": "NG DR U",
        "Tücke": "NG DR",
        "Wassermagie": "EW_W NG DR",
        "Wetter": "NG DR EW",
        "Wissen": "NG DR",
    }
    for name, cats in spells.items():
        add(
            f"Angeborener Zauber: {name}",
            "5 + (4 - uses_kp) * level",
            cats,
            {
                "level": param("Berechneter Zaubergrad", 1),
                "uses_kp": param("Mit KP-Kosten: 1; ohne KP-Kosten: 0", 0, 1),
            },
            page=483,
        )
    for name, formula, cats, params, page in (
        (
            "Ätherisch",
            "30 + 20 * transform - 5 * blood",
            "EW U NG",
            {
                "transform": param(
                    "Zusätzlich körperliche Gestalt: 1; sonst: 0", 0, 1
                ),
                "blood": param(
                    "Durch Blutwaffen verletzbar: 1; sonst: 0", 0, 1
                ),
            },
            483,
        ),
        (
            "Halbätherisch",
            "25 * transform",
            "EW NG B DR K U",
            {
                "transform": param(
                    "Zusätzlich körperliche Gestalt: 1; sonst: 0", 0, 1
                ),
            },
            487,
        ),
        (
            "Aura der Alten Götter",
            "20 + 35 * all_animals",
            "NG",
            {
                "all_animals": param(
                    "Alle Tierarten: 1; eine Tierart: 0", 0, 1
                ),
            },
            483,
        ),
        (
            "Frostsphäre",
            "5 + cold + radius * 5",
            "EW_W NG",
            {
                "cold": param("Kältestärke", 1),
                "radius": param("Radius in Metern", 1),
            },
            470,
        ),
        (
            "Odemwaffe der Drachen",
            "8 * dice + 4 * (width - 1) + distance / 2",
            "DR",
            {
                "dice": param("Anzahl W10", 1),
                "width": param("Kegelbreite in Metern", 1),
                "distance": param("Reichweite in Metern", 0),
            },
            471,
        ),
        (
            "Telepath",
            "target + group * 10 + distance",
            magical,
            {
                "target": param(
                    "Ein Wesen: 5; eigene Art: 10; "
                    "bekannte Sprache: 20; alle: 30",
                    5,
                    30,
                    [5, 10, 20, 30],
                ),
                "group": param("Mehrere gleichzeitig: 1; sonst: 0", 0, 1),
                "distance": param(
                    "Berührung: 0; unter 10 m: 5; Sicht: 10; Ebene: 20",
                    0,
                    20,
                    [0, 5, 10, 20],
                ),
            },
            492,
        ),
        (
            "Unsichtbar",
            "30 + 15 * transform",
            magical,
            {
                "transform": param("Auch sichtbar möglich: 1; sonst: 0", 0, 1),
            },
            493,
        ),
    ):
        add(name, formula, cats, params, page)
    for name, cost, cats in (
        ("Aura des empathischen Gespürs", 30, "NG DR"),
        ("Benötigt keine Flüssigkeit", 15, "T B NG DR EW K D"),
        ("Benötigt keine Nahrung", 15, "B NG DR EW K D"),
        ("Benötigt keinen Schlaf", 25, "B PF NG DR EW D"),
        ("Energieimpuls", 20, "EW_L NG B"),
        ("Entflammen", 15, "EW_F"),
        ("Erze suchen", 10, "EW_E B NG"),
        ("Fliegen (ohne Flügel)", 30, "EW_L NG U B"),
        ("Flüssige Gestalt", 45, "EW_W NG"),
        ("Furchtimmunität", 15, "U DR D NG B"),
        ("Gestaltwandel", 40, "PF B NG DR K"),
        ("Götterzorn", 40, "EW_L NG B DR"),
        ("Grabesklauen", 20, "U"),
        ("Heilen des Einhorns", 80, "NG"),
        ("Hitzeimmunität", 15, "EW_F NG B U PF DR D"),
        ("Immunität gegen Wasser und Eis", 25, "EW_W NG U"),
        ("Immunität gegen Energie", 18, "EW_L NG U"),
        ("Immunität gegen Erdmagie", 22, "EW_E NG U"),
        ("Immunität gegen Feuer und Hitze", 35, "EW_F NG U"),
        ("Immunität gegen Säure", 15, "DR D NG EW U PF K B"),
        ("Immunität gegen Luftangriffe", 12, "EW_L NG U"),
        ("Immunität gegen eine Zauberart", 20, magical),
        ("Klebriges Netz der Waldspinne", 25, "NG B DR"),
        ("Mit einem Element verschmelzen", 40, "NG EW DR B"),
        ("Negative Energie", 8, "U"),
        ("Rammen der Drachen", 12, "DR"),
        ("Reinigendes Licht", 15, "NG"),
        ("Sporen", 50, "NG B PF"),
        ("Spuken", 55, "GU"),
        ("Tarnung", 15, "NG B PF DR"),
        ("Untotenfäule", 20, "U"),
        ("Windangriff der Drachen", 25, "DR"),
        ("Wyldwuchs", 25, "PF NG"),
    ):
        add(
            name,
            cost,
            cats,
            page=493 if name in ("Untotenfäule", "Wyldwuchs") else 470,
        )
    for name, formula, cats, maximum in (
        ("Aussehen", "5 * level", "NG D U B", None),
        ("Besetzen (Geister)", "20 + 4 * (level - 1)", "NG GU", None),
        ("Blitzattacke", "10 * level", "NG B", 2),
        ("Elementarbrocken schleudern", "3 + 2 * level", "NG EW", None),
        ("Fanatismus", "2 * level", "NG B DR D", 20),
        ("Furcht", "5 + 3 * level", "DR D NG B U", None),
        ("Hitzeaura", "10 + 5 * level", "EW_F NG DR", None),
        ("Kalben", "5 * level", "EW", None),
        ("Kälteimmunität", "15 + level", magical, None),
        ("Kampfschule", "8 * level", "NG DR D U", None),
        ("Magieresistenz", "3 * level", magical, None),
        ("Magieschule", "8 * level", "NG DR D U", None),
        ("Orkanwirbel", "8 * level", "EW_L NG", None),
        ("Regeneration", "6 * level", magical, None),
        ("Resistenz gegen bestimmte Zauberart", "level", magical, 20),
        ("Sirenengesang", "10 + 5 * level", "NG B DR", None),
        ("Tragen", "5 + 4 * level", "GU NG", 20),
        (
            "Zugriff auf Zauber eines Aspektes",
            "5 * level",
            "NG B PF DR D U EW",
            None,
        ),
    ):
        level(name, formula, cats, maximum, page=471)
    for name in ("Säurebiss", "Säurehaltiges Blut"):
        add(
            name,
            "power / 2",
            "NG B DR K U",
            {
                "power": {"label": "Berechnete Macht der Säure", "min": 0},
            },
            page=471,
        )
    add(
        "Schutz vor Bösem",
        25,
        "NG",
        page=471,
        requirements={"arcane_power": True},
    )
    add(
        "Immunität gegen gezielte Treffer",
        "10 * central + 5 * other",
        "EW GU KU W NG PF K D",
        {
            "central": param("Kopf und/oder Torso: Anzahl", 0, 2),
            "other": param("Andere geschützte Körperzonen: Anzahl", 0, 4),
        },
        page=471,
    )
    for name in (
        "Augen der Hölle",
        "Dämonische Seele",
        "Flammenresistenz",
        "Fleischregeneration",
        "Gefallener Engel",
        "Giftiger Schwefelodem",
        "Höllenflamme",
        "Hornwaffe",
        "Hornzunge",
        "Immunität",
        "Lederne Haut",
        "Lederne Schwingen",
        "Peitschenschwanz",
        "Schattententakel",
        "Schwarze Klauen",
        "Seelengespür",
        "Unempfindlichkeit",
        "Unheilige Aura",
        "Unheiliges Gebiss",
        "Vierbeiner",
        "Zusätzliche Gliedmaßen",
    ):
        add(f"Dämon: {name}", 10, "D", page=471)
    for name in (
        "Beflecken",
        "Fäulnisklauen",
        "Feuerschwingen",
        "Freier Angriff",
        "Giftstachel",
        "Hautwandeln",
        "Höllenfeuer",
        "Schleier der sterblichen Hülle",
        "Tarnung (dämonisch)",
        "Tentakel der Finsternis",
        "Unheilige Ausdauer",
        "Unheilige Rüstung",
    ):
        add(f"Dämon: {name}", 25, "D", page=472)
    for name in (
        "Besetzen",
        "Diabolische Leidenschaft",
        "Hass erzeugen",
        "Heimsuchung",
        "Irrsinn",
        "Markierung",
        "Seelensauger",
        "Sündengespür",
    ):
        level(f"Dämon: {name}", "25 + 3 * (level - 1)", "D", page=472)
    for name in (
        "Arkane Macht verstärken",
        "Gestaltwandeln",
        "Höllenpanzer",
        "Infernalische Feuerwaffe",
        "Unverwundbarkeit",
        "Wiedergeburt",
        "Zeitriss",
        "Zwei freie Angriffe",
    ):
        add(f"Dämon: {name}", 55, "D", page=472)
    for name in (
        "Höllenbrut beschwören",
        "Inferno",
        "Kraft verleihen",
        "Seelenfresser",
        "Seuchenmeister",
    ):
        level(f"Dämon: {name}", "55 + 5 * (level - 1)", "D", page=472)
    for name in (
        "Übernatürliche Schönheit",
        "Die Macht des Blutes",
        "Fliegen",
        "Unverwundbarkeit",
        "Kinder der Nacht befehligen",
        "Blutsinn",
        "Gestaltwandel",
        "Prinz der Finsternis",
        "Unheilige Geschwindigkeit",
        "Gefährliche Klauen",
        "Geistkontrolle",
        "Furchtbare Präsenz",
        "Sterbliche Erscheinung",
        "Aura sehen",
        "Ghulmeister",
        "Nebelgestalt",
        "Zone der Stille",
        "In der Erde versinken",
        "Rufen",
        "Schatten befehligen",
        "Unheiliges Sanctum",
        "Schattenwandeln",
        "Schattengestalt",
        "Blutraub",
        "Geistreise",
    ):
        add(f"Vampir: {name}", 20, "V", page=472)
    level(
        "Vampir: Zusätzliche Alterszyklen ohne Kraft",
        "20 * level",
        "V",
        page=472,
    )
    for name, cost, cats in (
        ("Aggressivität", -4, "T B NG DR EW K D U"),
        ("Austrocknen", -10, "T B NG DR EW K D U"),
        ("Dummheit", -10, "T B"),
        ("Hitzeempfindlichkeit", -10, "T B NG DR EW K D U"),
        ("Energieempfindlichkeit", -6, "B NG DR EW K D U"),
        ("Erdempfindlichkeit", -6, "B NG DR EW K D U"),
        ("Erstarren des Gargyls", -4, "B K"),
        ("Feuerempfindlichkeit", -10, "B NG DR EW K D U"),
        ("Frostempfindlichkeit", -6, "B NG DR EW K D U"),
        ("Luftempfindlichkeit", -6, "B NG DR EW K D U"),
        ("Metallempfindlichkeit", -25, "B NG DR EW K D U"),
        ("Wasserempfindlichkeit", -6, "B NG DR EW K D U"),
    ):
        add(name, cost, cats, page=473)
    level("Kälteempfindlichkeit", "-3 * level", "T B NG DR EW K D U", page=472)
    level("Eisenallergie", "-2 * level", "NG B", page=473)
    add(
        "Eingeschränkte Bewegungsfreiheit der Arme",
        "-3 * arms * mode",
        "T B NG DR EW K D U",
        {
            "arms": param("Betroffene Arme", 1, 2),
            "mode": param("Grobe Manipulation: 1; nur beweglich: 2", 1, 2),
        },
        page=472,
    )
    add(
        "Weniger Arme",
        "-3 * arms * capacity",
        "T B NG DR EW K D U",
        {
            "arms": param("Fehlende Arme", 1, 2),
            "capacity": param(
                "Beweglich: 1; Manipulation: 2; Feinmanipulation: 3", 1, 3
            ),
        },
        page=472,
    )
    add(
        "Weniger Beine",
        "-cost",
        "T B NG DR EW K D U",
        {
            "cost": param(
                "Ein Bein: 3; keine Beine: 6; keine Fortbewegung: 20",
                3,
                20,
                [3, 6, 20],
            ),
        },
        page=472,
    )
    # The category packages already pay for their missing arms/immaterial form.
    for row in rows:
        if row["key"] in (
            "weniger-arme",
            "eingeschrankte-bewegungsfreiheit-der-arme",
        ):
            row["requirements"]["package_conflict"] = ["T", "B", "PF"]
        if row["key"] == "atherisch":
            row["requirements"]["package_conflict"] = ["GU"]
    return rows
