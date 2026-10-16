"""CodexOS versioning for Codex Arcana.

VERSION is the canonical application version.

The next version is calculated from Conventional Commits made since the
most recent commit that changed VERSION.

Rules:

- [v:X], [v:X-rcN] or [v:X.Y.Z]:
    - manually sets the exact version at that commit
    - commits before the marker are ignored for the next calculation
    - commits after the marker are evaluated normally
- feat -> next minor version
- fix -> next patch version
- all other commit types -> no automatic version change
- BREAKING CHANGE never changes the generation on its own
- a manual -rc suffix starts at -rc1; prereleases stay frozen until
  a new manual marker is set

Commit scopes are supported, e.g.:

    fix(items): ...
    feat(magic): ...
    feat(api)!: ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent.parent

VERSION_FILE = PROJECT_ROOT / "VERSION"

FALLBACK_VERSION = "0.8.0-beta"


_VERSION_PATTERN = re.compile(
    r"""
    ^
    (?P<major>0|[1-9]\d*)
    (?:
        \.
        (?P<minor>0|[1-9]\d*)
        \.
        (?P<patch>0|[1-9]\d*)
    )?
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


_MANUAL_VERSION_PATTERN = re.compile(
    r"\[v:(?P<version>[0-9A-Za-z.-]+)\]",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CommitDescription:
    """Commit information required for version classification."""

    subject: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class Version:
    """CodexOS version, retaining explicit legacy components on read."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    explicit_components: bool = field(default=False, compare=False)

    def __str__(self) -> str:
        version = str(self.major)

        if self.minor or self.patch or self.explicit_components:
            version = f"{self.major}.{self.minor}.{self.patch}"

        if self.prerelease:
            version = f"{version}-{self.prerelease}"

        return version

    @classmethod
    def parse(cls, value: str) -> "Version":
        """Parse CodexOS versions and existing SemVer versions losslessly."""

        normalized = value.strip()

        match = _VERSION_PATTERN.fullmatch(normalized)

        if not match:
            raise ValueError(
                f"Invalid Codex Arcana version: {value!r}"
            )

        prerelease = match.group("prerelease")
        explicit_components = match.group("minor") is not None
        if not explicit_components and prerelease and not re.fullmatch(
            r"rc(?:[1-9][0-9]*)?", prerelease
        ):
            raise ValueError(f"Invalid CodexOS version: {value!r}")

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor") or "0"),
            patch=int(match.group("patch") or "0"),
            prerelease=prerelease,
            explicit_components=explicit_components,
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


def _manual_version(
    commit: CommitDescription,
) -> Version | None:
    """Return an exact version declared by a [v:...] commit marker."""

    text = f"{commit.subject}\n{commit.body}"

    for match in reversed(list(_MANUAL_VERSION_PATTERN.finditer(text))):
        try:
            version = Version.parse(match.group("version"))
        except ValueError:
            continue
        if version.prerelease and not re.fullmatch(
            r"rc(?:[1-9][0-9]*)?", version.prerelease
        ):
            continue
        return Version(
            major=version.major,
            minor=version.minor,
            patch=version.patch,
            prerelease=(
                "rc1" if version.prerelease == "rc" else version.prerelease
            ),
        )
    return None


def calculate_version(
    commits: list[CommitDescription],
    *,
    base: Version,
) -> Version:
    """Calculate the next CodexOS version candidate.

    All commits since the most recent VERSION update are evaluated
    together.

    Multiple commits of the same class therefore only increase the
    version once.

    A manual [v:...] marker establishes a new base version.
    A bare -rc suffix is normalized to -rc1.
    The newest marker wins. Its own commit and all earlier commits are
    excluded from automatic bump classification; only later commits are
    evaluated.

    Priority after the manual anchor:

        feat > fix (only for full releases)
    """

    for index in range(
        len(commits) - 1,
        -1,
        -1,
    ):
        manual_version = _manual_version(
            commits[index]
        )

        if manual_version is None:
            continue

        base = manual_version
        commits = commits[index + 1:]
        break

    # Keep RCs and legacy prereleases unchanged until a manual marker.
    if base.prerelease:
        return base

    has_feature = any(
        _commit_type(commit) == "feat"
        for commit in commits
    )

    has_fix = any(
        _commit_type(commit) == "fix"
        for commit in commits
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
