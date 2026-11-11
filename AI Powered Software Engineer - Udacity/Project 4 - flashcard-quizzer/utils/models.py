"""Core data models shared by the loader, the quiz engine and the UI."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Flashcard:
    """A single question/answer pair.

    Attributes:
        front: The prompt shown to the user (for example an acronym).
        back: The expected answer.
    """

    front: str
    back: str


@dataclass(frozen=True)
class AnswerResult:
    """Outcome of one submitted answer.

    Attributes:
        card: The card that was asked.
        given: The raw text the user typed.
        correct: Whether the answer matched the card's back.
    """

    card: Flashcard
    given: str
    correct: bool


@dataclass
class SessionStats:
    """Running statistics for one quiz session.

    Attributes:
        total: Number of answers submitted (repeats in adaptive mode count).
        correct: Number of correct answers.
        missed: Fronts of cards answered wrongly at least once, in the order
            they were first missed, without duplicates.
    """

    total: int = 0
    correct: int = 0
    missed: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """Return the percentage of correct answers, or 0.0 with no answers."""
        if self.total == 0:
            return 0.0
        return 100.0 * self.correct / self.total

    def record(self, card: Flashcard, correct: bool) -> None:
        """Add one answer to the statistics.

        Args:
            card: The card that was answered.
            correct: Whether the answer was correct.
        """
        self.total += 1
        if correct:
            self.correct += 1
        elif card.front not in self.missed:
            self.missed.append(card.front)
