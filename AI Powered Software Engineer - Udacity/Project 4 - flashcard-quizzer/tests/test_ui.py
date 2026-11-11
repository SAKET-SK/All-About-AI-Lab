"""Tests for the terminal UI: colours, the quiz loop and rendered tables."""

import io
import random
import re

import pytest

from tests.conftest import ScriptedConsole
from utils.history import LifetimeStats
from utils.models import Flashcard, SessionStats
from utils.quiz_engine import QuizSession, SequentialMode
from utils.ui import (
    GREEN,
    MAX_TABLE_WIDTH,
    RED,
    RESET,
    Console,
    render_lifetime_stats,
    render_summary,
    run_quiz,
    should_use_color,
)


class FakeTerminal(io.StringIO):
    """A text stream that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


# --- Colour handling -------------------------------------------------------


def test_should_use_color_on_a_terminal() -> None:
    assert should_use_color(FakeTerminal(), env={}) is True


def test_should_not_use_color_when_output_is_redirected() -> None:
    assert should_use_color(io.StringIO(), env={}) is False


def test_should_not_use_color_with_the_flag() -> None:
    assert should_use_color(FakeTerminal(), disabled=True, env={}) is False


def test_should_not_use_color_when_no_color_is_set() -> None:
    assert should_use_color(FakeTerminal(), env={"NO_COLOR": "1"}) is False


def test_should_use_color_reads_the_real_environment_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    assert should_use_color(FakeTerminal()) is False


def test_console_wraps_text_in_green_and_red_when_colour_is_on() -> None:
    lines: list[str] = []
    console = Console(output_fn=lines.append, error_fn=lines.append, use_color=True)

    console.success("yes")
    console.failure("no")
    console.error("bad")

    assert lines == [
        f"{GREEN}yes{RESET}",
        f"{RED}no{RESET}",
        f"{RED}bad{RESET}",
    ]


def test_console_prints_plain_text_when_colour_is_off() -> None:
    script = ScriptedConsole()

    script.console.success("yes")
    script.console.failure("no")
    script.console.info("plain")

    assert script.output == ["yes", "no", "plain"]


def test_default_console_prints_to_standard_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    Console(use_color=False).info("hello")

    assert capsys.readouterr().out == "hello\n"


# --- Quiz loop -------------------------------------------------------------


def make_session(cards: list[Flashcard]) -> QuizSession:
    return QuizSession(SequentialMode(cards))


def test_run_quiz_shows_feedback_for_each_answer(cards: list[Flashcard]) -> None:
    script = ScriptedConsole(
        ["application programming interface", "wrong", "domain name system", "tls"]
    )

    finished = run_quiz(make_session(cards), script.console)

    assert finished is True
    assert script.output.count("Correct!") == 2
    assert "Incorrect. The answer is: Content Delivery Network" in script.output
    assert "Incorrect. The answer is: Transport Layer Security" in script.output


def test_run_quiz_uses_green_and_red_feedback(cards: list[Flashcard]) -> None:
    lines: list[str] = []
    answers = iter(["application programming interface", "wrong"])
    console = Console(
        input_fn=lambda prompt: next(answers),
        output_fn=lines.append,
        use_color=True,
    )

    run_quiz(QuizSession(SequentialMode(cards[:2])), console)

    assert f"{GREEN}Correct!{RESET}" in lines
    assert any(line.startswith(RED) for line in lines)


def test_run_quiz_numbers_the_questions(cards: list[Flashcard]) -> None:
    script = ScriptedConsole(["a", "b"])

    run_quiz(QuizSession(SequentialMode(cards[:2])), script.console)

    assert "Q1: API" in script.prompts[0]
    assert "Q2: CDN" in script.prompts[1]


@pytest.mark.parametrize("exit_text", ["exit", "EXIT", "  Exit  "])
def test_run_quiz_stops_when_the_user_types_exit(
    cards: list[Flashcard], exit_text: str
) -> None:
    script = ScriptedConsole(["application programming interface", exit_text])
    session = make_session(cards)

    finished = run_quiz(session, script.console)

    assert finished is False
    assert session.stats.total == 1  # "exit" is not counted as an answer
    assert "Quiz stopped." in script.output


def test_run_quiz_treats_exit_as_an_answer_when_it_is_the_real_answer() -> None:
    deck = [Flashcard("Which function ends the program?", "exit")]
    script = ScriptedConsole(["exit"])
    session = make_session(deck)

    finished = run_quiz(session, script.console)

    assert finished is True
    assert session.stats.correct == 1


def test_run_quiz_handles_ctrl_c_without_an_error(cards: list[Flashcard]) -> None:
    script = ScriptedConsole(["x", KeyboardInterrupt()])
    session = make_session(cards)

    finished = run_quiz(session, script.console)

    assert finished is False
    assert session.stats.total == 1
    assert any("Quiz stopped." in line for line in script.output)


def test_run_quiz_handles_end_of_input(cards: list[Flashcard]) -> None:
    script = ScriptedConsole([])  # no input at all: EOFError on the first prompt

    assert run_quiz(make_session(cards), script.console) is False


def test_run_quiz_works_with_the_adaptive_mode(cards: list[Flashcard]) -> None:
    from utils.quiz_engine import AdaptiveMode

    script = ScriptedConsole(["wrong"] * 4)
    session = QuizSession(AdaptiveMode(cards[:1], random.Random(0), max_retries=1))

    run_quiz(session, script.console)

    assert session.stats.total == 2  # asked once, then repeated once


# --- Rendering -------------------------------------------------------------


def test_render_summary_shows_totals_accuracy_and_missed_terms() -> None:
    stats = SessionStats(total=4, correct=3, missed=["DNS"])

    table = render_summary(stats)

    assert re.search(r"Total questions\s+: 4", table)
    assert re.search(r"Accuracy\s+: 75\.0%", table)
    assert re.search(r"Missed terms\s+: 1", table)
    assert "  - DNS" in table


def test_render_summary_says_none_when_nothing_was_missed() -> None:
    assert re.search(r"Missed terms\s+: none", render_summary(SessionStats(2, 2)))


def test_render_summary_lists_every_missed_term_on_its_own_row() -> None:
    table = render_summary(SessionStats(total=3, correct=1, missed=["A", "B"]))

    assert "  - A" in table
    assert "  - B" in table


def test_render_summary_keeps_long_terms_within_the_maximum_width() -> None:
    long_term = "Which keyword handles an exception raised in a try block? " * 3
    table = render_summary(SessionStats(total=2, correct=0, missed=[long_term]))

    assert max(len(line) for line in table.splitlines()) <= MAX_TABLE_WIDTH + 4
    assert table.count("exception raised") == 3  # nothing was cut off


def test_render_summary_wraps_a_single_unbreakable_word() -> None:
    table = render_summary(SessionStats(total=1, correct=0, missed=["x" * 200]))

    assert max(len(line) for line in table.splitlines()) <= MAX_TABLE_WIDTH + 4


def test_render_summary_draws_an_aligned_box() -> None:
    lines = render_summary(SessionStats(total=1, correct=1)).splitlines()

    assert len({len(line) for line in lines}) == 1
    assert lines[0].startswith("+") and lines[0].endswith("+")


def test_render_lifetime_stats_without_history() -> None:
    message = render_lifetime_stats("deck.json", LifetimeStats())

    assert "No saved sessions" in message


def test_render_lifetime_stats_with_history() -> None:
    stats = LifetimeStats(
        sessions=2, total=10, correct=7, hardest=[("DNS", 3), ("TLS", 1)]
    )

    table = render_lifetime_stats("deck.json", stats)

    assert re.search(r"Sessions played\s+: 2", table)
    assert re.search(r"Lifetime accuracy\s+: 70\.0%", table)
    assert re.search(r"Hardest cards\s+: 2", table)
    assert "  - DNS (missed 3x)" in table
    assert "  - TLS (missed 1x)" in table


def test_render_lifetime_stats_with_a_perfect_record() -> None:
    table = render_lifetime_stats("d", LifetimeStats(sessions=1, total=2, correct=2))

    assert "Hardest cards" in table
    assert "none" in table
