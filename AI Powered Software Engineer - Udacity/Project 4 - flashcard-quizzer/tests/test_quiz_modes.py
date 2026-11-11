"""Tests for the quiz modes (Strategy), the factory and the quiz session."""

import random

import pytest

from utils.models import Flashcard
from utils.quiz_engine import (
    AdaptiveMode,
    QuizMode,
    QuizModeFactory,
    QuizSession,
    RandomMode,
    SequentialMode,
    UnknownQuizModeError,
    normalize_answer,
)


def drain(mode: QuizMode) -> list[Flashcard]:
    """Collect every card a mode hands out, answering each correctly."""
    asked: list[Flashcard] = []
    while (card := mode.next_card()) is not None:
        asked.append(card)
        mode.record_result(card, True)
    return asked


# --- Factory ---------------------------------------------------------------


def test_quiz_mode_factory(cards: list[Flashcard]) -> None:
    assert isinstance(QuizModeFactory.create("sequential", cards), SequentialMode)
    assert isinstance(QuizModeFactory.create("random", cards), RandomMode)
    assert isinstance(QuizModeFactory.create("adaptive", cards), AdaptiveMode)


def test_quiz_mode_factory_ignores_case_and_spaces(cards: list[Flashcard]) -> None:
    assert isinstance(QuizModeFactory.create("  RANDOM ", cards), RandomMode)


def test_quiz_mode_factory_rejects_unknown_name(cards: list[Flashcard]) -> None:
    with pytest.raises(UnknownQuizModeError, match="adaptive, random|sequential"):
        QuizModeFactory.create("spaced", cards)


def test_quiz_mode_factory_lists_available_modes() -> None:
    assert QuizModeFactory.available() == ["sequential", "random", "adaptive"]


def test_quiz_mode_factory_passes_the_rng_to_the_mode(cards: list[Flashcard]) -> None:
    first = drain(QuizModeFactory.create("random", cards, random.Random(7)))
    second = drain(QuizModeFactory.create("random", cards, random.Random(7)))

    assert first == second


@pytest.mark.usefixtures("isolated_registry")
def test_quiz_mode_factory_accepts_new_modes(cards: list[Flashcard]) -> None:
    class ReverseMode(SequentialMode):
        name = "reverse"

        def _build_order(self) -> list[Flashcard]:
            return list(reversed(self._cards))

    QuizModeFactory.register(ReverseMode)

    mode = QuizModeFactory.create("reverse", cards)

    assert drain(mode) == list(reversed(cards))


@pytest.mark.usefixtures("isolated_registry")
def test_quiz_mode_factory_rejects_a_nameless_mode() -> None:
    class Nameless(QuizMode):
        def next_card(self) -> Flashcard | None:  # pragma: no cover
            return None

    with pytest.raises(ValueError, match="non-empty name"):
        QuizModeFactory.register(Nameless)


@pytest.mark.usefixtures("isolated_registry")
def test_quiz_mode_factory_never_replaces_a_built_in_mode(
    cards: list[Flashcard],
) -> None:
    class Imposter(SequentialMode):
        pass  # inherits the name "sequential" from SequentialMode

    with pytest.raises(ValueError, match="already exists"):
        QuizModeFactory.register(Imposter)

    assert type(QuizModeFactory.create("sequential", cards)) is SequentialMode


@pytest.mark.usefixtures("isolated_registry")
def test_quiz_mode_factory_allows_registering_the_same_mode_twice() -> None:
    QuizModeFactory.register(SequentialMode)

    assert QuizModeFactory.available().count("sequential") == 1


# --- Strategy base class ---------------------------------------------------


def test_quiz_mode_cannot_be_instantiated_directly(cards: list[Flashcard]) -> None:
    with pytest.raises(TypeError):
        QuizMode(cards)  # type: ignore[abstract]


@pytest.mark.parametrize("mode_name", ["sequential", "random", "adaptive"])
def test_every_mode_rejects_an_empty_deck(mode_name: str) -> None:
    with pytest.raises(ValueError, match="at least one card"):
        QuizModeFactory.create(mode_name, [])


# --- Sequential and random -------------------------------------------------


def test_sequential_mode_follows_deck_order(cards: list[Flashcard]) -> None:
    assert drain(SequentialMode(cards)) == cards


def test_sequential_mode_returns_none_when_finished(cards: list[Flashcard]) -> None:
    mode = SequentialMode(cards[:1])
    mode.next_card()

    assert mode.next_card() is None
    assert mode.next_card() is None


def test_random_mode_asks_every_card_exactly_once(cards: list[Flashcard]) -> None:
    asked = drain(RandomMode(cards, random.Random(3)))

    assert sorted(asked, key=lambda c: c.front) == sorted(cards, key=lambda c: c.front)


def test_random_mode_actually_shuffles(cards: list[Flashcard]) -> None:
    big_deck = [Flashcard(f"Q{i}", f"A{i}") for i in range(30)]

    assert drain(RandomMode(big_deck, random.Random(1))) != big_deck


def test_random_mode_does_not_modify_the_original_deck(
    cards: list[Flashcard],
) -> None:
    before = list(cards)
    drain(RandomMode(cards, random.Random(5)))

    assert cards == before


# --- Adaptive --------------------------------------------------------------


def test_adaptive_mode_behavior(cards: list[Flashcard]) -> None:
    mode = AdaptiveMode(cards, random.Random(0), retry_gap=2)
    first = mode.next_card()
    assert first is not None
    mode.record_result(first, False)  # the user gets the first card wrong

    following = [mode.next_card(), mode.next_card(), mode.next_card()]

    assert following[2] == first  # it comes back after `retry_gap` other cards
    assert following[0] != first and following[1] != first


def test_adaptive_mode_does_not_repeat_correct_cards(cards: list[Flashcard]) -> None:
    asked = drain(AdaptiveMode(cards, random.Random(0)))

    assert len(asked) == len(cards)


def test_adaptive_mode_keeps_repeating_a_card_until_it_is_answered_right(
    cards: list[Flashcard],
) -> None:
    mode = AdaptiveMode(cards[:1])
    asked = 0
    while (card := mode.next_card()) is not None:
        asked += 1
        mode.record_result(card, asked >= 3)  # wrong twice, right on the third

    assert asked == 3


def test_adaptive_mode_stops_retrying_after_max_retries(
    cards: list[Flashcard],
) -> None:
    mode = AdaptiveMode(cards[:1], max_retries=2)
    asked = 0
    while (card := mode.next_card()) is not None:
        asked += 1
        mode.record_result(card, False)  # never correct

    assert asked == 3  # the first time plus two retries


def test_adaptive_mode_repeats_immediately_when_the_queue_is_short(
    cards: list[Flashcard],
) -> None:
    mode = AdaptiveMode(cards[:2], random.Random(0), retry_gap=5)
    first = mode.next_card()
    assert first is not None
    mode.record_result(first, False)

    assert [mode.next_card(), mode.next_card()][1] == first  # after the other card


@pytest.mark.parametrize(
    ("retry_gap", "max_retries", "message"),
    [(0, 3, "retry_gap"), (2, -1, "max_retries")],
)
def test_adaptive_mode_validates_its_settings(
    cards: list[Flashcard], retry_gap: int, max_retries: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        AdaptiveMode(cards, retry_gap=retry_gap, max_retries=max_retries)


# --- Session ---------------------------------------------------------------


def test_normalize_answer_ignores_case_and_extra_whitespace() -> None:
    assert normalize_answer("  Domain   NAME\tSystem ") == "domain name system"


def test_session_marks_matching_answers_correct_ignoring_case(
    cards: list[Flashcard],
) -> None:
    session = QuizSession(SequentialMode(cards))
    card = session.next_card()
    assert card is not None

    result = session.submit("  application PROGRAMMING interface ")

    assert result.correct is True
    assert result.card == card


def test_session_marks_other_answers_incorrect(cards: list[Flashcard]) -> None:
    session = QuizSession(SequentialMode(cards))
    session.next_card()

    result = session.submit("no idea")

    assert result.correct is False
    assert session.stats.missed == ["API"]


def test_session_does_not_count_an_empty_answer_as_correct(
    cards: list[Flashcard],
) -> None:
    session = QuizSession(SequentialMode(cards))
    session.next_card()

    assert session.submit("").correct is False


def test_session_tracks_stats_across_answers(cards: list[Flashcard]) -> None:
    session = QuizSession(SequentialMode(cards))
    for answer in ["Application Programming Interface", "x", "Domain Name System"]:
        session.next_card()
        session.submit(answer)

    assert session.stats.total == 3
    assert session.stats.correct == 2
    assert session.stats.accuracy == pytest.approx(66.666, abs=0.01)
    assert session.stats.missed == ["CDN"]


def test_session_missed_terms_have_no_duplicates(cards: list[Flashcard]) -> None:
    session = QuizSession(AdaptiveMode(cards[:1], max_retries=2))
    while session.next_card() is not None:
        session.submit("wrong")

    assert session.stats.total == 3
    assert session.stats.missed == ["API"]


def test_session_stops_at_the_limit(cards: list[Flashcard]) -> None:
    session = QuizSession(SequentialMode(cards), limit=2)
    asked = 0
    while session.next_card() is not None:
        session.submit("x")
        asked += 1

    assert asked == 2


def test_session_rejects_a_non_positive_limit(cards: list[Flashcard]) -> None:
    with pytest.raises(ValueError, match="limit"):
        QuizSession(SequentialMode(cards), limit=0)


def test_session_submit_without_a_card_raises(cards: list[Flashcard]) -> None:
    session = QuizSession(SequentialMode(cards))

    with pytest.raises(RuntimeError, match="next_card"):
        session.submit("anything")


def test_session_cannot_submit_twice_for_one_card(cards: list[Flashcard]) -> None:
    session = QuizSession(SequentialMode(cards))
    session.next_card()
    session.submit("x")

    with pytest.raises(RuntimeError):
        session.submit("x")


def test_accuracy_is_zero_before_any_answer() -> None:
    from utils.models import SessionStats

    assert SessionStats().accuracy == 0.0
