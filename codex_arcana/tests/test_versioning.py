"""Tests for Codex Arcana semantic version calculation."""

from __future__ import annotations

import unittest

from codex_arcana.versioning import (
    CommitDescription,
    Version,
    calculate_version,
)


class VersionCalculationTests(unittest.TestCase):
    def test_manual_marker_sets_exact_version(self):
        result = calculate_version(
            [
                CommitDescription("feat: earlier feature"),
                CommitDescription(
                    "chore(release): enter release candidate [v:1.0.0-rc]"
                ),
            ],
            base=Version.parse("0.27.0-beta"),
        )

        self.assertEqual(str(result), "1.0.0-rc")

    def test_commits_before_manual_marker_are_ignored(self):
        result = calculate_version(
            [
                CommitDescription("feat: earlier feature"),
                CommitDescription("fix: earlier fix"),
                CommitDescription(
                    "chore(release): reset line",
                    body="[v:1.0.0-rc]",
                ),
            ],
            base=Version.parse("0.27.0-beta"),
        )

        self.assertEqual(str(result), "1.0.0-rc")

    def test_fix_after_manual_marker_bumps_patch(self):
        result = calculate_version(
            [
                CommitDescription(
                    "chore(release): enter release candidate [v:1.0.0-rc]"
                ),
                CommitDescription("fix: release candidate regression"),
            ],
            base=Version.parse("0.27.0-beta"),
        )

        self.assertEqual(str(result), "1.0.1-rc")

    def test_feature_after_manual_marker_bumps_minor(self):
        result = calculate_version(
            [
                CommitDescription(
                    "chore(release): enter release candidate [v:1.0.0-rc]"
                ),
                CommitDescription("feat: add another capability"),
            ],
            base=Version.parse("0.27.0-beta"),
        )

        self.assertEqual(str(result), "1.1.0-rc")

    def test_latest_manual_marker_wins(self):
        result = calculate_version(
            [
                CommitDescription("chore: first anchor [v:0.30.0-beta]"),
                CommitDescription("feat: ignored by later anchor"),
                CommitDescription("chore: final anchor [v:1.0.0-rc]"),
                CommitDescription("fix: counted after final anchor"),
            ],
            base=Version.parse("0.27.0-beta"),
        )

        self.assertEqual(str(result), "1.0.1-rc")

    def test_stable_manual_marker_removes_prerelease(self):
        result = calculate_version(
            [
                CommitDescription("chore(release): stable [v:1.0.0]"),
                CommitDescription("fix: post-release fix"),
            ],
            base=Version.parse("1.0.0-rc"),
        )

        self.assertEqual(str(result), "1.0.1")

    def test_invalid_manual_marker_fails_validation(self):
        with self.assertRaises(ValueError):
            calculate_version(
                [
                    CommitDescription("chore(release): bad [v:not-a-version]"),
                ],
                base=Version.parse("0.27.0-beta"),
            )


if __name__ == "__main__":
    unittest.main()
