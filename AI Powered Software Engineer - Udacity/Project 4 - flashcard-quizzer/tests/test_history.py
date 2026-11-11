"""Tests for the persistent session history."""

import json
from pathlib import Path

import pytest

from utils.history import (
    HARDEST_CARD_COUNT,
    HistoryError,
    HistoryStore,
    LifetimeStats,
    SessionRecord,
    default_history_path,
)


def record(
    deck: str = "deck.json",
    total: int = 4,
    correct: int = 3,
    missed: tuple[str, ...] = ("DNS",),
) -> SessionRecord:
    return SessionRecord(
        deck=deck,
        mode="sequential",
        timestamp="2026-01-01T00:00:00+00:00",
        total=total,
        correct=correct,
        missed=missed,
    )


def test_a_missing_history_file_means_no_records(tmp_path: Path) -> None:
    assert HistoryStore(tmp_path / "none.json").load() == []


def test_append_then_load_round_trips_a_record(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")

    store.append(record())

    assert store.load() == [record()]


def test_append_creates_missing_parent_folders(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "nested" / "dir" / "h.json")

    store.append(record())

    assert len(store.load()) == 1


def test_append_keeps_earlier_records(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")

    store.append(record(total=1))
    store.append(record(total=2))

    assert [item.total for item in store.load()] == [1, 2]


def test_append_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")

    store.append(record())

    assert sorted(path.name for path in tmp_path.iterdir()) == ["h.json"]


def test_create_stamps_the_current_time() -> None:
    created = SessionRecord.create("d", "random", 2, 1, ["X"])

    assert created.timestamp.endswith("+00:00")
    assert created.missed == ("X",)


@pytest.mark.parametrize(
    "content",
    ["not json", '{"deck": "x"}', '[{"deck": "x"}]', "[1, 2]", '[{"deck": "a", '],
)
def test_a_corrupt_history_file_raises_a_history_error(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "h.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(HistoryError, match="unreadable"):
        HistoryStore(path).load()


def test_append_never_overwrites_a_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    path.write_text("corrupt", encoding="utf-8")

    with pytest.raises(HistoryError):
        HistoryStore(path).append(record())

    assert path.read_text(encoding="utf-8") == "corrupt"


def test_append_reports_a_write_failure(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    store = HistoryStore(blocker / "h.json")

    with pytest.raises(HistoryError, match="Could not save"):
        store.append(record())


def test_summarize_with_no_history(tmp_path: Path) -> None:
    stats = HistoryStore(tmp_path / "h.json").summarize("deck.json")

    assert stats == LifetimeStats()
    assert stats.accuracy == 0.0


def test_summarize_combines_sessions_for_one_deck(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")
    store.append(record(total=4, correct=3, missed=("DNS",)))
    store.append(record(total=6, correct=4, missed=("DNS", "TLS")))
    store.append(record(deck="other.json", total=99, correct=0, missed=("ZZZ",)))

    stats = store.summarize("deck.json")

    assert stats.sessions == 2
    assert stats.total == 10
    assert stats.correct == 7
    assert stats.accuracy == pytest.approx(70.0)
    assert stats.hardest == [("DNS", 2), ("TLS", 1)]


def test_summarize_lists_only_the_hardest_cards(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")
    many = tuple(f"card{i}" for i in range(HARDEST_CARD_COUNT + 3))
    store.append(record(missed=many))

    assert len(store.summarize("deck.json").hardest) == HARDEST_CARD_COUNT


def test_history_file_is_plain_readable_json(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    HistoryStore(path).append(record())

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data[0]["deck"] == "deck.json"
    assert data[0]["missed"] == ["DNS"]


def test_default_history_path_lives_in_the_home_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert default_history_path() == tmp_path / ".flashcard_quizzer" / "history.json"


def test_default_history_path_falls_back_when_home_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", no_home)
    monkeypatch.chdir(tmp_path)

    assert default_history_path() == tmp_path / ".flashcard_quizzer" / "history.json"


def test_history_store_uses_the_default_path_when_none_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    HistoryStore().append(record())

    assert (tmp_path / ".flashcard_quizzer" / "history.json").exists()
