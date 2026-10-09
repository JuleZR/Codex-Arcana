"""Integer calendar arithmetic on a shared day axis, including year zero."""

from itertools import combinations
from math import gcd

from django.core.exceptions import ValidationError


def intersect(left, right):
    """Intersect two periodic residue classes using the generalized CRT."""
    a, p = left
    b, q = right
    common = gcd(p, q)
    if (b - a) % common:
        return None
    reduced = q // common
    step = ((b - a) // common * pow(p // common, -1, reduced)) % reduced
    period = p * reduced
    return (a + p * step) % period, period


def leap_terms(period, offset, exceptions):
    """Base rule minus excluded years, with inclusion taking precedence."""
    excluded = [(o, p) for effect, o, p in exceptions if effect == "exclude"]
    included = [(o, p) for effect, o, p in exceptions if effect == "include"]
    terms = [(1, (offset, period))]
    for size in range(1, len(excluded) + 1):
        for subset in combinations(excluded, size):
            for restore_size in range(len(included) + 1):
                for restores in combinations(included, restore_size):
                    residue = (offset, period)
                    for exception in subset + restores:
                        residue = intersect(residue, exception)
                        if residue is None:
                            break
                    if residue is not None:
                        terms.append(((-1) ** (size + restore_size), residue))
    return terms


def rule_applies(year, period, offset, exceptions):
    if (year - offset) % period:
        return False
    matches = {effect for effect, o, p in exceptions if (year - o) % p == 0}
    return "exclude" not in matches or "include" in matches


class CalendarEngine:
    def __init__(self):
        self.structures = {}
        self.offsets = {}

    def validate_real_date_calendar(self, calendar):
        """Validate only the explicitly designated Gregorian clock bridge."""
        months, rules = self.structure(calendar)
        normal = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        valid = [month.days for month in months] == normal
        for rule, exceptions, _ in rules:
            valid = valid and 400 % rule.period == 0
            valid = valid and all(
                400 % period == 0 for _, _, period in exceptions
            )
        if valid:
            for year in range(400):
                expected = normal.copy()
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    expected[1] += 1
                if self.month_lengths(calendar, year) != expected:
                    valid = False
                    break
        if not valid:
            raise ValidationError(
                {
                    "real_date_reference": "Die reale Bezugszeitrechnung "
                    "benötigt "
                    "einen gregorianischen Kalender mit korrekter "
                    "4-/100-/400-Jahresregel.",
                }
            )

    def structure(self, calendar):
        if calendar.pk not in self.structures:
            months = calendar.validate_structure()
            rules = []
            for rule in calendar.leap_rules.prefetch_related("exceptions"):
                exceptions = [
                    (e.effect, e.offset, e.period)
                    for e in rule.exceptions.all()
                ]
                terms = leap_terms(rule.period, rule.offset, exceptions)
                rules.append((rule, exceptions, terms))
            self.structures[calendar.pk] = (months, rules)
        return self.structures[calendar.pk]

    def year_start(self, calendar, year):
        _, rules = self.structure(calendar)
        total = year * calendar.days_per_year
        for rule, _, terms in rules:
            for sign, (offset, period) in terms:
                count = (year - 1 - offset) // period - (-1 - offset) // period
                total += sign * count * rule.added_days
        return total

    def month_lengths(self, calendar, year):
        months, rules = self.structure(calendar)
        lengths = {month.pk: month.days for month in months}
        for rule, exceptions, _ in rules:
            if rule_applies(year, rule.period, rule.offset, exceptions):
                lengths[rule.month_id] += rule.added_days
        return [lengths[month.pk] for month in months]

    def local_day(self, calendar, year, month, day):
        if any(type(value) is not int for value in (year, month, day)):
            raise ValidationError(
                "Jahr, Monat und Tag müssen Ganzzahlen sein."
            )
        lengths = self.month_lengths(calendar, year)
        if not 1 <= month <= len(lengths):
            raise ValidationError(
                "Der gewählte Monat existiert nicht " "in diesem Kalender."
            )
        if not 1 <= day <= lengths[month - 1]:
            raise ValidationError(
                f"Das gewählte Datum existiert in diesem Kalender nicht. "
                f"Dieser Monat hat im Jahr {year} {lengths[month - 1]} Tage."
            )
        return (
            self.year_start(calendar, year)
            + sum(lengths[: month - 1])
            + day
            - 1
        )

    def local_date(self, calendar, absolute):
        guess = absolute // calendar.days_per_year
        low, high = min(0, guess), max(1, guess + 1)
        while self.year_start(calendar, low) > absolute:
            low = low * 2 - 1
        while self.year_start(calendar, high) <= absolute:
            high = high * 2 + 1
        while high - low > 1:
            middle = (low + high) // 2
            if self.year_start(calendar, middle) <= absolute:
                low = middle
            else:
                high = middle
        day = absolute - self.year_start(calendar, low)
        for month, length in enumerate(self.month_lengths(calendar, low), 1):
            if day < length:
                return low, month, day + 1
            day -= length
        raise ValidationError("Ungültige Kalenderstruktur.")

    def system_offset(self, system):
        pending, seen = [], set()
        current = system
        while current.pk not in self.offsets:
            if current.pk in seen:
                raise ValidationError(
                    "Die Bezugszeitrechnungen bilden "
                    "einen ungültigen Verweiskreis."
                )
            seen.add(current.pk)
            self.structure(current.calendar_definition)
            if not current.reference_system_id:
                self.offsets[current.pk] = -current.root_origin_day
                break
            pending.append(current)
            current = current.reference_system
        for child in reversed(pending):
            reference = child.reference_system
            reference_day = self.local_day(
                reference.calendar_definition,
                child.reference_year,
                child.reference_month,
                child.reference_day,
            )
            anchor_day = self.local_day(
                child.calendar_definition,
                child.anchor_year,
                child.anchor_month,
                child.anchor_day,
            )
            self.offsets[child.pk] = (
                self.offsets[reference.pk] + reference_day - anchor_day
            )
        return self.offsets[system.pk]

    def to_absolute(self, system, year, month, day):
        return self.system_offset(system) + self.local_day(
            system.calendar_definition, year, month, day
        )

    def from_absolute(self, system, absolute_day):
        if type(absolute_day) is not int:
            raise ValidationError(
                "Die absolute Tageszahl muss eine Ganzzahl sein."
            )
        return self.local_date(
            system.calendar_definition,
            absolute_day - self.system_offset(system),
        )

    def convert(self, source, target, year, month, day):
        return self.from_absolute(
            target, self.to_absolute(source, year, month, day)
        )
