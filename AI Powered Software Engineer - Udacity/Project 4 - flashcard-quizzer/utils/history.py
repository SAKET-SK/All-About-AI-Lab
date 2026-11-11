"""Persistent session history, used for the ``--stats`` lifetime statistics.

History is stored as a JSON list in the user's home directory. The store takes
its path as an argument, so tests and callers can point it anywhere.
"""

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HARDEST_CARD_COUNT = 5


def default_history_path() -> Path:
    """Return where history is stored when no path is given.

    This is ``~/.flashcard_quizzer/history.json``. If the home directory cannot
    be determined, the current directory is used instead of failing.
    """
    try:
        base = Path.home()
    except RuntimeError:
        base = Path.cwd()
    return base / ".flashcard_quizzer" / "history.json"


class HistoryError(Exception):
    """Raised when the history file cannot be read, parsed or written."""


@dataclass(frozen=True)
class SessionRecord:
    """One finished quiz session.

    Attributes:
        deck: Identifier of the deck (the resolved file path).
        mode: Name of the quiz mode that was used.
        timestamp: UTC time the session ended, in ISO 8601 format.
        total: Number of answers submitted.
        correct: Number of correct answers.
        missed: Fronts of the cards missed during the session.
    """

    deck: str
    mode: str
    timestamp: str
    total: int
    correct: int
    missed: tuple[str, ...] = ()

    @classmethod
    def create(
        cls, deck: str, mode: str, total: int, correct: int, missed: list[str]
    ) -> "SessionRecord":
        """Build a record stamped with the current UTC time."""
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return cls(deck, mode, stamp, total, correct, tuple(missed))


@dataclass(frozen=True)
class LifetimeStats:
    """Totals across every saved session for one deck.

    Attributes:
        sessions: Number of saved sessions.
        total: Total answers submitted.
        correct: Total correct answers.
        hardest: Up to five ``(front, times_missed)`` pairs, most missed first.
    """

    sessions: int = 0
    total: int = 0
    correct: int = 0
    hardest: list[tuple[str, int]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """Return the lifetime accuracy percentage, or 0.0 with no answers."""
        if self.total == 0:
            return 0.0
        return 100.0 * self.correct / self.total


class HistoryStore:
    """Reads and appends :class:`SessionRecord` entries in a JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        """Remember where the history file lives.

        Args:
            path: Location of the JSON history file (default location if None).
        """
        self._path = path if path is not None else default_history_path()

    def load(self) -> list[SessionRecord]:
        """Return all saved records; a missing file means no history yet.

        Raises:
            HistoryError: If the file exists but cannot be read or parsed.
        """
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("expected a JSON list")
            return [_record_from_dict(item) for item in data]
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise HistoryError(
                f"History file {self._path} is unreadable: {exc}"
            ) from exc

    def append(self, record: SessionRecord) -> None:
        """Add a record, writing the file atomically.

        Args:
            record: The session to save.

        Raises:
            HistoryError: If the existing history is corrupt or cannot be
                written. A corrupt file is never overwritten.
        """
        records = self.load()
        records.append(record)
        payload = json.dumps([asdict(item) for item in records], indent=2)
        temp_path = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(self._path)
        except OSError as exc:
            raise HistoryError(
                f"Could not save history to {self._path}: {exc}"
            ) from exc

    def summarize(self, deck: str) -> LifetimeStats:
        """Combine all saved sessions for one deck.

        Args:
            deck: Deck identifier to filter on.

        Returns:
            Lifetime totals and the most frequently missed cards.

        Raises:
            HistoryError: If the history file is unreadable.
        """
        records = [item for item in self.load() if item.deck == deck]
        misses: Counter[str] = Counter()
        for item in records:
            misses.update(item.missed)
        return LifetimeStats(
            sessions=len(records),
            total=sum(item.total for item in records),
            correct=sum(item.correct for item in records),
            hardest=misses.most_common(HARDEST_CARD_COUNT),
        )


def _record_from_dict(item: object) -> SessionRecord:
    """Convert one JSON object to a record, raising on a bad shape."""
    if not isinstance(item, dict):
        raise TypeError("each history entry must be an object")
    return SessionRecord(
        deck=str(item["deck"]),
        mode=str(item["mode"]),
        timestamp=str(item["timestamp"]),
        total=int(item["total"]),
        correct=int(item["correct"]),
        missed=tuple(str(front) for front in item.get("missed", [])),
    )
