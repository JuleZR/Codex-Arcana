"""Tests for automatic application version calculation."""

from django.test import SimpleTestCase

from codex_arcana.versioning import CommitDescription, Version, calculate_version


class VersionCalculationTests(SimpleTestCase):
    def test_formats_all_components_with_leading_zeroes(self):
        self.assertEqual(str(Version(0, 12, 13, 17)), "v.0.12.013-b0017")

    def test_applies_commit_type_rules_in_chronological_order(self):
        commits = [
            CommitDescription("docs: add deployment notes"),
            CommitDescription("fix: correct login redirect"),
            CommitDescription("feat: add group invitations"),
            CommitDescription("refactor: simplify invitation lookup"),
            CommitDescription("chore: update dependencies"),
        ]

        version = calculate_version(
            commits,
            base=Version(phase=0, feature=12, patch=13, build=17),
        )

        self.assertEqual(str(version), "v.0.13.001-b0022")

    def test_breaking_commit_increases_feature_not_phase(self):
        version = calculate_version(
            [CommitDescription("feat!: change group permissions")],
            base=Version(phase=0, feature=12, patch=13, build=17),
        )

        self.assertEqual(str(version), "v.0.13.000-b0018")

    def test_unknown_commit_only_increases_build(self):
        version = calculate_version(
            [CommitDescription("Update admin.py")],
            base=Version(phase=0, feature=12, patch=13, build=17),
        )

        self.assertEqual(str(version), "v.0.12.013-b0018")
