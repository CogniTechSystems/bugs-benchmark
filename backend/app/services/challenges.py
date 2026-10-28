"""Loading bug hunt challenge definitions from disk.

Each challenge lives in its own directory containing:

* ``challenge.toml`` describing the project and the expected bugs,
* ``src/`` holding the code the agent inspects,
* ``tests/`` holding hidden tests used to verify proposed fixes.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import utc_now
from app.models import BugHunt, Difficulty

MANIFEST_NAME = "challenge.toml"
IGNORED_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache"})


class ChallengeDefinitionError(ValueError):
    """Raised when a challenge manifest is invalid."""


class ChallengeNotFoundError(LookupError):
    """Raised when a challenge slug does not exist in the catalogue."""


@dataclass(frozen=True)
class ExpectedBug:
    key: str
    title: str
    file: str
    points: int
    tests: tuple[str, ...]
    original: str
    replacement: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class Challenge:
    slug: str
    title: str
    difficulty: Difficulty
    language: str
    summary: str
    time_budget_seconds: int
    root: Path
    bugs: tuple[ExpectedBug, ...]

    @property
    def source_dir(self) -> Path:
        return self.root / "src"

    @property
    def tests_dir(self) -> Path:
        return self.root / "tests"

    @property
    def max_points(self) -> int:
        return 2 * sum(bug.points for bug in self.bugs)

    def source_files(self) -> Iterator[str]:
        """Yield source file paths relative to ``source_dir`` using forward slashes."""
        for path in sorted(self.source_dir.rglob("*")):
            relative = path.relative_to(self.source_dir)
            if path.is_file() and not IGNORED_PARTS.intersection(relative.parts):
                yield relative.as_posix()

    def resolve_source_path(self, relative_path: str) -> Path:
        """Resolve a path supplied by the agent, refusing anything outside ``source_dir``."""
        root = self.source_dir.resolve()
        candidate = (root / normalise_source_path(relative_path)).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise FileNotFoundError(f"No such file in the project: {relative_path}")
        return candidate


class ChallengeCatalog:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._challenges: dict[str, Challenge] = {}
        self.reload()

    def reload(self) -> None:
        challenges = {}
        if self._directory.is_dir():
            for manifest in sorted(self._directory.glob(f"*/{MANIFEST_NAME}")):
                challenge = load_challenge(manifest.parent)
                challenges[challenge.slug] = challenge
        self._challenges = challenges

    def all(self) -> list[Challenge]:
        return list(self._challenges.values())

    def get(self, slug: str) -> Challenge:
        try:
            return self._challenges[slug.strip().lower()]
        except KeyError:
            raise ChallengeNotFoundError(f"Unknown bug hunt: {slug}") from None

    def sync(self, db: Session) -> None:
        """Mirror the catalogue into the ``bug_hunts`` table."""
        existing = {hunt.slug: hunt for hunt in db.scalars(select(BugHunt))}
        for challenge in self._challenges.values():
            hunt = existing.pop(challenge.slug, None) or BugHunt(slug=challenge.slug)
            hunt.title = challenge.title
            hunt.difficulty = challenge.difficulty
            hunt.language = challenge.language
            hunt.summary = challenge.summary
            hunt.bug_count = len(challenge.bugs)
            hunt.max_points = challenge.max_points
            hunt.time_budget_seconds = challenge.time_budget_seconds
            hunt.is_available = True
            hunt.synced_at = utc_now()
            db.add(hunt)
        for missing in existing.values():
            missing.is_available = False
        db.commit()


def normalise_source_path(path: str) -> str:
    """Normalise an agent-supplied path to a forward-slash path relative to ``src/``."""
    normalised = path.strip().replace("\\", "/")
    while normalised.startswith(("./", "/")):
        normalised = normalised.removeprefix("./").removeprefix("/")
    return normalised.removeprefix("src/")


def load_challenge(root: Path) -> Challenge:
    manifest_path = root / MANIFEST_NAME
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        challenge = Challenge(
            slug=root.name,
            title=manifest["title"],
            difficulty=Difficulty(manifest["difficulty"]),
            language=manifest.get("language", "python"),
            summary=manifest["summary"].strip(),
            time_budget_seconds=int(manifest["time_budget_seconds"]),
            root=root,
            bugs=(),
        )
        bugs = tuple(_load_bug(challenge, entry) for entry in manifest["bugs"])
    except (KeyError, TypeError, ValueError, OSError, tomllib.TOMLDecodeError) as exc:
        raise ChallengeDefinitionError(f"Invalid manifest {manifest_path}: {exc}") from exc

    keys = [bug.key for bug in bugs]
    if len(set(keys)) != len(keys):
        raise ChallengeDefinitionError(f"Duplicate bug keys in {manifest_path}")
    return replace(challenge, bugs=bugs)


def _load_bug(challenge: Challenge, entry: dict[str, object]) -> ExpectedBug:
    file = str(entry["file"])
    original = str(entry["original"])
    content = challenge.resolve_source_path(file).read_text(encoding="utf-8")
    occurrences = content.count(original)
    if occurrences != 1:
        raise ChallengeDefinitionError(
            f"Bug '{entry['key']}' original code must occur exactly once in {file}, "
            f"found {occurrences}."
        )
    line_start = content.count("\n", 0, content.index(original)) + 1
    tests = entry["tests"]
    if not isinstance(tests, list) or not tests:
        raise ChallengeDefinitionError(f"Bug '{entry['key']}' must list at least one test.")
    return ExpectedBug(
        key=str(entry["key"]),
        title=str(entry["title"]),
        file=file,
        points=int(str(entry.get("points", 1))),
        tests=tuple(str(test) for test in tests),
        original=original,
        replacement=str(entry["replacement"]),
        line_start=line_start,
        line_end=line_start + original.rstrip("\n").count("\n"),
    )
