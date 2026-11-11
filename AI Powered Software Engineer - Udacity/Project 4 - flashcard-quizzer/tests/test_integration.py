"""End-to-end tests that combine the loader, engine, UI and history."""

import random
from pathlib import Path

import pytest

import main
from tests.conftest import DeckWriter, ScriptedConsole
from utils.data_loader import load_flashcards
from utils.history import HistoryStore
from utils.quiz_engine import QuizModeFactory, QuizSession
from utils.ui import render_summary, run_quiz

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_full_session(write_deck: DeckWriter) -> None:
    """Answer three questions (two right, one wrong) and check the final stats."""
    deck = write_deck(
        {
            "cards": [
                {"front": "def", "back": "function"},
                {"front": "len", "back": "length"},
                {"front": "for", "back": "loop"},
            ]
        }
    )
    cards = load_flashcards(deck)
    session = QuizSession(QuizModeFactory.create("sequential", cards))
    script = ScriptedConsole(["FUNCTION", "wrong answer", " Loop "])

    finished = run_quiz(session, script.console)

    assert finished is True
    stats = session.stats
    assert stats.total == 3
    assert stats.correct == 2
    assert stats.accuracy == pytest.approx(66.7, abs=0.05)
    assert stats.missed == ["len"]
    summary = render_summary(stats)
    assert "66.7%" in summary
    assert "len" in summary


def test_full_adaptive_session_on_a_bundled_deck() -> None:
    cards = load_flashcards(DATA_DIR / "python_basics.json")
    answers = {card.front: card.back for card in cards}
    session = QuizSession(QuizModeFactory.create("adaptive", cards, random.Random(4)))
    first_attempts: set[str] = set()

    while (card := session.next_card()) is not None:
        # Miss every card on its first attempt, answer correctly afterwards.
        if card.front not in first_attempts:
            first_attempts.add(card.front)
            session.submit("definitely wrong")
        else:
            session.submit(answers[card.front])

    assert session.stats.total == 2 * len(cards)
    assert session.stats.correct == len(cards)
    assert sorted(session.stats.missed) == sorted(answers)


@pytest.mark.parametrize("deck_name", ["glossary.json", "python_basics.json"])
@pytest.mark.parametrize("mode", ["sequential", "random", "adaptive"])
def test_every_mode_completes_on_every_bundled_deck(
    deck_name: str, mode: str, tmp_path: Path
) -> None:
    deck_path = DATA_DIR / deck_name
    expected = {card.front: card.back for card in load_flashcards(deck_path)}
    script = ScriptedConsole()
    answers_given: list[str] = []

    def answer(prompt: str) -> str:
        """Answer correctly by reading the question out of the prompt."""
        front = prompt.split(": ", 1)[1].split("\n", 1)[0]
        answers_given.append(front)
        return expected[front]

    script.console.input_fn = answer

    code = main.main(
        ["-f", str(deck_path), "-m", mode, "--history-file", str(tmp_path / "h.json")],
        script.console,
    )

    assert code == 0
    assert sorted(answers_given) == sorted(expected)  # each card exactly once
    assert "100.0%" in script.text


def test_sessions_accumulate_into_lifetime_statistics(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    deck = str(DATA_DIR / "glossary.json")
    for _ in range(2):
        script = ScriptedConsole(["wrong"] * 3)
        main.main(
            ["-f", deck, "-n", "3", "--history-file", str(history)], script.console
        )

    stats = HistoryStore(history).summarize(str(Path(deck).resolve()))

    assert stats.sessions == 2
    assert stats.total == 6
    assert stats.correct == 0
    assert stats.hardest[0][1] == 2  # the first cards were missed in both sessions
