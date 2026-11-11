"""Shared fixtures and helpers for the test suite."""

import json
from pathlib import Path
from typing import Iterable, Protocol

import pytest

from utils.models import Flashcard
from utils.quiz_engine import QuizModeFactory
from utils.ui import Console

ScriptItem = str | BaseException


class DeckWriter(Protocol):
    """Callable that writes JSON data to a deck file and returns its path."""

    def __call__(self, data: object, name: str = "deck.json") -> Path: ...


class ScriptedConsole:
    """A Console whose input is scripted and whose output is captured.

    When the script runs out, reading raises ``EOFError`` (end of input), so a
    test can never hang waiting for the keyboard.
    """

    def __init__(self, answers: Iterable[ScriptItem] = ()) -> None:
        self._answers = iter(answers)
        self.output: list[str] = []
        self.errors: list[str] = []
        self.prompts: list[str] = []
        self.console = Console(
            input_fn=self._read,
            output_fn=self.output.append,
            error_fn=self.errors.append,
            use_color=False,
        )

    def _read(self, prompt: str) -> str:
        self.prompts.append(prompt)
        try:
            item = next(self._answers)
        except StopIteration:
            raise EOFError from None
        if isinstance(item, BaseException):
            raise item
        return item

    @property
    def text(self) -> str:
        """All captured output joined into one string."""
        return "\n".join(self.output)


@pytest.fixture
def cards() -> list[Flashcard]:
    """A small deck of four cards."""
    return [
        Flashcard("API", "Application Programming Interface"),
        Flashcard("CDN", "Content Delivery Network"),
        Flashcard("DNS", "Domain Name System"),
        Flashcard("TLS", "Transport Layer Security"),
    ]


@pytest.fixture
def write_deck(tmp_path: Path) -> DeckWriter:
    """Return a helper that writes JSON data to a deck file."""

    def _write(data: object, name: str = "deck.json") -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def isolated_registry() -> Iterable[None]:
    """Restore the quiz-mode registry after a test that registers modes."""
    saved = dict(QuizModeFactory._registry)
    yield
    QuizModeFactory._registry.clear()
    QuizModeFactory._registry.update(saved)
