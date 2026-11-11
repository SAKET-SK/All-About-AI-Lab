"""Entry point for the Flashcard Quizzer command-line application.

Example::

    python main.py --mode adaptive --file data/python_basics.json
    python main.py --stats --file data/glossary.json
"""

import argparse
import random
import sys
from pathlib import Path
from typing import Sequence

from utils.data_loader import FlashcardLoadError, load_flashcards
from utils.history import (
    HistoryError,
    HistoryStore,
    SessionRecord,
    default_history_path,
)
from utils.quiz_engine import QuizModeFactory, QuizSession
from utils.ui import (
    Console,
    render_lifetime_stats,
    render_summary,
    run_quiz,
    should_use_color,
)

DEFAULT_DECK = Path(__file__).resolve().parent / "data" / "glossary.json"


def _positive_int(text: str) -> int:
    """Argparse type that accepts only integers of at least 1."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a whole number.") from None
    if value < 1:
        raise argparse.ArgumentTypeError("the value must be at least 1.")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Quiz yourself with flashcards loaded from a JSON file.",
    )
    parser.add_argument(
        "-f",
        "--file",
        default=str(DEFAULT_DECK),
        help="path to the JSON deck (default: data/glossary.json)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        default="sequential",
        type=str.lower,
        choices=QuizModeFactory.available(),
        help="how cards are chosen: sequential, random or adaptive "
        "(adaptive repeats the cards you miss)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="show lifetime statistics for the deck and exit",
    )
    parser.add_argument(
        "-n", "--limit", type=_positive_int, help="stop after this many questions"
    )
    parser.add_argument(
        "--seed", type=int, help="seed the random generator for repeatable runs"
    )
    parser.add_argument("--no-color", action="store_true", help="disable colours")
    parser.add_argument(
        "--no-save", action="store_true", help="do not record this session"
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        default=default_history_path(),
        help="where session history is stored (default: %(default)s)",
    )
    return parser


def _show_lifetime_stats(deck: str, store: HistoryStore, console: Console) -> int:
    """Print lifetime statistics for ``deck`` and return an exit code."""
    try:
        stats = store.summarize(deck)
    except HistoryError as exc:
        console.error(f"Error: {exc}")
        return 1
    console.info(render_lifetime_stats(deck, stats))
    return 0


def _save_session(store: HistoryStore, record: SessionRecord, console: Console) -> None:
    """Save a finished session, warning (not failing) if that is impossible."""
    try:
        store.append(record)
    except HistoryError as exc:
        console.error(f"Warning: session not saved. {exc}")


def main(argv: Sequence[str] | None = None, console: Console | None = None) -> int:
    """Run the application.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).
        console: Console to use; tests pass one with scripted input.

    Returns:
        The process exit code: 0 on success, 1 for a deck or history problem.
    """
    args = build_parser().parse_args(argv)
    if console is None:
        console = Console(
            error_fn=lambda text: print(text, file=sys.stderr),
            use_color=should_use_color(sys.stdout, args.no_color),
        )
    deck = str(Path(args.file).resolve())
    store = HistoryStore(args.history_file)
    if args.stats:
        return _show_lifetime_stats(deck, store, console)
    try:
        cards = load_flashcards(args.file)
    except FlashcardLoadError as exc:
        console.error(f"Error: {exc}")
        return 1
    # The generator only shuffles flashcards, so it is not security sensitive.
    rng = random.Random(args.seed)  # nosec B311
    session = QuizSession(QuizModeFactory.create(args.mode, cards, rng), args.limit)
    run_quiz(session, console)
    stats = session.stats
    console.info("")
    console.info(render_summary(stats))
    if stats.total and not args.no_save:
        record = SessionRecord.create(
            deck, args.mode, stats.total, stats.correct, stats.missed
        )
        _save_session(store, record, console)
    return 0


if __name__ == "__main__":
    sys.exit(main())
