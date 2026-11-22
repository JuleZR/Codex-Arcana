"""Structured damage variants from Kompendium p. 465, continued per p. 463."""


def dice(count, divisor=1):
    return {"kind": "dice", "count": count, "sides": 10, "divisor": divisor}


def constant(value):
    return {"kind": "constant", "value": value}


def expression(*terms):
    return {"kind": "sum", "terms": list(terms)}


def render_formula(formula):
    """Render expression nodes without parsing or rewriting formula text."""
    kind = formula["kind"]
    if kind == "constant":
        return str(formula["value"])
    if kind == "range":
        return f"{formula['minimum']}–{formula['maximum']}"
    if kind == "dice":
        result = f"{formula['count']}w{formula['sides']}"
        if formula["divisor"] != 1:
            result += f"/{formula['divisor']}"
        return result
    if kind == "sum":
        parts = []
        for term in formula["terms"]:
            rendered = render_formula(term)
            if parts and not (
                term["kind"] == "constant" and term["value"] < 0
            ):
                parts.append("+")
            parts.append(rendered)
        return "".join(parts)
    raise ValueError("Unbekannte Schadensformel.")


def damage_variants(level):
    """Return printed alternatives without deriving levels from formulas."""
    if not isinstance(level, int) or level < 0:
        raise ValueError(
            "Schadensstufe muss eine nichtnegative Ganzzahl sein."
        )
    if level < 5:
        formulas = {
            0: [constant(0)],
            1: [constant(1)],
            2: [
                {"kind": "range", "minimum": 1, "maximum": 2},
                expression(dice(1, 2), constant(-3)),
            ],
            3: [expression(dice(1, 2), constant(-2))],
            4: [expression(dice(1, 2), constant(-1))],
        }[level]
    elif level == 5:
        formulas = [dice(1, 2)]
    elif level in (6, 7):
        formulas = [
            expression(dice(1, 2), constant(level - 5)),
            expression(dice(1), constant(level - 8)),
        ]
    else:
        count, bonus = divmod(level - 8, 6)
        count += 1
        if bonus == 0:
            formulas = [dice(count)]
            if level == 26:
                formulas.insert(0, constant(24))
        else:
            formulas = [
                expression(dice(count), constant(bonus)),
                expression(dice(count + 1), constant(bonus - 6)),
            ]
            if bonus == 3:
                formulas.insert(0, expression(dice(count), dice(1, 2)))
    return [
        {
            "key": f"{level}:{index}",
            "formula": formula,
            "label": render_formula(formula),
        }
        for index, formula in enumerate(formulas)
    ]


def select_damage_variant(level, key=""):
    variants = damage_variants(level)
    for variant in variants:
        if variant["key"] == key:
            return variant
    # Keep the builder's previous default representation for existing drafts.
    alternate = level in (6, 7, 26) or (level >= 8 and (level - 8) % 6 == 3)
    default = 1 if alternate else 0
    return variants[default]


def validate_formula(formula):
    """Validate a bounded expression tree, never executable formula text."""

    def integer(value, minimum, maximum):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Ungültiger Zahlenwert in der Schadensformel.")

    if not isinstance(formula, dict):
        raise ValueError("Schadensformel muss strukturiert angegeben werden.")
    kind = formula.get("kind")
    if kind == "sum":
        terms = formula.get("terms")
        if not isinstance(terms, list) or not 1 <= len(terms) <= 33:
            raise ValueError("Eine Formel benötigt 1 bis 33 Bestandteile.")
        for term in terms:
            if not isinstance(term, dict) or term.get("kind") == "sum":
                raise ValueError("Verschachtelte Summen sind nicht zulässig.")
            validate_formula(term)
    elif kind == "dice":
        integer(formula.get("count"), 1, 10000)
        integer(formula.get("sides"), 2, 10000)
        integer(formula.get("divisor"), 1, 10000)
    elif kind == "constant":
        integer(formula.get("value"), -1000000, 1000000)
    elif kind == "range":
        if formula != {"kind": "range", "minimum": 1, "maximum": 2}:
            raise ValueError("Nur die Tabellenangabe 1–2 ist zulässig.")
    else:
        raise ValueError("Unbekannter Bestandteil der Schadensformel.")
    return formula


def formula_signature(formula):
    """Compare terms structurally, without expected dice values.

    Undivided dice can be combined. Divided dice remain separate because
    rounding each term is different from dividing a combined dice roll.
    """
    validate_formula(formula)
    terms = formula["terms"] if formula["kind"] == "sum" else [formula]
    whole = {}
    divided = []
    fixed = 0
    for term in terms:
        if term["kind"] == "constant":
            fixed += term["value"]
        elif term["kind"] == "dice" and term["divisor"] == 1:
            sides = term["sides"]
            whole[sides] = whole.get(sides, 0) + term["count"]
        elif term["kind"] == "dice":
            divided.append((term["count"], term["sides"], term["divisor"]))
        else:
            return ("range", term["minimum"], term["maximum"], len(terms))
    return (tuple(sorted(whole.items())), tuple(sorted(divided)), fixed)


def match_damage_level(formula):
    """Look up official formulas, including the documented continuation."""
    signature = formula_signature(formula)
    candidates = set(range(9)) | {26}
    if signature[0] != "range":
        whole, divided, fixed = signature
        count = dict(whole).get(10, 0)
        if count:
            candidates.add(8 + (count - 1) * 6 + fixed)
            candidates.add(8 + (count - 1) * 6 + 3)
    for level in sorted(candidates):
        if level < 0:
            continue
        for variant in damage_variants(level):
            try:
                candidate = formula_signature(variant["formula"])
            except ValueError:
                continue
            if candidate == signature:
                return level
    return None


def legacy_formula(attack):
    """Read the existing numeric model fields without parsing display text."""
    if attack.show_notes_as_damage:
        return None
    terms = []
    if attack.damage_dice_amount and attack.damage_dice_faces:
        divisor = (
            attack.damage_flat_bonus
            if attack.damage_flat_operator == "/"
            else 1
        )
        terms.append(
            {
                "kind": "dice",
                "count": attack.damage_dice_amount,
                "sides": attack.damage_dice_faces,
                "divisor": max(1, divisor),
            }
        )
    if attack.damage_flat_operator != "/" and attack.damage_flat_bonus:
        sign = -1 if attack.damage_flat_operator == "-" else 1
        terms.append(constant(sign * attack.damage_flat_bonus))
    return expression(*terms) if terms else constant(0)
