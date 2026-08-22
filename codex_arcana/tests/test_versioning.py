"""Tests for Codex Arcana Semantic Versioning."""

import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from codex_arcana.versioning import (
    CommitDescription,
    Version,
    _version_for_git_head,
    calculate_version,
    get_application_version,
    write_deployed_version,
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
            timeout=5,
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

    def test_breaking_change_body_before_one_increases_minor(
        self,
    ):
        commits = [
            CommitDescription(
                "refactor: replace spell API",
                "BREAKING CHANGE: old spell API removed",
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

    def test_feature_after_one_increases_minor(
        self,
    ):
        base = Version.parse(
            "1.4.2"
        )

        version = calculate_version(
            [
                CommitDescription(
                    "feat: add new sheet panel"
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
                    "fix: correct sheet rendering"
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


class ApplicationVersionTests(SimpleTestCase):
    def tearDown(self):
        _version_for_git_head.cache_clear()

    def test_application_version_refreshes_when_head_changes(
        self,
    ):
        commits_by_head = {
            "old-head": [],
            "new-head": [
                CommitDescription(
                    "fix: refresh version"
                ),
            ],
        }

        with (
            patch.dict(
                os.environ,
                {
                    "CODEX_ARCANA_VERSION": "",
                },
            ),
            patch(
                "codex_arcana.versioning._read_deployed_version",
                return_value="",
            ),
            patch(
                "codex_arcana.versioning._read_declared_version",
                return_value="0.8.0-beta",
            ),
            patch(
                "codex_arcana.versioning._git_head",
                side_effect=[
                    "old-head",
                    "new-head",
                    "new-head",
                ],
            ),
            patch(
                "codex_arcana.versioning._version_anchor",
                return_value="version-anchor",
            ),
            patch(
                "codex_arcana.versioning._git_commits_since",
                side_effect=lambda _anchor, head: commits_by_head[head],
            ) as git_commits,
        ):
            self.assertEqual(
                get_application_version(),
                "0.8.0-beta",
            )

            self.assertEqual(
                get_application_version(),
                "0.8.1-beta",
            )

            self.assertEqual(
                get_application_version(),
                "0.8.1-beta",
            )

        self.assertEqual(
            git_commits.call_count,
            2,
        )

    @patch(
        "codex_arcana.versioning._git_head"
    )
    @patch(
        "codex_arcana.versioning._read_deployed_version",
        return_value="0.8.1-beta",
    )
    def test_application_uses_deployment_file_without_git(
        self,
        _read_deployed_version,
        git_head,
    ):
        with patch.dict(
            os.environ,
            {
                "CODEX_ARCANA_VERSION": "",
            },
        ):
            self.assertEqual(
                get_application_version(),
                "0.8.1-beta",
            )

        git_head.assert_not_called()

    @patch(
        "codex_arcana.versioning._read_deployed_version",
        return_value="",
    )
    def test_environment_override_has_priority(
        self,
        _read_deployed_version,
    ):
        with patch.dict(
            os.environ,
            {
                "CODEX_ARCANA_VERSION": "0.9.0-beta",
            },
        ):
            self.assertEqual(
                get_application_version(),
                "0.9.0-beta",
            )

    def test_writes_deployment_version_atomically(
        self,
    ):
        version_file = MagicMock()

        version_file.name = (
            ".codex-arcana-version"
        )

        temporary_file = (
            version_file.with_name.return_value
        )

        with (
            patch(
                "codex_arcana.versioning.DEPLOYED_VERSION_FILE",
                version_file,
            ),
            patch(
                "codex_arcana.versioning.get_git_version",
                return_value="0.8.1-beta",
            ),
        ):
            self.assertEqual(
                write_deployed_version(),
                "0.8.1-beta",
            )

        version_file.with_name.assert_called_once_with(
            ".codex-arcana-version.tmp"
        )

        temporary_file.write_text.assert_called_once_with(
            "0.8.1-beta\n",
            encoding="utf-8",
        )

        temporary_file.replace.assert_called_once_with(
            version_file
        )
