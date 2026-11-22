"""Exact creature creation costs (Kompendium, chapter 16, pp. 457-498).

Movement deliberately follows p. 467, including the final division by two.
The abbreviated formula on p. 498 omits that division. Inputs are base template
values, never the current values of a trained, injured or modified instance.
"""

import ast
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from charsheet.constants import LANGUAGE_LITERACY_MIN_LEVEL

CATEGORIES = {
    "T": ("Tiere", -12),
    "PF": ("Pflanzen", -58),
    "B": ("Bestien", -12),
    "NG": ("Naturgeister", 0),
    "DR": ("Drachen", 0),
    "EW": ("Elementarwesen", 0),
    "K": ("Konstrukte", 0),
    "D": ("Dämonen", 0),
    "W": ("Wiedergänger", 15),
    "KU": ("Körperliche Untote", 15),
    "GU": ("Geisterhafte Untote", 40),
    "V": ("Vampire", 60),
    "SC": ("Spielerrassen", 0),
}
CATEGORY_TYPES = {
    "T": ("tier", "Tier"),
    "PF": ("pflanze", "Pflanze"),
    "B": ("bestie", "Bestie"),
    "NG": ("naturgeist", "Naturgeist"),
    "DR": ("drache", "Drache"),
    "EW": ("elementarwesen", "Elementarwesen"),
    "K": ("konstrukt", "Konstrukt"),
    "D": ("damon", "Dämon"),
    "W": ("untoter", "Untoter"),
    "KU": ("untoter", "Untoter"),
    "GU": ("untoter", "Untoter"),
    "V": ("vampir", "Vampir"),
    "SC": ("spielerrasse", "Spielerrasse"),
}
SIZE_MODIFIERS = {
    "S": 8,
    "F": 4,
    "W": 2,
    "K": 1,
    "M": 0,
    "G": -1,
    "R": -2,
    "Gi": -4,
    "Kol": -8,
}
STRENGTH_LIMITS = {
    "S": (-125, -20),
    "F": (-61, -4),
    "W": (-29, 4),
    "K": (-13, 8),
    "M": (-5, 10),
    "G": (-3, 18),
    "R": (1, 34),
    "Gi": (9, 66),
    "Kol": (25, 130),
}
STEPS = (
    "Kategorie",
    "Name",
    "Größe",
    "Eigenschaften",
    "Initiative",
    "Angriff",
    "Schaden",
    "Widerstandswerte",
    "Rüstungsschutz",
    "Lebenspunkte",
    "Bewegungsweite",
    "Fertigkeiten",
    "Besondere Fähigkeiten und Nachteile",
    "Arkane Macht",
)
ATTRIBUTE_CODES = ("ST", "KON", "GE", "INT", "WA", "WILL", "CHA")


def number(value):
    """Keep exact decimals; reject missing, non-finite and boolean values."""
    if value is None or isinstance(value, bool):
        raise ValueError("Zahlenwert fehlt.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Ungültiger Zahlenwert.") from exc
    if not result.is_finite():
        raise ValueError("Zahlenwert muss endlich sein.")
    return result


def formula_value(formula, parameters):
    """Evaluate arithmetic without eval, calls, attributes or subscripts."""
    if not isinstance(formula, str) or len(formula) > 1000:
        raise ValueError("Ungültige Kostenformel.")
    try:
        tree = ast.parse(formula, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Ungültige Kostenformel.") from exc
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("Kostenformel ist zu komplex.")

    def visit(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise ValueError("Boolesche Werte sind keine Machtkosten.")
            if isinstance(node.value, (int, float)):
                return number(ast.get_source_segment(formula, node))
            raise ValueError("Konstanten müssen Zahlen sein.")
        if isinstance(node, ast.Name):
            if node.id not in parameters:
                raise ValueError(f"Parameter {node.id} fehlt.")
            return number(parameters[node.id])
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return visit(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div) and right:
                return left / right
        raise ValueError("Nur +, -, *, / und benannte Parameter sind erlaubt.")

    return visit(tree.body)


@dataclass(frozen=True)
class PowerResult:
    costs: dict
    errors: dict
    derived: dict

    @property
    def complete(self):
        return not self.errors and len(self.costs) == 14

    @property
    def total(self):
        return sum(self.costs.values(), Decimal(0)) if self.complete else None

    @property
    def subtotal(self):
        return sum(self.costs.values(), Decimal(0))

    def as_dict(self):
        return {
            "complete": self.complete,
            "total": str(self.total) if self.total is not None else None,
            "subtotal": str(self.subtotal),
            "steps": [
                {
                    "step": step,
                    "label": label,
                    "cost": (
                        str(self.costs[step]) if step in self.costs else None
                    ),
                    "error": self.errors.get(step, ""),
                }
                for step, label in enumerate(STEPS, 1)
            ],
            "derived": {
                key: str(value) for key, value in self.derived.items()
            },
        }


class CreaturePowerCalculator:
    """Calculate all fourteen steps from explicit creation inputs.

    Damage levels are the official levels from p. 465, not average dice damage.
    Ability rows contain database definitions plus their selected parameters;
    semantic effects are deliberately not counted as separate purchases.
    """

    def __init__(self, data):
        self.data = data
        self.derived = {}

    def calculate(self):
        costs, errors = {}, {}
        for step in range(1, 15):
            try:
                costs[step] = number(getattr(self, f"step_{step}")())
            except KeyError:
                errors[step] = "Regelangaben dieses Schrittes fehlen."
            except (ValueError, TypeError, ArithmeticError) as exc:
                errors[step] = str(exc) or "Regelangaben fehlen."
        return PowerResult(costs, errors, self.derived)

    def attr(self, code):
        # An explicitly absent attribute (dash) costs as -5, p. 462.
        value = self.data["attributes"][code]
        return Decimal(-5) if value is None else number(value)

    def size(self):
        return SIZE_MODIFIERS[self.data["size_class"]]

    def step_1(self):
        return CATEGORIES[self.data["category"]][1]

    def step_2(self):
        if not str(self.data.get("name", "")).strip():
            raise ValueError("Name fehlt.")
        return 0

    def step_3(self):
        low, high = STRENGTH_LIMITS[self.data["size_class"]]
        if not self.data.get("magical_strength") and "ST" in self.data.get(
            "attributes", {}
        ):
            if not low <= self.attr("ST") <= high:
                raise ValueError(
                    f"Natürliche Stärke muss in {low} bis {high} liegen."
                )
        self.derived["size_modifier"] = self.size()
        return self.size() * 10

    def step_4(self):
        return (
            sum((self.attr(code) for code in ATTRIBUTE_CODES), Decimal(0)) * 10
        )

    def effective(self, key, base):
        value = self.data.get(key)
        result = base if value is None or value == "" else number(value)
        self.derived[key] = result
        return result

    def stat_base(self, key):
        if key == "initiative":
            return self.attr("WA")
        attributes = {
            "vw": ("WA", "GE"),
            "sr": ("ST", "KON"),
            "gw": ("INT", "WA"),
        }
        result = 14 + sum(self.attr(code) for code in attributes[key])
        return result + self.size() if key == "vw" else result

    def step_5(self):
        base = self.stat_base("initiative")
        return (self.effective("initiative", base) - base) * 3

    def step_6(self):
        attacks = self.data["attacks"]
        if not attacks:
            return 0
        base = self.attr("GE") + self.size()
        values = sorted(
            (number(row["attack_value"]) for row in attacks), reverse=True
        )
        for index, row in enumerate(attacks, 1):
            self.derived[f"attack_{index}"] = number(row["attack_value"])
        difference = values[0] - base
        if self.data.get("general_attack"):
            if any(value != values[0] for value in values):
                raise ValueError(
                    "Genereller Angriffswert muss für alle Angriffe "
                    "gleich sein."
                )
            return difference * (8 if difference > 0 else 4)
        primary = max(
            range(len(attacks)),
            key=lambda index: number(attacks[index]["attack_value"]),
        )
        for index, row in enumerate(attacks):
            deviation = number(row["attack_value"]) - base
            self.derived[f"attack_cost_{index + 1}"] = (
                deviation * 4 if index == primary else max(0, deviation)
            )
        return difference * 4 + sum(
            max(0, value - base) for value in values[1:]
        )

    def step_7(self):
        attacks = self.data["attacks"]
        if not attacks:
            return 0
        levels = [number(row["damage_level"]) for row in attacks]
        for index, level in enumerate(levels, 1):
            self.derived[f"damage_{index}"] = level
        if any(level < 0 or level != int(level) for level in levels):
            raise ValueError("Schadensstufen müssen ganze Zahlen ab 0 sein.")
        primary = max(range(len(levels)), key=levels.__getitem__)
        base = max(0, self.attr("ST") + 5)
        ethereal = any(
            row.get("key") == "atherisch"
            for row in self.data.get("abilities", [])
        )
        total = Decimal(0)
        for index, (row, level) in enumerate(zip(attacks, levels)):
            if ethereal:
                cost = level * 4
            else:
                cost = (
                    (level - base) * 3
                    if index == primary
                    else max(0, level - base)
                )
            kind = row.get("damage_kind", "physical")
            if kind == "energy":
                cost *= 2
            elif kind == "fire":
                cost *= Decimal("1.25")
            elif kind not in ("physical", "acid"):
                raise ValueError("Unbekannte Schadensart.")
            if kind == "acid":
                cost += number(row["acid_power"]) / 2
            total += cost + number(row.get("short_range", 0))
            total += number(row.get("extra_damage_types", 0)) * 3
            self.derived[f"damage_cost_{index + 1}"] = (
                cost
                + number(row.get("short_range", 0))
                + number(row.get("extra_damage_types", 0)) * 3
            )
        return total

    def step_8(self):
        bases = {key: self.stat_base(key) for key in ("vw", "sr", "gw")}
        return sum(
            (self.effective(key, base) - base) * 5
            for key, base in bases.items()
        )

    def step_9(self):
        rs = number(self.data["natural_rs"])
        if not 0 <= rs <= 50:
            raise ValueError("Natürlicher RS muss zwischen 0 und 50 liegen.")
        return rs * 6

    def step_10(self):
        constitution = max(1, self.attr("KON") + 5)
        zones = self.data.get("wound_zones")
        if zones is None:
            step = self.effective("wound_step", constitution)
            zones = [step] * 6
        if len(zones) != 6 or any(number(value) < 0 for value in zones):
            raise ValueError(
                "Sechs nichtnegative LP-Wundgrade sind erforderlich."
            )
        if self.data.get("category") in ("W", "KU", "GU", "V") or any(
            row.get("key") == "damon-damonische-seele"
            for row in self.data.get("abilities", [])
        ):
            # These packages ignore pain and incapacitation. Moving their
            # existing LP into a single pool is part of the package, p. 466.
            return sum(map(number, zones)) - constitution * 6
        weights = (2, 1, 1, 1, Decimal("0.5"), Decimal("0.5"))
        return sum(
            (number(value) - constitution) * weight
            for value, weight in zip(zones, weights)
        )

    def step_11(self):
        total = Decimal(0)
        for mode in ("ground", "swim", "fly"):
            values = self.data["movement"].get(mode)
            if values is None:
                continue
            if len(values) == 1:
                sprint = number(values[0])
                values = (sprint / 8, sprint / 4, sprint)
            if len(values) != 3:
                raise ValueError(
                    "Bewegungsart muss vollständig angegeben sein."
                )
            combat, march, sprint = map(number, values)
            if min(combat, march, sprint) < 0:
                raise ValueError("Bewegungsweiten dürfen nicht negativ sein.")
            total += combat * 4 + march + sprint / 4
        return (total - 36) / 2

    def step_12(self):
        free = self.data.get("free_survival_count", 0)
        if free > 1:
            raise ValueError(
                "Nur eine natürliche Überlebensfertigkeit ist frei."
            )
        if free and not self.data.get("natural_survival_eligible", False):
            raise ValueError(
                "Diese Kategorie hat keinen Anspruch auf eine natürliche "
                "Überlebensfertigkeit."
            )
        levels = [number(row["paid_level"]) for row in self.data["skills"]]
        if any(value < 0 for value in levels):
            raise ValueError(
                "Gekaufte Fertigkeitsstufen dürfen nicht negativ sein."
            )
        languages = self.data.get("languages", [])
        language_cost = Decimal(0)
        for row in languages:
            level = number(row["levels"])
            if level < 1 or level != int(level):
                raise ValueError("Sprachstufen müssen ganze Zahlen ab 1 sein.")
            if row.get("can_write") and level < LANGUAGE_LITERACY_MIN_LEVEL:
                raise ValueError("Lesen und Schreiben benötigt Sprachstufe 3.")
            language_cost += level + bool(row.get("can_write"))
        return sum(levels, Decimal(0)) + language_cost - 30

    def step_13(self):
        category = self.data["category"]
        selections = self.data["abilities"]
        selected = {str(row["key"]) for row in selections}
        seen, total = set(), Decimal(0)
        vampire_powers = 0
        for row in selections:
            key = str(row["key"])
            if key in seen:
                raise ValueError("Fähigkeit mehrfach ausgewählt.")
            seen.add(key)
            allowed = row["categories"]
            category_keys = {category}
            if category in ("W", "KU", "GU", "V"):
                category_keys.add("U")
            if category == "EW":
                category_keys.add(f"EW_{self.data.get('element', '')}")
            if allowed and not category_keys.intersection(allowed):
                raise ValueError(f"{row['name']}: Kategorie nicht zulässig.")
            requires = row.get("requires", {})
            if category in requires.get("package_conflict", []):
                raise ValueError(
                    f"{row['name']}: bereits im Grundpaket enthalten."
                )
            if not set(requires.get("abilities", [])).issubset(selected):
                raise ValueError(f"{row['name']}: Voraussetzung fehlt.")
            if set(requires.get("excludes", [])).intersection(selected):
                raise ValueError(
                    f"{row['name']}: widersprüchliche Fähigkeiten."
                )
            if requires.get("arcane_power"):
                self.step_14()
                if not self.derived["arcane_power"]:
                    raise ValueError(
                        f"{row['name']}: Arkane Macht erforderlich."
                    )
            parameters = row.get("parameters", {})
            for name, bounds in row.get("parameter_schema", {}).items():
                value = number(parameters.get(name))
                if "min" in bounds and value < number(bounds["min"]):
                    raise ValueError(f"{row['name']}: {name} ist zu klein.")
                if "max" in bounds and value > number(bounds["max"]):
                    raise ValueError(f"{row['name']}: {name} ist zu groß.")
                if bounds.get("integer") and value != int(value):
                    raise ValueError(
                        f"{row['name']}: {name} muss ganzzahlig sein."
                    )
                if "choices" in bounds and value not in map(
                    number, bounds["choices"]
                ):
                    raise ValueError(
                        f"{row['name']}: ungültige Variante für {name}."
                    )
            total += formula_value(row["formula"], parameters)
            if (
                category == "V"
                and row["key"].startswith("vampir-")
                and row["key"] != "vampir-zusatzliche-alterszyklen-ohne-kraft"
            ):
                vampire_powers += 1
        if category == "V":
            if not vampire_powers:
                raise ValueError(
                    "Erste Vampirkraft des Grundpakets auswählen."
                )
            total -= 20  # One vampire power is included in the 60 MP package.
        return total

    def step_14(self):
        will = max(0, self.attr("WILL") + 5)
        schools = number(self.data.get("school_levels", 0))
        base = will + schools
        power = self.effective("arcane_power", base)
        if power < 0:
            raise ValueError("Arkane Macht darf nicht negativ sein.")
        self.effective("potential", will // 2)
        return (power - base) * 3
