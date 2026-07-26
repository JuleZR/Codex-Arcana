"""Calculate the visible application version from the Git commit history."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEPLOYED_VERSION_FILE = PROJECT_ROOT / ".codex-arcana-version"

# This fallback represents the repository state at which automatic versioning
# was introduced. Deployments that do not include `.git` should provide the
# freshly calculated value through CODEX_ARCANA_VERSION.
FALLBACK_VERSION = "v.0.91.0-b329"

_COMMIT_TYPE_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?:",
    re.IGNORECASE,
)
_BREAKING_CHANGE_PATTERN = re.compile(
    r"(?:^|\n)BREAKING(?: |-)?CHANGE\s*:",
    re.IGNORECASE,
)
_PATCH_TYPES = frozenset({"fix", "perf", "refactor"})


@dataclass(frozen=True, slots=True)
class CommitDescription:
    """The subject and body needed to classify one commit."""

    subject: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class Version:
    """The four components of the Codex Arcana version number."""

    phase: int = 0
    feature: int = 0
    patch: int = 0
    build: int = 0

    def __str__(self) -> str:
        return f"v.{self.phase}.{self.feature}.{self.patch}-b{self.build}"


def calculate_version(
    commits: list[CommitDescription],
    *,
    base: Version | None = None,
) -> Version:
    """Apply the project version rules to commits in chronological order."""

    version = base or Version()

    for commit in commits:
        phase = version.phase
        feature = version.feature
        patch = version.patch
        build = version.build + 1

        match = _COMMIT_TYPE_PATTERN.match(commit.subject.strip())
        commit_type = match.group("type").lower() if match else ""
        is_breaking = bool(match and match.group("breaking")) or bool(
            _BREAKING_CHANGE_PATTERN.search(commit.body)
        )

        if is_breaking or commit_type == "feat":
            feature += 1
            patch = 0
        elif commit_type in _PATCH_TYPES:
            patch += 1

        version = Version(
            phase=phase,
            feature=feature,
            patch=patch,
            build=build,
        )

    return version


def _run_git(*arguments: str) -> str:
    """Run a read-only Git command in the project repository."""

    result = subprocess.run(
        ["git", "-c", f"safe.directory={PROJECT_ROOT}", *arguments],
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
    """Return the commit that currently determines the application version."""

    return _run_git("rev-parse", "--verify", "HEAD").strip()


def _git_commits(revision: str = "HEAD") -> list[CommitDescription]:
    """Read all commits reachable from a revision, oldest first."""

    output = _run_git(
        "log",
        "--reverse",
        "--format=%s%x00%b%x00",
        revision,
    )
    fields = output.split("\x00")
    commits: list[CommitDescription] = []

    for index in range(0, len(fields) - 1, 2):
        subject = fields[index].strip()
        body = fields[index + 1].strip()
        if subject:
            commits.append(CommitDescription(subject=subject, body=body))

    return commits


@lru_cache(maxsize=8)
def _version_for_git_head(head: str) -> str:
    """Calculate once per Git commit instead of once per server process."""

    return str(calculate_version(_git_commits(head)))


def get_git_version() -> str:
    """Calculate the version directly from the current Git checkout."""

    return _version_for_git_head(_git_head())


def _read_deployed_version() -> str:
    """Read the version snapshot created by the deployment script."""

    try:
        return DEPLOYED_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_deployed_version() -> str:
    """Atomically store the Git version for processes without Git access."""

    version = get_git_version()
    temporary_file = DEPLOYED_VERSION_FILE.with_name(
        f"{DEPLOYED_VERSION_FILE.name}.tmp"
    )
    temporary_file.write_text(f"{version}\n", encoding="utf-8")
    temporary_file.replace(DEPLOYED_VERSION_FILE)
    return version


def get_application_version() -> str:
    """Return an explicit deployment version or calculate it from Git."""

    override = os.getenv("CODEX_ARCANA_VERSION", "").strip()
    if override:
        return override

    deployed_version = _read_deployed_version()
    if deployed_version:
        return deployed_version

    try:
        return get_git_version()
    except (OSError, subprocess.SubprocessError):
        return FALLBACK_VERSION
