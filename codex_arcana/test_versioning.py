"""Tests for automatic application version calculation."""

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


class VersionCalculationTests(SimpleTestCase):
    @patch("codex_arcana.versioning.subprocess.run")
    def test_git_commands_trust_the_deployed_project_directory(self, run):
        from codex_arcana.versioning import PROJECT_ROOT, _run_git

        run.return_value.stdout = "commit-id\n"

        self.assertEqual(_run_git("rev-parse", "HEAD"), "commit-id\n")
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

    def test_formats_all_components_without_leading_zeroes(self):
        self.assertEqual(str(Version(0, 5, 13, 17)), "v.0.5.13-b17")

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

        self.assertEqual(str(version), "v.0.13.1-b22")

    def test_breaking_commit_increases_feature_not_phase(self):
        version = calculate_version(
            [CommitDescription("feat!: change group permissions")],
            base=Version(phase=0, feature=12, patch=13, build=17),
        )

        self.assertEqual(str(version), "v.0.13.0-b18")

    def test_unknown_commit_only_increases_build(self):
        version = calculate_version(
            [CommitDescription("Update admin.py")],
            base=Version(phase=0, feature=12, patch=13, build=17),
        )

        self.assertEqual(str(version), "v.0.12.13-b18")

    def test_application_version_refreshes_when_git_head_changes(self):
        commits_by_head = {
            "old-head": [CommitDescription("docs: initial state")],
            "new-head": [
                CommitDescription("docs: initial state"),
                CommitDescription("fix: refresh version"),
            ],
        }
        _version_for_git_head.cache_clear()
        self.addCleanup(_version_for_git_head.cache_clear)

        with (
            patch.dict(os.environ, {"CODEX_ARCANA_VERSION": ""}),
            patch(
                "codex_arcana.versioning._git_head",
                side_effect=["old-head", "new-head", "new-head"],
            ),
            patch(
                "codex_arcana.versioning._git_commits",
                side_effect=lambda head: commits_by_head[head],
            ) as git_commits,
        ):
            self.assertEqual(get_application_version(), "v.0.0.0-b1")
            self.assertEqual(get_application_version(), "v.0.0.1-b2")
            self.assertEqual(get_application_version(), "v.0.0.1-b2")

        self.assertEqual(git_commits.call_count, 2)

    @patch("codex_arcana.versioning._git_head")
    @patch(
        "codex_arcana.versioning._read_deployed_version",
        return_value="v.0.93.2-b336",
    )
    def test_application_uses_deployment_file_without_calling_git(
        self,
        _read_deployed_version,
        git_head,
    ):
        with patch.dict(os.environ, {"CODEX_ARCANA_VERSION": ""}):
            self.assertEqual(get_application_version(), "v.0.93.2-b336")

        git_head.assert_not_called()

    def test_writes_deployment_version_atomically(self):
        version_file = MagicMock()
        version_file.name = ".codex-arcana-version"
        temporary_file = version_file.with_name.return_value

        with (
            patch(
                "codex_arcana.versioning.DEPLOYED_VERSION_FILE",
                version_file,
            ),
            patch(
                "codex_arcana.versioning.get_git_version",
                return_value="v.0.93.2-b336",
            ),
        ):
            self.assertEqual(write_deployed_version(), "v.0.93.2-b336")

        version_file.with_name.assert_called_once_with(
            ".codex-arcana-version.tmp"
        )
        temporary_file.write_text.assert_called_once_with(
            "v.0.93.2-b336\n",
            encoding="utf-8",
        )
        temporary_file.replace.assert_called_once_with(version_file)
