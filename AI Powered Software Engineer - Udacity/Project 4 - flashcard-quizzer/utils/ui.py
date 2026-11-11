"""Terminal user interface: colours, the quiz loop and text rendering.

All input and output goes through :class:`Console`, whose functions are
injected, so the quiz loop can be tested without a real terminal.
"""

import os
import textwrap
from dataclasses import dataclass
from typing import Callable, Mapping, TextIO

from utils.history import LifetimeStats
from utils.models import SessionStats
from utils.quiz_engine import QuizSession, normalize_answer

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"
EXIT_WORD = "exit"
MAX_TABLE_WIDTH = 76  # keeps tables readable in an 80-column terminal


def should_use_color(
    stream: TextIO, disabled: bool = False, env: Mapping[str, str] | None = None
) -> bool:
    """Decide whether ANSI colours should be printed.

    Args:
        stream: The stream colours would be written to.
        disabled: True when the user passed ``--no-color``.
        env: Environment variables (defaults to ``os.environ``).

    Returns:
        False if disabled, if ``NO_COLOR`` is set, or if the stream is not a
        terminal; otherwise True.
    """
    environment = os.environ if env is None else env
    if disabled or "NO_COLOR" in environment:
        return False
    return stream.isatty()


def _default_input(prompt: str) -> str:
    """Read a line with ``input``, looked up on every call (not at import)."""
    return input(prompt)


def _default_output(text: str) -> None:
    """Print a line with ``print``, looked up on every call (not at import)."""
    print(text)


@dataclass
class Console:
    """Input/output helper with optional colour.

    Attributes:
        input_fn: Reads one line, given a prompt (``input`` by default).
        output_fn: Writes one line (``print`` by default).
        error_fn: Writes one error line.
        use_color: Whether to wrap text in ANSI colour codes.
    """

    input_fn: Callable[[str], str] = _default_input
    output_fn: Callable[[str], None] = _default_output
    error_fn: Callable[[str], None] = _default_output
    use_color: bool = True

    def colorize(self, text: str, color: str) -> str:
        """Wrap ``text`` in a colour code when colour is enabled."""
        if not self.use_color:
            return text
        return f"{color}{text}{RESET}"

    def info(self, text: str = "") -> None:
        """Print a plain line."""
        self.output_fn(text)

    def success(self, text: str) -> None:
        """Print a green line, used for correct answers."""
        self.output_fn(self.colorize(text, GREEN))

    def failure(self, text: str) -> None:
        """Print a red line, used for incorrect answers."""
        self.output_fn(self.colorize(text, RED))

    def error(self, text: str) -> None:
        """Print an error line (to stderr in the real application)."""
        self.error_fn(self.colorize(text, RED))

    def ask(self, prompt: str) -> str:
        """Read one line of input."""
        return self.input_fn(prompt)


def run_quiz(session: QuizSession, console: Console) -> bool:
    """Ask questions until the session ends or the user quits.

    The user can type ``exit`` (unless it is the card's real answer), press
    Ctrl+C or send end-of-input to leave early; none of these raise errors.

    Args:
        session: The session supplying cards and tracking statistics.
        console: Where prompts and feedback are shown.

    Returns:
        True if every question was asked, False if the user quit early.
    """
    console.info(f"Type '{EXIT_WORD}' or press Ctrl+C to stop at any time.")
    number = 0
    while True:
        card = session.next_card()
        if card is None:
            return True
        number += 1
        try:
            answer = console.ask(f"\nQ{number}: {card.front}\n> ")
        except (KeyboardInterrupt, EOFError):
            console.info("\nQuiz stopped.")
            return False
        wants_exit = normalize_answer(answer) == EXIT_WORD
        if wants_exit and normalize_answer(card.back) != EXIT_WORD:
            console.info("Quiz stopped.")
            return False
        result = session.submit(answer)
        if result.correct:
            console.success("Correct!")
        else:
            console.failure(f"Incorrect. The answer is: {card.back}")


def render_summary(stats: SessionStats) -> str:
    """Render the end-of-session summary as a text table.

    Args:
        stats: Statistics of the finished session.

    Returns:
        A multi-line table with total questions, accuracy and one row for each
        missed term.
    """
    rows = [
        ("Total questions", str(stats.total)),
        ("Correct answers", str(stats.correct)),
        ("Accuracy", f"{stats.accuracy:.1f}%"),
        ("Missed terms", str(len(stats.missed)) if stats.missed else "none"),
    ]
    return _render_table("Session summary", rows, stats.missed)


def render_lifetime_stats(deck: str, stats: LifetimeStats) -> str:
    """Render lifetime statistics for a deck as a text table.

    Args:
        deck: Deck identifier shown in the title.
        stats: Totals across all saved sessions.

    Returns:
        A multi-line table, or a short message when nothing is saved yet.
    """
    if stats.sessions == 0:
        return f"No saved sessions for {deck} yet. Play a quiz first."
    rows = [
        ("Sessions played", str(stats.sessions)),
        ("Total questions", str(stats.total)),
        ("Lifetime accuracy", f"{stats.accuracy:.1f}%"),
        ("Hardest cards", str(len(stats.hardest)) if stats.hardest else "none"),
    ]
    items = [f"{front} (missed {count}x)" for front, count in stats.hardest]
    return _render_table(f"Lifetime statistics: {deck}", rows, items)


def _render_table(
    title: str, rows: list[tuple[str, str]], items: list[str] | None = None
) -> str:
    """Draw a bordered table: label/value rows, then an optional bullet list.

    Long text is wrapped so the table never exceeds ``MAX_TABLE_WIDTH``.
    """
    label_width = max(len(label) for label, _ in rows)
    body: list[str] = []
    for label, value in rows:
        body.extend(
            _wrap(f"{label.ljust(label_width)} : {value}", indent=label_width + 3)
        )
    for item in items or []:
        body.extend(_wrap(f"  - {item}", indent=4))
    inner = max(len(line) for line in [title, *body])
    border = "+" + "-" * (inner + 2) + "+"
    lines = [border, f"| {title.ljust(inner)} |", border]
    lines.extend(f"| {line.ljust(inner)} |" for line in body)
    lines.append(border)
    return "\n".join(lines)


def _wrap(text: str, indent: int) -> list[str]:
    """Wrap one table line to the maximum width, indenting continuation lines."""
    return textwrap.wrap(
        text,
        width=MAX_TABLE_WIDTH,
        subsequent_indent=" " * indent,
        break_long_words=True,
    ) or [""]
