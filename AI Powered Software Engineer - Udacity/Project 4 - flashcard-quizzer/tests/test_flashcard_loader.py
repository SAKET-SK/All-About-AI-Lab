"""Tests for loading and validating flashcard decks."""

from pathlib import Path

import pytest

from tests.conftest import DeckWriter
from utils import data_loader
from utils.data_loader import FlashcardLoadError, load_flashcards, parse_flashcards
from utils.models import Flashcard

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_load_valid_flashcards_array(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "API", "back": "Application Programming Interface"}])

    cards = load_flashcards(path)

    assert cards == [Flashcard("API", "Application Programming Interface")]


def test_load_valid_flashcards_object_format(write_deck: DeckWriter) -> None:
    path = write_deck({"cards": [{"front": "def", "back": "function"}]})

    assert load_flashcards(path) == [Flashcard("def", "function")]


def test_load_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('[{"front": "API", "back": ', encoding="utf-8")

    with pytest.raises(FlashcardLoadError, match="Invalid JSON") as info:
        load_flashcards(path)

    assert "line 1" in str(info.value)


def test_load_missing_required_field(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "API", "back": "ok"}, {"front": "CDN"}])

    with pytest.raises(FlashcardLoadError) as info:
        load_flashcards(path)

    assert 'Card 2: missing or empty "back"' in str(info.value)


def test_load_rejects_missing_front(write_deck: DeckWriter) -> None:
    with pytest.raises(FlashcardLoadError, match='"front"'):
        load_flashcards(write_deck([{"back": "answer"}]))


@pytest.mark.parametrize("bad_value", ["", "   ", None, 42, ["x"]])
def test_load_rejects_empty_or_non_text_values(
    write_deck: DeckWriter, bad_value: object
) -> None:
    with pytest.raises(FlashcardLoadError, match='"back"'):
        load_flashcards(write_deck([{"front": "Q", "back": bad_value}]))


def test_load_rejects_card_that_is_not_an_object(write_deck: DeckWriter) -> None:
    with pytest.raises(FlashcardLoadError, match="Card 1: expected an object"):
        load_flashcards(write_deck(["just a string"]))


@pytest.mark.parametrize("data", [42, "text", None, True])
def test_load_rejects_wrong_top_level_type(
    write_deck: DeckWriter, data: object
) -> None:
    with pytest.raises(FlashcardLoadError, match="JSON array or an object"):
        load_flashcards(write_deck(data))


def test_load_rejects_object_without_cards_key(write_deck: DeckWriter) -> None:
    with pytest.raises(FlashcardLoadError, match='needs a "cards" list'):
        load_flashcards(write_deck({"deck": []}))


def test_load_rejects_cards_value_that_is_not_a_list(write_deck: DeckWriter) -> None:
    with pytest.raises(FlashcardLoadError, match="must be a list"):
        load_flashcards(write_deck({"cards": "nope"}))


@pytest.mark.parametrize("data", [[], {"cards": []}])
def test_load_rejects_empty_deck(write_deck: DeckWriter, data: object) -> None:
    with pytest.raises(FlashcardLoadError, match="no cards"):
        load_flashcards(write_deck(data))


def test_load_trims_whitespace_around_text(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "  API ", "back": "\tInterface\n"}])

    assert load_flashcards(path) == [Flashcard("API", "Interface")]


def test_load_missing_file_has_friendly_message(tmp_path: Path) -> None:
    with pytest.raises(FlashcardLoadError, match="File not found"):
        load_flashcards(tmp_path / "missing.json")


def test_load_directory_has_friendly_message(tmp_path: Path) -> None:
    with pytest.raises(FlashcardLoadError, match="is a directory"):
        load_flashcards(tmp_path)


def test_load_non_utf8_file_has_friendly_message(tmp_path: Path) -> None:
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\x00\x80")

    with pytest.raises(FlashcardLoadError, match="not valid UTF-8"):
        load_flashcards(path)


def test_load_oversized_file_is_refused(
    write_deck: DeckWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_deck([{"front": "Q", "back": "A"}])
    monkeypatch.setattr(data_loader, "MAX_FILE_BYTES", 5)

    with pytest.raises(FlashcardLoadError, match="too large"):
        load_flashcards(path)


def test_load_permission_error_has_friendly_message(
    write_deck: DeckWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_deck([{"front": "Q", "back": "A"}])

    def deny(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError

    monkeypatch.setattr(Path, "read_text", deny)

    with pytest.raises(FlashcardLoadError, match="Permission denied"):
        load_flashcards(path)


def test_load_other_os_error_has_friendly_message(
    write_deck: DeckWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_deck([{"front": "Q", "back": "A"}])

    def fail(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(Path, "read_text", fail)

    with pytest.raises(FlashcardLoadError, match="Could not read"):
        load_flashcards(path)


def test_parse_flashcards_accepts_already_parsed_data() -> None:
    assert parse_flashcards({"cards": [{"front": "a", "back": "b"}]}) == [
        Flashcard("a", "b")
    ]


@pytest.mark.parametrize(
    ("filename", "expected_count"), [("glossary.json", 10), ("python_basics.json", 8)]
)
def test_bundled_sample_decks_load(filename: str, expected_count: int) -> None:
    assert len(load_flashcards(DATA_DIR / filename)) == expected_count


def test_every_deck_in_the_data_folder_is_valid() -> None:
    decks = sorted(DATA_DIR.glob("*.json"))

    assert len(decks) >= 3  # glossary, python_basics and network_ports
    for deck in decks:
        assert load_flashcards(deck), f"{deck.name} produced no cards"
