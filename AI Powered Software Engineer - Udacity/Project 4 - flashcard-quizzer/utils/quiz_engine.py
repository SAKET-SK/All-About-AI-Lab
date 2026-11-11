"""Quiz engine: card-selection strategies, a factory and the quiz session.

Design patterns used here:

* **Strategy** - :class:`QuizMode` is the abstract strategy that decides which
  card is asked next. :class:`SequentialMode`, :class:`RandomMode` and
  :class:`AdaptiveMode` are interchangeable concrete strategies, and
  :class:`QuizSession` (the context) works with any of them.
* **Factory** - :class:`QuizModeFactory` turns a mode name from the command line
  into the right strategy object, and new modes can be registered without
  changing existing code.
"""

import random
from abc import ABC, abstractmethod
from collections import deque
from typing import ClassVar, Sequence

from utils.models import AnswerResult, Flashcard, SessionStats


def normalize_answer(text: str) -> str:
    """Normalise text for comparison: case-insensitive, whitespace-tolerant.

    Args:
        text: Raw user input or a card's expected answer.

    Returns:
        The text lower-cased with leading/trailing spaces removed and runs of
        whitespace collapsed to single spaces.
    """
    return " ".join(text.casefold().split())


class UnknownQuizModeError(ValueError):
    """Raised when a quiz mode name is not registered with the factory."""


class QuizMode(ABC):
    """Strategy interface: decides which flashcard is asked next.

    Subclasses implement :meth:`next_card`. They may also override
    :meth:`record_result` to react to the user's answers.
    """

    name: ClassVar[str] = ""

    def __init__(
        self, cards: Sequence[Flashcard], rng: random.Random | None = None
    ) -> None:
        """Store the deck and the random generator used by the mode.

        Args:
            cards: The deck to quiz on. Must not be empty.
            rng: Random generator, injectable so tests can be deterministic.

        Raises:
            ValueError: If the deck is empty.
        """
        if not cards:
            raise ValueError("A quiz needs at least one card.")
        self._cards: list[Flashcard] = list(cards)
        # Shuffling flashcards is not security sensitive, so the standard
        # (non-cryptographic) generator is the right tool.
        default_rng = random.Random()  # nosec B311
        self._rng: random.Random = rng if rng is not None else default_rng

    @abstractmethod
    def next_card(self) -> Flashcard | None:
        """Return the next card to ask, or ``None`` when the quiz is over."""

    def record_result(self, card: Flashcard, correct: bool) -> None:
        """Tell the mode how the user did; the default does nothing.

        Args:
            card: The card that was just answered.
            correct: Whether the answer was correct.
        """


class _FixedOrderMode(QuizMode):
    """Shared behaviour for modes that ask every card once in a fixed order."""

    def __init__(
        self, cards: Sequence[Flashcard], rng: random.Random | None = None
    ) -> None:
        super().__init__(cards, rng)
        self._order: list[Flashcard] = self._build_order()
        self._position = 0

    @abstractmethod
    def _build_order(self) -> list[Flashcard]:
        """Return the order in which the cards will be asked."""

    def next_card(self) -> Flashcard | None:
        """Return the next card in the prepared order, or ``None`` at the end."""
        if self._position >= len(self._order):
            return None
        card = self._order[self._position]
        self._position += 1
        return card


class SequentialMode(_FixedOrderMode):
    """Ask the cards in deck order: 1, 2, 3, ... N."""

    name = "sequential"

    def _build_order(self) -> list[Flashcard]:
        return list(self._cards)


class RandomMode(_FixedOrderMode):
    """Ask every card once, in shuffled order."""

    name = "random"

    def _build_order(self) -> list[Flashcard]:
        order = list(self._cards)
        self._rng.shuffle(order)
        return order


class AdaptiveMode(QuizMode):
    """Prioritise cards the user gets wrong.

    The deck is shuffled once. A card answered correctly is retired. A card
    answered wrongly is put back in the queue ``retry_gap`` cards later, up to
    ``max_retries`` times, so difficult cards come back until they are learned.
    The quiz ends when the queue is empty.
    """

    name = "adaptive"

    def __init__(
        self,
        cards: Sequence[Flashcard],
        rng: random.Random | None = None,
        retry_gap: int = 2,
        max_retries: int = 3,
    ) -> None:
        """Create the adaptive queue.

        Args:
            cards: The deck to quiz on. Must not be empty.
            rng: Random generator used for the initial shuffle.
            retry_gap: How many cards are asked before a missed card returns.
            max_retries: Maximum number of times one card is re-queued.

        Raises:
            ValueError: If the deck is empty, ``retry_gap`` is below 1 or
                ``max_retries`` is negative.
        """
        super().__init__(cards, rng)
        if retry_gap < 1:
            raise ValueError("retry_gap must be at least 1.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        self._retry_gap = retry_gap
        self._max_retries = max_retries
        self._retries: dict[Flashcard, int] = {}
        order = list(self._cards)
        self._rng.shuffle(order)
        self._queue: deque[Flashcard] = deque(order)

    def next_card(self) -> Flashcard | None:
        """Return the next queued card, or ``None`` when nothing is left."""
        if not self._queue:
            return None
        return self._queue.popleft()

    def record_result(self, card: Flashcard, correct: bool) -> None:
        """Re-queue a wrongly answered card while it has retries left.

        Args:
            card: The card that was just answered.
            correct: Whether the answer was correct.
        """
        if correct:
            return
        used = self._retries.get(card, 0)
        if used >= self._max_retries:
            return
        self._retries[card] = used + 1
        self._queue.insert(min(self._retry_gap, len(self._queue)), card)


class QuizModeFactory:
    """Factory that creates the quiz mode matching a name."""

    _registry: ClassVar[dict[str, type[QuizMode]]] = {
        SequentialMode.name: SequentialMode,
        RandomMode.name: RandomMode,
        AdaptiveMode.name: AdaptiveMode,
    }

    @classmethod
    def available(cls) -> list[str]:
        """Return the registered mode names in registration order."""
        return list(cls._registry)

    @classmethod
    def register(cls, mode_class: type[QuizMode]) -> None:
        """Add a new mode so it can be created by name.

        Args:
            mode_class: A concrete :class:`QuizMode` with a non-empty ``name``.

        Raises:
            ValueError: If the class has no name, or the name is already used
                by a different mode (so built-in modes are never replaced
                by accident).
        """
        if not mode_class.name:
            raise ValueError("A quiz mode needs a non-empty name.")
        existing = cls._registry.get(mode_class.name)
        if existing is not None and existing is not mode_class:
            raise ValueError(f"A quiz mode named '{mode_class.name}' already exists.")
        cls._registry[mode_class.name] = mode_class

    @classmethod
    def create(
        cls,
        name: str,
        cards: Sequence[Flashcard],
        rng: random.Random | None = None,
    ) -> QuizMode:
        """Build the mode registered under ``name``.

        Args:
            name: Mode name, matched case-insensitively.
            cards: The deck to quiz on.
            rng: Optional random generator passed to the mode.

        Returns:
            A new quiz mode instance.

        Raises:
            UnknownQuizModeError: If ``name`` is not registered.
        """
        mode_class = cls._registry.get(name.strip().casefold())
        if mode_class is None:
            choices = ", ".join(cls.available())
            raise UnknownQuizModeError(
                f"Unknown quiz mode '{name}'. Choose one of: {choices}."
            )
        return mode_class(cards, rng)


class QuizSession:
    """Context that runs a quiz using whichever :class:`QuizMode` it is given."""

    def __init__(self, mode: QuizMode, limit: int | None = None) -> None:
        """Create a session.

        Args:
            mode: The strategy that chooses the cards.
            limit: Optional maximum number of questions to ask.

        Raises:
            ValueError: If ``limit`` is given and is not positive.
        """
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1.")
        self._mode = mode
        self._limit = limit
        self._current: Flashcard | None = None
        self.stats = SessionStats()

    def next_card(self) -> Flashcard | None:
        """Return the next card, or ``None`` when the quiz is finished."""
        if self._limit is not None and self.stats.total >= self._limit:
            self._current = None
        else:
            self._current = self._mode.next_card()
        return self._current

    def submit(self, answer: str) -> AnswerResult:
        """Check an answer for the card most recently returned.

        Args:
            answer: The text the user typed.

        Returns:
            The result, after statistics and the mode have been updated.

        Raises:
            RuntimeError: If there is no current card to answer.
        """
        if self._current is None:
            raise RuntimeError("No active card: call next_card() first.")
        card = self._current
        correct = normalize_answer(answer) == normalize_answer(card.back)
        self.stats.record(card, correct)
        self._mode.record_result(card, correct)
        self._current = None
        return AnswerResult(card=card, given=answer, correct=correct)
