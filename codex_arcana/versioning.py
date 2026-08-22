"""Calculate the visible Codex Arcana version from the declared release version
and Conventional Commits made since that version was set.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent.parent

VERSION_FILE = PROJECT_ROOT / "VERSION"

DEPLOYED_VERSION_FILE = PROJECT_ROOT / ".codex-arcana-version"

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
    """The subject and body needed to classify one commit."""

    subject: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class Version:
    """A Semantic Versioning version."""

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


def _commit_is_breaking(commit: CommitDescription) -> bool:
    """Return whether a Conventional Commit declares a breaking change."""

    match = _COMMIT_TYPE_PATTERN.match(commit.subject.strip())

    if match and match.group("breaking"):
        return True

    return bool(_BREAKING_CHANGE_PATTERN.search(commit.body))


def _commit_type(commit: CommitDescription) -> str:
    """Return the Conventional Commit type, if present."""

    match = _COMMIT_TYPE_PATTERN.match(commit.subject.strip())

    if not match:
        return ""

    return match.group("type").lower()


def calculate_version(
    commits: list[CommitDescription],
    *,
    base: Version,
) -> Version:
    """Calculate the next semantic version candidate.

    Version changes are aggregated across all commits since the declared
    VERSION baseline.

    Multiple commits of the same class therefore do not repeatedly increase
    the version.

    Rules:

    - BREAKING CHANGE:
        - before 1.0.0 -> next minor version
        - from 1.0.0 onward -> next major version
    - feat -> next minor version
    - fix -> next patch version
    - all other commit types -> no automatic version change
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
    """Run a read-only Git command in the project repository."""

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
        timeout=5,
    )

    return result.stdout


def _git_head() -> str:
    """Return the current Git HEAD."""

    return _run_git(
        "rev-parse",
        "--verify",
        "HEAD",
    ).strip()


def _version_file_repository_path() -> str:
    """Return VERSION as a repository-relative path."""

    return str(
        VERSION_FILE.relative_to(PROJECT_ROOT)
    )


def _version_anchor(
    revision: str = "HEAD",
) -> str:
    """Return the most recent commit that changed VERSION."""

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
    """Read commits after the VERSION anchor, oldest first."""

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

    for index in range(0, len(fields) - 1, 2):
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
    """Read the release baseline from VERSION."""

    try:
        value = VERSION_FILE.read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return FALLBACK_VERSION

    if not value:
        return FALLBACK_VERSION

    return value


@lru_cache(maxsize=8)
def _version_for_git_head(
    head: str,
    declared_version: str,
) -> str:
    """Calculate once per HEAD and declared VERSION combination."""

    base = Version.parse(declared_version)

    anchor = _version_anchor(head)

    if not anchor:
        return str(base)

    commits = _git_commits_since(
        anchor,
        head,
    )

    return str(
        calculate_version(
            commits,
            base=base,
        )
    )


def get_git_version() -> str:
    """Calculate the application version from VERSION and Git history."""

    declared_version = _read_declared_version()

    Version.parse(declared_version)

    head = _git_head()

    return _version_for_git_head(
        head,
        declared_version,
    )


def _read_deployed_version() -> str:
    """Read the deployment snapshot created by the deployment script."""

    try:
        return DEPLOYED_VERSION_FILE.read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return ""


def write_deployed_version() -> str:
    """Atomically store the current Git-derived application version."""

    version = get_git_version()

    temporary_file = DEPLOYED_VERSION_FILE.with_name(
        f"{DEPLOYED_VERSION_FILE.name}.tmp"
    )

    temporary_file.write_text(
        f"{version}\n",
        encoding="utf-8",
    )

    temporary_file.replace(
        DEPLOYED_VERSION_FILE
    )

    return version


def get_application_version() -> str:
    """Return the deployment override or calculated application version."""

    override = os.getenv(
        "CODEX_ARCANA_VERSION",
        "",
    ).strip()

    if override:
        return override

    deployed_version = _read_deployed_version()

    if deployed_version:
        return deployed_version

    try:
        return get_git_version()
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ):
        return FALLBACK_VERSION
