"""Semantic Versioning for Codex Arcana.

VERSION is the canonical application version.

The next version is calculated from Conventional Commits made since the
most recent commit that changed VERSION.

Rules:

- BREAKING CHANGE:
    - before 1.0.0 -> next minor version
    - from 1.0.0 onward -> next major version
- feat -> next minor version
- fix -> next patch version
- all other commit types -> no automatic version change

Commit scopes are supported, e.g.:

    fix(items): ...
    feat(magic): ...
    feat(api)!: ...
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent.parent

VERSION_FILE = PROJECT_ROOT / "VERSION"

FALLBACK_VERSION = "0.8.0-beta"


_SEMVER_PATTERN = re.compile(
    r"""
    ^
    (?P<major>0|[1-9]\d*)
    \.
    (?P<minor>0|[1-9]\d*)
    \.
    (?P<patch>0|[1-9]\d*)
    (?:
        -
        (?P<prerelease>[0-9A-Za-z.-]+)
    )?
    $
    """,
    re.VERBOSE,
)


_COMMIT_TYPE_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?:",
    re.IGNORECASE,
)


_BREAKING_CHANGE_PATTERN = re.compile(
    r"(?:^|\n)BREAKING(?: |-)?CHANGE\s*:",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CommitDescription:
    """Commit information required for version classification."""

    subject: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class Version:
    """Semantic Versioning version."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"

        if self.prerelease:
            version = f"{version}-{self.prerelease}"

        return version

    @classmethod
    def parse(cls, value: str) -> "Version":
        """Parse a strict SemVer-style project version."""

        normalized = value.strip()

        match = _SEMVER_PATTERN.fullmatch(normalized)

        if not match:
            raise ValueError(
                f"Invalid Codex Arcana version: {value!r}"
            )

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=match.group("prerelease"),
        )


def _commit_is_breaking(
    commit: CommitDescription,
) -> bool:
    """Return whether a Conventional Commit declares a breaking change."""

    match = _COMMIT_TYPE_PATTERN.match(
        commit.subject.strip()
    )

    if match and match.group("breaking"):
        return True

    return bool(
        _BREAKING_CHANGE_PATTERN.search(
            commit.body
        )
    )


def _commit_type(
    commit: CommitDescription,
) -> str:
    """Return the Conventional Commit type."""

    match = _COMMIT_TYPE_PATTERN.match(
        commit.subject.strip()
    )

    if not match:
        return ""

    return match.group("type").lower()


def calculate_version(
    commits: list[CommitDescription],
    *,
    base: Version,
) -> Version:
    """Calculate the next semantic version candidate.

    All commits since the most recent VERSION update are evaluated
    together.

    Multiple commits of the same class therefore only increase the
    version once.

    Priority:

        BREAKING CHANGE > feat > fix
    """

    has_breaking_change = any(
        _commit_is_breaking(commit)
        for commit in commits
    )

    has_feature = any(
        _commit_type(commit) == "feat"
        for commit in commits
    )

    has_fix = any(
        _commit_type(commit) == "fix"
        for commit in commits
    )

    if has_breaking_change:
        if base.major == 0:
            return Version(
                major=0,
                minor=base.minor + 1,
                patch=0,
                prerelease=base.prerelease,
            )

        return Version(
            major=base.major + 1,
            minor=0,
            patch=0,
            prerelease=base.prerelease,
        )

    if has_feature:
        return Version(
            major=base.major,
            minor=base.minor + 1,
            patch=0,
            prerelease=base.prerelease,
        )

    if has_fix:
        return Version(
            major=base.major,
            minor=base.minor,
            patch=base.patch + 1,
            prerelease=base.prerelease,
        )

    return base


def _run_git(*arguments: str) -> str:
    """Run a read-only Git command."""

    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={PROJECT_ROOT}",
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )

    return result.stdout


def _version_file_repository_path() -> str:
    """Return VERSION as repository-relative path."""

    return str(
        VERSION_FILE.relative_to(
            PROJECT_ROOT
        )
    )


def _version_anchor(
    revision: str = "HEAD",
) -> str:
    """Return the latest commit that changed VERSION."""

    return _run_git(
        "log",
        "-1",
        "--format=%H",
        revision,
        "--",
        _version_file_repository_path(),
    ).strip()


def _git_commits_since(
    anchor: str,
    revision: str = "HEAD",
) -> list[CommitDescription]:
    """Read commits after VERSION anchor, oldest first."""

    if not anchor:
        return []

    output = _run_git(
        "log",
        "--reverse",
        "--format=%s%x00%b%x00",
        f"{anchor}..{revision}",
    )

    fields = output.split("\x00")

    commits: list[CommitDescription] = []

    for index in range(
        0,
        len(fields) - 1,
        2,
    ):
        subject = fields[index].strip()
        body = fields[index + 1].strip()

        if not subject:
            continue

        commits.append(
            CommitDescription(
                subject=subject,
                body=body,
            )
        )

    return commits


def _read_declared_version() -> str:
    """Read VERSION."""

    try:
        value = VERSION_FILE.read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return FALLBACK_VERSION

    if not value:
        return FALLBACK_VERSION

    return value


def calculate_repository_version(
    revision: str = "HEAD",
) -> str:
    """Calculate the version from VERSION and Git history."""

    declared_version = _read_declared_version()

    base = Version.parse(
        declared_version
    )

    anchor = _version_anchor(
        revision
    )

    if not anchor:
        return str(base)

    commits = _git_commits_since(
        anchor,
        revision,
    )

    return str(
        calculate_version(
            commits,
            base=base,
        )
    )


def write_calculated_version() -> tuple[str, bool]:
    """Calculate the repository version and persist it in VERSION.

    Returns:

        (version, changed)
    """

    current_version = _read_declared_version()

    calculated_version = (
        calculate_repository_version()
    )

    Version.parse(
        calculated_version
    )

    if calculated_version == current_version:
        return calculated_version, False

    temporary_file = VERSION_FILE.with_name(
        "VERSION.tmp"
    )

    temporary_file.write_text(
        f"{calculated_version}\n",
        encoding="utf-8",
    )

    temporary_file.replace(
        VERSION_FILE
    )

    return calculated_version, True


def get_application_version() -> str:
    """Return the persisted application version.

    VERSION is the single source of truth.
    """

    version = _read_declared_version()

    try:
        Version.parse(version)
    except ValueError:
        return FALLBACK_VERSION

    return version


def main() -> int:
    """Update VERSION from Git history."""

    version, changed = (
        write_calculated_version()
    )

    if changed:
        print(
            f"VERSION updated to {version}"
        )
    else:
        print(
            f"VERSION unchanged: {version}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )