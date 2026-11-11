# Flashcard Quizzer

A command-line flashcard trainer written in Python. Load a deck from a JSON file, pick how
the cards are served (in order, shuffled, or **adaptive**, which keeps re-asking what you
get wrong), and see a summary of how you did. It was built for the "AI-assisted
development" capstone: the code was written with an AI assistant and then reviewed,
tested and refined (see [AI-assisted development](#ai-assisted-development)).

## Features

- **Two deck formats.** A plain array `[{"front": "...", "back": "..."}]` or an object
  `{"cards": [...]}`. Bad files give a one-line, friendly error, never a traceback.
- **Three quiz modes** chosen with `-m`: `sequential`, `random` and `adaptive`.
- **Adaptive mode** re-queues a missed card a couple of questions later, so hard cards
  keep coming back until you know them.
- **Case-insensitive answers.** `  domain   NAME system ` matches `Domain Name System`.
- **Coloured feedback** (green for correct, red for incorrect). Colours switch off
  automatically when output is not a terminal, with `--no-color`, or when `NO_COLOR` is set.
- **Graceful exit.** Type `exit` or press Ctrl+C at any time. You still get the summary.
- **Session summary table** with total questions, accuracy and the terms you missed.
- **Lifetime statistics** (`--stats`): sessions played, accuracy over time and your
  hardest cards, from a small history file saved after each session.
- **Handy options:** `--limit N` to cap the number of questions, `--seed N` for repeatable
  shuffles, `--no-save` to skip recording a session.

## Requirements

- Python 3.10 or newer
- The app itself uses only the standard library. The dev tools (pytest, black, flake8, mypy,
  isort, bandit) are listed in `requirements.txt`.

## Setup

Run these from the project folder (the one containing `main.py`).

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate

python -m pip install -r requirements.txt
```

## Usage

```bash
python main.py --help
python main.py --mode sequential --file data/glossary.json
python main.py -m adaptive -f data/python_basics.json
python main.py -m random -f data/network_ports.json --limit 5
python main.py --stats -f data/python_basics.json
```

If you leave out `-f` the glossary deck is used, and if you leave out `-m` the mode is
`sequential`.

```text
usage: main.py [-h] [-f FILE] [-m {sequential,random,adaptive}] [--stats]
               [-n LIMIT] [--seed SEED] [--no-color] [--no-save]
               [--history-file HISTORY_FILE]

Quiz yourself with flashcards loaded from a JSON file.

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  path to the JSON deck (default: data/glossary.json)
  -m {sequential,random,adaptive}, --mode {sequential,random,adaptive}
                        how cards are chosen: sequential, random or adaptive
                        (adaptive repeats the cards you miss)
  --stats               show lifetime statistics for the deck and exit
  -n LIMIT, --limit LIMIT
                        stop after this many questions
  --seed SEED           seed the random generator for repeatable runs
  --no-color            disable colours
  --no-save             do not record this session
  --history-file HISTORY_FILE
                        where session history is stored (default:
                        ~/.flashcard_quizzer/history.json)
```

### Bundled decks

| File | Cards | Format |
|---|---|---|
| `data/glossary.json` | 10 | array |
| `data/python_basics.json` | 8 | object (`"cards"`) |
| `data/network_ports.json` | 8 | object (`"cards"`) |

### Writing your own deck

Create a `.json` file in `data/` using either layout. Every card needs a non-empty `front`
(the question) and `back` (the answer):

```json
[
  {"front": "API", "back": "Application Programming Interface"},
  {"front": "DNS", "back": "Domain Name System"}
]
```

### Example session (adaptive mode)

Two cards were missed on purpose. Notice that each one comes back two questions later
(Q5 returns as Q8, Q7 returns as Q10).

```text
Type 'exit' or press Ctrl+C to stop at any time.

Q1: Which keyword defines a function?
> def
Correct!

Q2: Which built-in function converts the string "42" to an integer?
> int
Correct!

Q3: Which keyword imports a module?
> import
Correct!

Q4: Which keyword starts a loop over the items of a sequence?
> for
Correct!

Q5: Which built-in function returns the length of a list?
> no idea
Incorrect. The answer is: len

Q6: Which mutable built-in type stores key-value pairs?
> dict
Correct!

Q7: Which keyword handles an exception raised in a try block?
> no idea
Incorrect. The answer is: except

Q8: Which built-in function returns the length of a list?
> len
Correct!

Q9: What is the boolean type called?
> bool
Correct!

Q10: Which keyword handles an exception raised in a try block?
> except
Correct!

+---------------------------------------------------------------+
| Session summary                                               |
+---------------------------------------------------------------+
| Total questions : 10                                          |
| Correct answers : 8                                           |
| Accuracy        : 80.0%                                       |
| Missed terms    : 2                                           |
|   - Which built-in function returns the length of a list?     |
|   - Which keyword handles an exception raised in a try block? |
+---------------------------------------------------------------+
```

## How adaptive mode works

1. The deck is shuffled once.
2. A card answered **correctly** is retired.
3. A card answered **wrongly** goes back into the queue `retry_gap` (2) cards later.
4. Each card can be re-queued at most `max_retries` (3) times, so the quiz always finishes.
5. The quiz ends when the queue is empty. Repeated questions count towards the total, and
   the missed list shows each term once.

## Architecture

```text
               +-----------------------------------------------+
               |                    main.py                    |
               |    parses flags, wires the pieces together    |
               +-----------------------------------------------+
                                       |
         +-------------------+---------+---------+-------------------+
         v                   v                   v                   v
+-----------------+ +-----------------+ +-----------------+ +-----------------+
| data_loader.py  | | quiz_engine.py  | |      ui.py      | |   history.py    |
| load + validate | | Strategy modes  | | Console + loop  | | saved sessions  |
|   JSON decks    | |Factory, Session | | summary tables  | | lifetime stats  |
+-----------------+ +-----------------+ +-----------------+ +-----------------+

+-----------------------------------------------------------------------------+
|    models.py: Flashcard, AnswerResult, SessionStats (shared data types)     |
+-----------------------------------------------------------------------------+
```

| Module | Responsibility |
|---|---|
| `main.py` | Command-line arguments, wiring, exit codes |
| `utils/models.py` | `Flashcard`, `AnswerResult`, `SessionStats` |
| `utils/data_loader.py` | Reading and validating JSON decks |
| `utils/quiz_engine.py` | Quiz modes (Strategy), `QuizModeFactory`, `QuizSession` |
| `utils/ui.py` | `Console` (injectable input/output), quiz loop, table rendering |
| `utils/history.py` | Saving sessions and computing lifetime statistics |

### Design patterns

**Strategy.** Sequential, random and adaptive are three algorithms for the same job,
choosing the next card. They share the abstract `QuizMode` interface, and `QuizSession`
works with any of them.

```text
+----------------+        +----------------------------------+
|  QuizSession   | uses   |       QuizMode (abstract)        |
| (the context)  |------->|   next_card(), record_result()   |
+----------------+        +----------------------------------+
                                            ^
                                            |
                                            |
            +-------------------------+-----+-------------------+
            |                         |                         |
+----------------------+  +----------------------+  +----------------------+
|    SequentialMode    |  |      RandomMode      |  |     AdaptiveMode     |
| cards 1, 2, 3 ... N  |  |    shuffled once     |  | re-asks missed cards |
+----------------------+  +----------------------+  +----------------------+
```

**Factory.** `QuizModeFactory.create("adaptive", cards)` turns the `-m` text into the right
strategy object, so `main.py` never needs an `if/elif` chain. Registering a new mode is
one call, and the factory refuses to replace a mode that already exists:

```python
class ReverseMode(SequentialMode):
    name = "reverse"

    def _build_order(self) -> list[Flashcard]:
        return list(reversed(self._cards))


QuizModeFactory.register(ReverseMode)  # now "-m reverse" works
```

Both patterns serve a real purpose here: adding a spaced-repetition mode later means writing
one class, with no change to the loop, the CLI or the existing modes.

**Dependency injection** (a supporting technique). `Console` takes its input, output and
error functions as arguments and the quiz modes take a random generator. That is why the
whole quiz loop, including Ctrl+C handling, can be tested without a keyboard.

## Testing and code quality

```bash
python -m pytest tests/                                 # run the tests
python -m pytest --cov=. --cov-report=html              # coverage report (open htmlcov/index.html)
python -m black --check . && python -m isort --check-only .
python -m flake8 .
python -m mypy .
python -m bandit -r main.py utils
```

| Check | Result |
|---|---|
| pytest | 151 tests pass |
| Coverage | 100% of the application code (412 statements) |
| black / isort | clean |
| flake8 | 0 errors (configured in `.flake8` to match black's 88-character lines) |
| mypy | 0 errors, with `disallow_untyped_defs` on |
| bandit | 0 issues (2 reviewed false positives, annotated with `# nosec`) |

Saved evidence: [`docs/coverage_report.txt`](docs/coverage_report.txt),
[`docs/quality_report.txt`](docs/quality_report.txt) and the browsable HTML report in
[`docs/coverage_html/`](docs/coverage_html/index.html).

| Test file | Covers |
|---|---|
| `tests/test_flashcard_loader.py` | Both deck formats, malformed JSON, missing fields, file errors |
| `tests/test_quiz_modes.py` | Factory, all three modes (including adaptive repeats), session |
| `tests/test_integration.py` | A full 3-question session, every mode on every bundled deck |
| `tests/test_ui.py` | Colours, quiz loop, `exit` and Ctrl+C, summary tables |
| `tests/test_history.py` | Saving, corrupt files, lifetime statistics |
| `tests/test_cli.py` | Flags, friendly errors, and real runs of `main.py` as a subprocess |

## Project structure

```text
flashcard-quizzer/
|-- .claude/
|   |-- commands/
|   |   |-- debug-help
|   |   |-- generate-function
|   |   |-- refactor-code
|   |   `-- review-code
|   |-- CLAUDE.md
|   `-- mcp.json
|-- ai_guidance/
|   |-- code_review_checklist.md
|   `-- prompting_best_practices.md
|-- data/
|   |-- glossary.json
|   |-- network_ports.json
|   `-- python_basics.json
|-- docs/
|   |-- coverage_html/
|   |-- ai_edit_log.md
|   |-- coverage_report.txt
|   |-- design_patterns.md
|   |-- final_report.md
|   |-- quality_report.txt
|   `-- report_template.md
|-- tests/
|   |-- __init__.py
|   |-- conftest.py
|   |-- test_cli.py
|   |-- test_flashcard_loader.py
|   |-- test_history.py
|   |-- test_integration.py
|   |-- test_quiz_modes.py
|   `-- test_ui.py
|-- utils/
|   |-- __init__.py
|   |-- data_loader.py
|   |-- history.py
|   |-- models.py
|   |-- quiz_engine.py
|   `-- ui.py
|-- .editorconfig
|-- .flake8
|-- .gitignore
|-- README.md
|-- main.py
|-- pyproject.toml
`-- requirements.txt
```

## Known limitations

- Answers must match the card's back exactly (ignoring case and extra spaces). There is no
  fuzzy matching, so `"color"` does not match `"colour"`.
- A card whose real answer is `exit` is accepted as an answer rather than quitting. Use
  Ctrl+C on that card.
- History is stored per user in `~/.flashcard_quizzer/history.json` (change it with
  `--history-file`). A corrupt history file never stops a quiz, and it is never overwritten.

## AI-assisted development

The application was generated with an AI assistant (Claude), then reviewed against
`ai_guidance/code_review_checklist.md`, run through the quality tools and exercised with
tests. The problems found along the way, and how each was fixed, are recorded in
[`docs/ai_edit_log.md`](docs/ai_edit_log.md). The project report is
[`docs/final_report.md`](docs/final_report.md).
