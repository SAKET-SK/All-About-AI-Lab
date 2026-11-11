"""Loading and validating flashcard decks from JSON files.

Two layouts are supported:

* Array format: ``[{"front": "...", "back": "..."}, ...]``
* Object format: ``{"cards": [{"front": "...", "back": "..."}, ...]}``

Every problem is reported as a :class:`FlashcardLoadError` with a short,
human-readable message, so callers never have to show a raw traceback.
"""

import json
from pathlib import Path

from utils.models import Flashcard

MAX_FILE_BYTES = 5_000_000  # Refuse absurdly large decks instead of loading them.
REQUIRED_FIELDS = ("front", "back")


class FlashcardLoadError(Exception):
    """Raised when a deck cannot be read or does not have a valid structure."""


def load_flashcards(path: str | Path) -> list[Flashcard]:
    """Read a JSON deck from disk and return its validated cards.

    Args:
        path: Location of the JSON deck.

    Returns:
        The cards in file order.

    Raises:
        FlashcardLoadError: If the file is missing, unreadable, too large,
            not valid JSON, or contains an invalid card.
    """
    deck_path = Path(path)
    text = _read_text(deck_path)
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FlashcardLoadError(
            f"Invalid JSON in {deck_path}: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})."
        ) from exc
    return parse_flashcards(data)


def parse_flashcards(data: object) -> list[Flashcard]:
    """Validate already-parsed JSON data and convert it to flashcards.

    Args:
        data: The result of ``json.loads`` for a deck.

    Returns:
        The validated cards, with surrounding whitespace trimmed.

    Raises:
        FlashcardLoadError: If the structure is wrong or a card is invalid.
    """
    raw_cards = _extract_card_list(data)
    if not raw_cards:
        raise FlashcardLoadError("The deck contains no cards.")
    return [_parse_card(item, index) for index, item in enumerate(raw_cards, 1)]


def _read_text(path: Path) -> str:
    """Read a deck file, translating OS errors into friendly messages."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise FlashcardLoadError(
                f"{path} is too large (limit is {MAX_FILE_BYTES:,} bytes)."
            )
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FlashcardLoadError(f"File not found: {path}") from None
    except IsADirectoryError:
        raise FlashcardLoadError(f"{path} is a directory, not a JSON file.") from None
    except PermissionError:
        raise FlashcardLoadError(f"Permission denied when reading {path}.") from None
    except UnicodeDecodeError:
        raise FlashcardLoadError(f"{path} is not valid UTF-8 text.") from None
    except OSError as exc:
        raise FlashcardLoadError(f"Could not read {path}: {exc.strerror}.") from exc


def _extract_card_list(data: object) -> list[object]:
    """Return the list of raw cards from either supported layout."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "cards" not in data:
            raise FlashcardLoadError('Object format needs a "cards" list.')
        cards = data["cards"]
        if not isinstance(cards, list):
            raise FlashcardLoadError('The "cards" value must be a list.')
        return cards
    raise FlashcardLoadError(
        'The deck must be a JSON array or an object with a "cards" list.'
    )


def _parse_card(item: object, index: int) -> Flashcard:
    """Validate one raw card; ``index`` is 1-based for error messages."""
    if not isinstance(item, dict):
        raise FlashcardLoadError(
            f'Card {index}: expected an object with "front" and "back".'
        )
    values: dict[str, str] = {}
    for field_name in REQUIRED_FIELDS:
        value = item.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise FlashcardLoadError(
                f'Card {index}: missing or empty "{field_name}" text.'
            )
        values[field_name] = value.strip()
    return Flashcard(front=values["front"], back=values["back"])
