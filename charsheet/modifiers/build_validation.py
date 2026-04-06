"""Build-time validation rules for advantages and disadvantages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TraitBuildRule:
    """Validation metadata for a trait during character creation."""

    slug: str
    cp_cost: int = 0
    cp_refund: int = 0
    cp_cost_by_rank: tuple[int, ...] = ()
    cp_refund_by_rank: tuple[int, ...] = ()
    min_rank: int = 0
    max_rank: int = 1
    repeatable: bool = False
    mutually_exclusive_with: tuple[str, ...] = ()
    includes_other_disadvantages: tuple[str, ...] = ()
    exclusivity_groups: tuple[str, ...] = ()
    overlap_groups: tuple[str, ...] = ()
    cap_groups: tuple[str, ...] = ()
    creation_only: bool = True

    def total_cp_cost(self, rank: int) -> int:
        """Return cumulative CP cost for the selected rank."""
        value = int(rank)
        if value <= 0:
            return 0
        if self.cp_cost_by_rank:
            return int(sum(self.cp_cost_by_rank[:value]))
        return self.cp_cost * value

    def total_cp_refund(self, rank: int) -> int:
        """Return cumulative CP refund for the selected rank."""
        value = int(rank)
        if value <= 0:
            return 0
        if self.cp_refund_by_rank:
            return int(sum(self.cp_refund_by_rank[:value]))
        return self.cp_refund * value


@dataclass(slots=True)
class BuildValidationIssue:
    """One build validation error or warning."""

    code: str
    message: str
    related_slugs: tuple[str, ...] = ()


@dataclass(slots=True)
class CharacterBuildValidator:
    """Validate selected trait ranks against CP caps and exclusion rules."""

    rules: dict[str, TraitBuildRule]
    max_disadvantage_cp: int = 20

    def validate(self, selected_ranks: dict[str, int]) -> list[BuildValidationIssue]:
        """Return all detected issues for one build selection."""
        issues: list[BuildValidationIssue] = []
        normalized = {str(slug): int(level) for slug, level in selected_ranks.items() if int(level) > 0}
        seen_mutual_pairs: set[tuple[str, str]] = set()

        total_refund = 0
        overlap_usage: dict[str, list[str]] = {}
        for slug, rank in normalized.items():
            rule = self.rules.get(slug)
            if rule is None:
                continue
            if rank < rule.min_rank or rank > rule.max_rank:
                issues.append(
                    BuildValidationIssue(
                        code="rank_out_of_range",
                        message=f"Trait '{slug}' rank {rank} is outside the allowed range.",
                        related_slugs=(slug,),
                    )
                )
            if not rule.repeatable and rank > 1 and rule.max_rank <= 1:
                issues.append(
                    BuildValidationIssue(
                        code="not_repeatable",
                        message=f"Trait '{slug}' is not repeatable.",
                        related_slugs=(slug,),
                    )
                )
            total_refund += rule.total_cp_refund(rank)
            for other_slug in rule.mutually_exclusive_with:
                if other_slug in normalized:
                    pair = tuple(sorted((slug, other_slug)))
                    if pair in seen_mutual_pairs:
                        continue
                    seen_mutual_pairs.add(pair)
                    issues.append(
                        BuildValidationIssue(
                            code="mutually_exclusive",
                            message=f"Traits '{slug}' and '{other_slug}' are mutually exclusive.",
                            related_slugs=pair,
                        )
                    )
            for contained_slug in rule.includes_other_disadvantages:
                if contained_slug in normalized:
                    issues.append(
                        BuildValidationIssue(
                            code="included_disadvantage",
                            message=f"Trait '{contained_slug}' is already included in '{slug}'.",
                            related_slugs=(slug, contained_slug),
                        )
                    )
            for group in rule.overlap_groups:
                overlap_usage.setdefault(group, []).append(slug)

        if total_refund > self.max_disadvantage_cp:
            issues.append(
                BuildValidationIssue(
                    code="disadvantage_cap_exceeded",
                    message=f"Disadvantage CP refund exceeds the maximum of {self.max_disadvantage_cp}.",
                )
            )

        for group, slugs in overlap_usage.items():
            if len(slugs) > 1:
                issues.append(
                    BuildValidationIssue(
                        code="overlap_group_conflict",
                        message=f"Overlap group '{group}' is selected multiple times: {', '.join(sorted(slugs))}.",
                        related_slugs=tuple(sorted(slugs)),
                    )
                )
        return issues
