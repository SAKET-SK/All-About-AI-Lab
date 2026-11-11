"""Tests for the command-line interface in ``main.py``."""

import subprocess
import sys
from pathlib import Path

import pytest

import main
from tests.conftest import DeckWriter, ScriptedConsole

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS = [
    {"front": "API", "back": "Application Programming Interface"},
    {"front": "CDN", "back": "Content Delivery Network"},
]


@pytest.fixture
def deck(write_deck: DeckWriter) -> Path:
    return write_deck(CARDS)


@pytest.fixture
def history_file(tmp_path: Path) -> Path:
    return tmp_path / "history.json"


def run(
    args: list[str], answers: list[str], history_file: Path
) -> tuple[int, ScriptedConsole]:
    """Run main() with scripted input and an isolated history file."""
    script = ScriptedConsole(answers)
    code = main.main([*args, "--history-file", str(history_file)], script.console)
    return code, script


# --- Arguments -------------------------------------------------------------


def test_help_lists_every_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main.main(["--help"])

    out = capsys.readouterr().out
    assert info.value.code == 0
    for flag in ("--file", "--mode", "--stats", "--limit", "--seed", "--no-color"):
        assert flag in out


def test_an_unknown_mode_is_rejected_by_argparse(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as info:
        main.main(["--mode", "bogus"])

    assert info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["0", "-3", "many"])
def test_limit_must_be_a_positive_whole_number(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as info:
        main.main(["--limit", value])

    assert info.value.code == 2
    assert "--limit" in capsys.readouterr().err


def test_mode_names_are_case_insensitive(deck: Path, history_file: Path) -> None:
    code, script = run(["-f", str(deck), "-m", "RANDOM"], ["x", "y"], history_file)

    assert code == 0
    assert "Total questions" in script.text


# --- Running a quiz --------------------------------------------------------


def test_sequential_session_shows_summary(deck: Path, history_file: Path) -> None:
    code, script = run(
        ["-f", str(deck), "-m", "sequential"],
        ["application programming interface", "wrong"],
        history_file,
    )

    assert code == 0
    assert "Correct!" in script.output
    assert "Accuracy" in script.text and "50.0%" in script.text
    assert "CDN" in script.text  # listed as a missed term


def test_the_default_mode_is_sequential(deck: Path, history_file: Path) -> None:
    _, script = run(["-f", str(deck)], ["a", "b"], history_file)

    assert "Q1: API" in script.prompts[0]


def test_adaptive_session_repeats_missed_cards(deck: Path, history_file: Path) -> None:
    code, script = run(
        ["-f", str(deck), "-m", "adaptive", "--seed", "1"],
        ["wrong"] * 20,
        history_file,
    )

    assert code == 0
    assert len(script.prompts) > 2  # missed cards were asked again


def test_limit_caps_the_number_of_questions(deck: Path, history_file: Path) -> None:
    _, script = run(["-f", str(deck), "-n", "1"], ["a", "b"], history_file)

    assert len(script.prompts) == 1


def test_seed_makes_random_order_repeatable(
    write_deck: DeckWriter, history_file: Path
) -> None:
    big = write_deck([{"front": f"Q{i}", "back": f"A{i}"} for i in range(12)])
    args = ["-f", str(big), "-m", "random", "--seed", "42", "--no-save"]

    _, first = run(args, ["x"] * 12, history_file)
    _, second = run(args, ["x"] * 12, history_file)

    assert first.prompts == second.prompts


def test_exit_still_prints_the_summary(deck: Path, history_file: Path) -> None:
    code, script = run(["-f", str(deck)], ["exit"], history_file)

    assert code == 0
    assert "Session summary" in script.text


def test_ctrl_c_exits_cleanly(deck: Path, history_file: Path) -> None:
    script = ScriptedConsole(["x", KeyboardInterrupt()])

    code = main.main(
        ["-f", str(deck), "--history-file", str(history_file)], script.console
    )

    assert code == 0
    assert "Session summary" in script.text


# --- Errors ----------------------------------------------------------------


def test_a_missing_deck_gives_a_friendly_error(history_file: Path) -> None:
    code, script = run(["-f", "no_such_deck.json"], [], history_file)

    assert code == 1
    assert script.errors == ["Error: File not found: no_such_deck.json"]


def test_a_malformed_deck_gives_a_friendly_error(
    tmp_path: Path, history_file: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")

    code, script = run(["-f", str(bad)], [], history_file)

    assert code == 1
    assert "Invalid JSON" in script.errors[0]


def test_a_card_without_a_back_gives_a_friendly_error(
    write_deck: DeckWriter, history_file: Path
) -> None:
    bad = write_deck([{"front": "API"}])

    code, script = run(["-f", str(bad)], [], history_file)

    assert code == 1
    assert 'missing or empty "back"' in script.errors[0]


# --- History and statistics ------------------------------------------------


def test_a_finished_session_is_saved_to_history(deck: Path, history_file: Path) -> None:
    run(["-f", str(deck)], ["x", "y"], history_file)

    assert history_file.exists()


def test_no_save_skips_writing_history(deck: Path, history_file: Path) -> None:
    run(["-f", str(deck), "--no-save"], ["x", "y"], history_file)

    assert not history_file.exists()


def test_a_session_with_no_answers_is_not_saved(deck: Path, history_file: Path) -> None:
    run(["-f", str(deck)], ["exit"], history_file)

    assert not history_file.exists()


def test_stats_flag_reports_lifetime_statistics(deck: Path, history_file: Path) -> None:
    run(["-f", str(deck)], ["application programming interface", "wrong"], history_file)
    run(["-f", str(deck)], ["wrong", "wrong"], history_file)

    code, script = run(["-f", str(deck), "--stats"], [], history_file)

    assert code == 0
    assert "Sessions played" in script.text
    assert "25.0%" in script.text  # 1 correct out of 4 answers
    assert script.prompts == []  # no quiz was started


def test_stats_flag_without_history_explains_itself(
    deck: Path, history_file: Path
) -> None:
    code, script = run(["-f", str(deck), "--stats"], [], history_file)

    assert code == 0
    assert "No saved sessions" in script.text


def test_stats_flag_with_a_corrupt_history_file(deck: Path, history_file: Path) -> None:
    history_file.write_text("corrupt", encoding="utf-8")

    code, script = run(["-f", str(deck), "--stats"], [], history_file)

    assert code == 1
    assert "unreadable" in script.errors[0]


def test_a_corrupt_history_does_not_stop_the_quiz(
    deck: Path, history_file: Path
) -> None:
    history_file.write_text("corrupt", encoding="utf-8")

    code, script = run(["-f", str(deck)], ["x", "y"], history_file)

    assert code == 0
    assert "Session summary" in script.text
    assert script.errors and script.errors[0].startswith("Warning: session not saved")
    assert history_file.read_text(encoding="utf-8") == "corrupt"


# --- Default console -------------------------------------------------------


def test_the_default_console_sends_errors_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main.main(["-f", "no_such_deck.json"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.strip() == "Error: File not found: no_such_deck.json"
    assert captured.out == ""


def test_the_default_console_reads_from_standard_input(
    deck: Path,
    history_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(["application programming interface", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    code = main.main(["-f", str(deck), "--history-file", str(history_file)])

    assert code == 0
    assert "Correct!" in capsys.readouterr().out


# --- Real process ----------------------------------------------------------


def run_process(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PROJECT_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_process_help_works() -> None:
    result = run_process(["--help"])

    assert result.returncode == 0
    assert "--mode" in result.stdout


def test_process_full_game_has_no_traceback(history_file: Path) -> None:
    result = run_process(
        [
            "-m",
            "adaptive",
            "-f",
            "data/python_basics.json",
            "--seed",
            "1",
            "--history-file",
            str(history_file),
        ],
        stdin="def\nwrong\n" * 40,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "Session summary" in result.stdout


def test_process_missing_file_prints_one_line_error() -> None:
    result = run_process(["-f", "nope.json"])

    assert result.returncode == 1
    assert result.stderr.strip() == "Error: File not found: nope.json"


def test_process_works_from_another_working_directory(
    tmp_path: Path, history_file: Path
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--stats",
            "--history-file",
            str(history_file),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "No saved sessions" in result.stdout
