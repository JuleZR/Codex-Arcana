"""Tests for Codex Arcana Semantic Versioning."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from codex_arcana.versioning import (
    CommitDescription,
    Version,
    calculate_repository_version,
    calculate_version,
    get_application_version,
    write_calculated_version,
)


class VersionParsingTests(SimpleTestCase):
    def test_formats_beta_version(self):
        version = Version(
            major=0,
            minor=8,
            patch=0,
            prerelease="beta",
        )

        self.assertEqual(
            str(version),
            "0.8.0-beta",
        )

    def test_formats_stable_version(self):
        version = Version(
            major=1,
            minor=0,
            patch=0,
        )

        self.assertEqual(
            str(version),
            "1.0.0",
        )

    def test_parses_beta_version(self):
        version = Version.parse(
            "0.8.0-beta"
        )

        self.assertEqual(
            version,
            Version(
                major=0,
                minor=8,
                patch=0,
                prerelease="beta",
            ),
        )

    def test_parses_stable_version(self):
        version = Version.parse(
            "1.2.3"
        )

        self.assertEqual(
            version,
            Version(
                major=1,
                minor=2,
                patch=3,
            ),
        )

    def test_rejects_invalid_version(self):
        with self.assertRaises(ValueError):
            Version.parse(
                "v.0.8.0-b123"
            )

    def test_rejects_incomplete_version(self):
        with self.assertRaises(ValueError):
            Version.parse(
                "0.8"
            )

    def test_rejects_leading_zero(self):
        with self.assertRaises(ValueError):
            Version.parse(
                "0.08.0-beta"
            )


class VersionCalculationTests(SimpleTestCase):
    def setUp(self):
        self.beta = Version.parse(
            "0.8.0-beta"
        )

    @patch(
        "codex_arcana.versioning.subprocess.run"
    )
    def test_git_commands_trust_project_directory(
        self,
        run,
    ):
        from codex_arcana.versioning import (
            PROJECT_ROOT,
            _run_git,
        )

        run.return_value.stdout = "commit-id\n"

        self.assertEqual(
            _run_git(
                "rev-parse",
                "HEAD",
            ),
            "commit-id\n",
        )

        run.assert_called_once_with(
            [
                "git",
                "-c",
                f"safe.directory={PROJECT_ROOT}",
                "rev-parse",
                "HEAD",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

    def test_no_release_relevant_commit_keeps_version(
        self,
    ):
        commits = [
            CommitDescription(
                "docs: update README"
            ),
            CommitDescription(
                "test: extend version tests"
            ),
            CommitDescription(
                "chore: update tooling"
            ),
            CommitDescription(
                "refactor: simplify helper"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.0-beta",
        )

    def test_fix_increases_patch(self):
        commits = [
            CommitDescription(
                "fix: correct armor calculation"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.1-beta",
        )

    def test_fix_with_scope_increases_patch(self):
        commits = [
            CommitDescription(
                "fix(items): correct weapon display"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.1-beta",
        )

    def test_multiple_fixes_only_increase_patch_once(
        self,
    ):
        commits = [
            CommitDescription(
                "fix: correct armor calculation"
            ),
            CommitDescription(
                "fix: correct shield calculation"
            ),
            CommitDescription(
                "fix: correct tooltip"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.1-beta",
        )

    def test_multiple_scoped_fixes_only_increase_patch_once(
        self,
    ):
        commits = [
            CommitDescription(
                "fix(items): correct item display"
            ),
            CommitDescription(
                "fix(sheet): correct sheet display"
            ),
            CommitDescription(
                "fix(magic): correct magic display"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.1-beta",
        )

    def test_feature_increases_minor(self):
        commits = [
            CommitDescription(
                "feat: add flexible magic"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_feature_with_scope_increases_minor(self):
        commits = [
            CommitDescription(
                "feat(magic): add spell filtering"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_multiple_features_only_increase_minor_once(
        self,
    ):
        commits = [
            CommitDescription(
                "feat(items): add item feature"
            ),
            CommitDescription(
                "feat(magic): add magic feature"
            ),
            CommitDescription(
                "feat(sheet): add sheet feature"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_feature_has_priority_over_fixes(
        self,
    ):
        commits = [
            CommitDescription(
                "fix: correct armor calculation"
            ),
            CommitDescription(
                "feat: add flexible magic"
            ),
            CommitDescription(
                "fix: correct spell tooltip"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_scoped_feature_has_priority_over_scoped_fixes(
        self,
    ):
        commits = [
            CommitDescription(
                "fix(items): correct item display"
            ),
            CommitDescription(
                "feat(magic): add spell filtering"
            ),
            CommitDescription(
                "fix(sheet): correct tooltip"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_change_before_one_increases_minor(
        self,
    ):
        commits = [
            CommitDescription(
                "feat!: replace spell API"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_feature_with_scope_before_one_increases_minor(
        self,
    ):
        commits = [
            CommitDescription(
                "feat(api)!: replace spell API"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_fix_with_scope_before_one_increases_minor(
        self,
    ):
        commits = [
            CommitDescription(
                "fix(api)!: replace old API"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_change_body_before_one_increases_minor(
        self,
    ):
        commits = [
            CommitDescription(
                "refactor: replace spell API",
                (
                    "BREAKING CHANGE: "
                    "old spell API removed"
                ),
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_change_hyphen_body_is_supported(
        self,
    ):
        commits = [
            CommitDescription(
                "refactor(api): replace spell API",
                (
                    "BREAKING-CHANGE: "
                    "old spell API removed"
                ),
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_change_has_priority_over_feature_and_fix(
        self,
    ):
        commits = [
            CommitDescription(
                "fix(items): correct item display"
            ),
            CommitDescription(
                "feat(magic): add spell filtering"
            ),
            CommitDescription(
                "refactor(api)!: replace API"
            ),
        ]

        version = calculate_version(
            commits,
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.9.0-beta",
        )

    def test_breaking_change_after_one_increases_major(
        self,
    ):
        base = Version.parse(
            "1.4.2"
        )

        commits = [
            CommitDescription(
                "feat!: replace public API"
            ),
        ]

        version = calculate_version(
            commits,
            base=base,
        )

        self.assertEqual(
            str(version),
            "2.0.0",
        )

    def test_breaking_feature_with_scope_after_one_increases_major(
        self,
    ):
        base = Version.parse(
            "1.4.2"
        )

        commits = [
            CommitDescription(
                "feat(api)!: replace public API"
            ),
        ]

        version = calculate_version(
            commits,
            base=base,
        )

        self.assertEqual(
            str(version),
            "2.0.0",
        )

    def test_feature_after_one_increases_minor(
        self,
    ):
        base = Version.parse(
            "1.4.2"
        )

        version = calculate_version(
            [
                CommitDescription(
                    "feat(sheet): add new sheet panel"
                ),
            ],
            base=base,
        )

        self.assertEqual(
            str(version),
            "1.5.0",
        )

    def test_fix_after_one_increases_patch(
        self,
    ):
        base = Version.parse(
            "1.4.2"
        )

        version = calculate_version(
            [
                CommitDescription(
                    "fix(sheet): correct sheet rendering"
                ),
            ],
            base=base,
        )

        self.assertEqual(
            str(version),
            "1.4.3",
        )

    def test_unknown_commit_does_not_change_version(
        self,
    ):
        version = calculate_version(
            [
                CommitDescription(
                    "Update admin.py"
                ),
            ],
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.0-beta",
        )

    def test_commit_type_matching_is_case_insensitive(
        self,
    ):
        version = calculate_version(
            [
                CommitDescription(
                    "FIX(items): correct item display"
                ),
            ],
            base=self.beta,
        )

        self.assertEqual(
            str(version),
            "0.8.1-beta",
        )


class RepositoryVersionTests(SimpleTestCase):
    def test_repository_version_uses_commits_since_version_anchor(
        self,
    ):
        with (
            patch(
                "codex_arcana.versioning._read_declared_version",
                return_value="0.8.0-beta",
            ),
            patch(
                "codex_arcana.versioning._version_anchor",
                return_value="version-anchor",
            ) as version_anchor,
            patch(
                "codex_arcana.versioning._git_commits_since",
                return_value=[
                    CommitDescription(
                        "feat(magic): add spell filtering"
                    ),
                ],
            ) as git_commits,
        ):
            version = (
                calculate_repository_version()
            )

        self.assertEqual(
            version,
            "0.9.0-beta",
        )

        version_anchor.assert_called_once_with(
            "HEAD"
        )

        git_commits.assert_called_once_with(
            "version-anchor",
            "HEAD",
        )

    def test_repository_version_without_anchor_returns_base(
        self,
    ):
        with (
            patch(
                "codex_arcana.versioning._read_declared_version",
                return_value="0.8.0-beta",
            ),
            patch(
                "codex_arcana.versioning._version_anchor",
                return_value="",
            ),
            patch(
                "codex_arcana.versioning._git_commits_since",
            ) as git_commits,
        ):
            version = (
                calculate_repository_version()
            )

        self.assertEqual(
            version,
            "0.8.0-beta",
        )

        git_commits.assert_not_called()

    def test_repository_version_respects_custom_revision(
        self,
    ):
        with (
            patch(
                "codex_arcana.versioning._read_declared_version",
                return_value="0.8.0-beta",
            ),
            patch(
                "codex_arcana.versioning._version_anchor",
                return_value="version-anchor",
            ) as version_anchor,
            patch(
                "codex_arcana.versioning._git_commits_since",
                return_value=[
                    CommitDescription(
                        "fix(items): correct item display"
                    ),
                ],
            ) as git_commits,
        ):
            version = (
                calculate_repository_version(
                    "test-revision"
                )
            )

        self.assertEqual(
            version,
            "0.8.1-beta",
        )

        version_anchor.assert_called_once_with(
            "test-revision"
        )

        git_commits.assert_called_once_with(
            "version-anchor",
            "test-revision",
        )


class VersionPersistenceTests(SimpleTestCase):
    def test_write_calculated_version_updates_version_file(
        self,
    ):
        with TemporaryDirectory() as temp_dir:
            version_file = (
                Path(temp_dir) / "VERSION"
            )

            version_file.write_text(
                "0.8.0-beta\n",
                encoding="utf-8",
            )

            with (
                patch(
                    "codex_arcana.versioning.VERSION_FILE",
                    version_file,
                ),
                patch(
                    "codex_arcana.versioning.calculate_repository_version",
                    return_value="0.8.1-beta",
                ),
            ):
                version, changed = (
                    write_calculated_version()
                )

            self.assertEqual(
                version,
                "0.8.1-beta",
            )

            self.assertTrue(
                changed
            )

            self.assertEqual(
                version_file.read_text(
                    encoding="utf-8"
                ),
                "0.8.1-beta\n",
            )

            self.assertFalse(
                (
                    Path(temp_dir)
                    / "VERSION.tmp"
                ).exists()
            )

    def test_write_calculated_version_does_not_rewrite_unchanged_version(
        self,
    ):
        with TemporaryDirectory() as temp_dir:
            version_file = (
                Path(temp_dir) / "VERSION"
            )

            version_file.write_text(
                "0.8.1-beta\n",
                encoding="utf-8",
            )

            with (
                patch(
                    "codex_arcana.versioning.VERSION_FILE",
                    version_file,
                ),
                patch(
                    "codex_arcana.versioning.calculate_repository_version",
                    return_value="0.8.1-beta",
                ),
            ):
                version, changed = (
                    write_calculated_version()
                )

            self.assertEqual(
                version,
                "0.8.1-beta",
            )

            self.assertFalse(
                changed
            )

            self.assertEqual(
                version_file.read_text(
                    encoding="utf-8"
                ),
                "0.8.1-beta\n",
            )

    def test_invalid_calculated_version_is_not_written(
        self,
    ):
        with TemporaryDirectory() as temp_dir:
            version_file = (
                Path(temp_dir) / "VERSION"
            )

            version_file.write_text(
                "0.8.0-beta\n",
                encoding="utf-8",
            )

            with (
                patch(
                    "codex_arcana.versioning.VERSION_FILE",
                    version_file,
                ),
                patch(
                    "codex_arcana.versioning.calculate_repository_version",
                    return_value="invalid",
                ),
            ):
                with self.assertRaises(
                    ValueError
                ):
                    write_calculated_version()

            self.assertEqual(
                version_file.read_text(
                    encoding="utf-8"
                ),
                "0.8.0-beta\n",
            )


class ApplicationVersionTests(SimpleTestCase):
    @patch(
        "codex_arcana.versioning._read_declared_version",
        return_value="0.8.4-beta",
    )
    def test_application_version_reads_version_file(
        self,
        _read_declared_version,
    ):
        self.assertEqual(
            get_application_version(),
            "0.8.4-beta",
        )

    @patch(
        "codex_arcana.versioning._read_declared_version",
        return_value="1.3.7",
    )
    def test_application_version_reads_stable_version(
        self,
        _read_declared_version,
    ):
        self.assertEqual(
            get_application_version(),
            "1.3.7",
        )

    @patch(
        "codex_arcana.versioning._read_declared_version",
        return_value="invalid",
    )
    def test_application_version_uses_fallback_for_invalid_version(
        self,
        _read_declared_version,
    ):
        self.assertEqual(
            get_application_version(),
            "0.8.0-beta",
        )