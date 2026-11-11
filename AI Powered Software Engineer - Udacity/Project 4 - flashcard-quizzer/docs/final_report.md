# AI-Assisted Development Project Report

**Student Name:** Saket Khopkar
**Project Title:** Flashcard Quizzer CLI
**Date:** 11 November 2026

## Executive Summary

I built the Flashcard Quizzer, a command-line tool that loads flashcards from a JSON file, quizzes the user in one of three modes, and prints a summary of the session. It runs in the terminal, reads decks from JSON, and is organised so new modes can be added without rewriting it.

The main features are sequential, random and adaptive modes (adaptive keeps re-asking cards the user misses), validation that turns bad files into one-line errors, coloured feedback, graceful exit, a summary table, and lifetime statistics from saved sessions. I used an AI assistant (Claude, in chat) to generate the code in phases, then reviewed it against the course checklist, ran the quality tools, and corrected the problems that surfaced.

## Project Overview

### Problem Statement
New staff need a fast way to memorise terms. The tool must run in any terminal, accept new decks as plain JSON, and show which terms need practice.

### Solution Approach
The code is split by responsibility: `data_loader.py` reads and validates decks, `quiz_engine.py` holds the quiz logic, `ui.py` handles all input and output, `history.py` stores sessions, and `main.py` only wires them together. Only the Python standard library is used at runtime. Input and output functions are injected, so the entire quiz loop is testable without a keyboard.

### Final Features
- [x] Load array and object format decks with friendly errors
- [x] Sequential, random and adaptive quiz modes (Strategy pattern, Factory)
- [x] Case-insensitive answers, green and red feedback, `exit` and Ctrl+C
- [x] Session summary table: total, accuracy, missed terms
- [x] Lifetime statistics (`--stats`), `--limit`, `--seed`, `--no-color`, `--no-save`

## AI Collaboration Experience

### AI Tools Used
- [x] Claude (chat assistant)

### Collaboration Workflow
I gave Claude the full brief and rubric and asked it to build the application in the brief's three phases, with tests alongside each. Claude first read the starter repository, then proposed the architecture before writing code. Code was produced module by module and checked immediately with `pytest`, `black`, `isort`, `flake8`, `mypy` and `bandit`.

Review had three layers: the tools, a read-through against `ai_guidance/code_review_checklist.md`, and running the real program with the commands from the Definition of Done. Each problem found was fixed in the code and recorded in `docs/ai_edit_log.md`.

### Most Valuable AI Interactions

#### Example 1: A test that found a real bug
**Context:** Testing the factory's `register()` method.
**AI Prompt:** Test that a nameless mode is rejected.
**AI Response:** The test failed. A subclass inherited the name `"sequential"`, so registering it silently replaced the built-in mode.
**Changes Made:** `register()` now refuses a name already in use, with tests for built-in protection.
**Outcome:** A dangerous extension point became safe.

#### Example 2: Running the real program
**Context:** Playing an adaptive game on the Python deck.
**AI Prompt:** Run the Definition of Done commands and inspect the output.
**AI Response:** The game worked, but the summary table was 130 characters wide because all missed terms shared one cell.
**Changes Made:** One term per row, wrapped at 76 columns, with new tests.
**Outcome:** A 65-column table. 150 passing tests had missed it.

#### Example 3: Proving the tests can fail
**Context:** Coverage was 100%, but that only shows lines ran.
**AI Prompt:** Show that the tests catch mistakes.
**AI Response:** Nine deliberate bugs were introduced one at a time (for example, adaptive mode never repeating). All nine made tests fail.
**Outcome:** Evidence that the suite checks behaviour.

### Challenges with AI Collaboration
The AI was strong on structure and the happy path, but weaker on unusual cases. Problems clustered around edge behaviour: a default bound at import time, leftover unused code, and a path lookup that could crash on start-up. Tools caught type and style errors, but not "valid but pointless" code or realistic data shapes. The brief's `--stats` flag was ambiguous, so I treat my reading of it (lifetime statistics) as an assumption.

## Software Engineering Practices

### Code Quality Measures
- [x] Formatting: black and isort, both clean
- [x] Linting: flake8 with zero errors, mypy with zero errors
- [x] Type hints on every function, and docstrings on every public item
- [x] Documentation: README, docstrings, this report
- [x] Error handling: custom exceptions, friendly messages, no raw tracebacks

### Testing Strategy
There are 151 pytest tests: unit tests for the loader, modes, session, UI and history, plus CLI tests and integration tests, including real runs of `main.py` as a subprocess. Coverage of the application code is 100% (412 statements). Edge cases include malformed JSON, missing fields, unreadable and oversized files, corrupt history, Ctrl+C, end of input, and a card whose answer is `exit`. Tests were written alongside the code, not strictly test-first.

### Design Patterns Used
- **Strategy:** `QuizMode` is the abstract strategy and `SequentialMode`, `RandomMode` and `AdaptiveMode` are interchangeable algorithms for choosing the next card. I chose it because the three modes differ only in that one decision, so a future spaced-repetition mode is one new class.
- **Factory:** `QuizModeFactory` turns the `-m` text into the right object, removing an `if/elif` chain from `main.py`. It also guards against replacing existing modes.
- **Dependency injection** (supporting technique): `Console` and the random generator are passed in, which makes behaviour testable.

### Code Structure and Organization
Each module has one job and depends only on lower layers. `models.py` holds shared data types, and nothing in `utils/` imports `main.py`. Refactoring during review included replacing a wide table cell with a wrapped list, and making defaults resolve at call time.

## Technical Challenges and Solutions

### Challenge 1: A terminating adaptive algorithm
**Problem:** "Prioritise missed cards" can loop forever.
**Solution:** A queue that re-inserts a missed card two questions later, at most three times per card.
**AI Involvement:** Claude proposed it, and considered and rejected a weighted-random alternative as hard to test.
**Lessons Learned:** Choose algorithms you can assert on.

### Challenge 2: Failing gracefully
**Problem:** The brief forbids tracebacks, but files, JSON, history and keyboards can all fail.
**Solution:** One exception per layer, caught in `main.py` and shown as one line, and a corrupt history file is never overwritten.
**AI Involvement:** Claude wrote the handlers; the review found an import-time `Path.home()` call that could crash before any handler existed.
**Lessons Learned:** Do risky lookups inside code that has error handling.

## Code Quality Analysis

### Metrics
- Lines of code: 814 application, 960 tests (non-blank)
- Test coverage: 100% of application code (412 statements)
- Functions/classes: 52 functions and methods, 17 classes in the application
- Linting: flake8 0 errors, mypy 0 errors, bandit 0 issues (2 reviewed suppressions)

### Self-Assessment
- **Code Readability:** 4. Small modules with docstrings and type hints, though `ui.py` mixes colours, the loop and table drawing.
- **Code Maintainability:** 4. Clear boundaries and an extension point, but the factory registry is class-level shared state.
- **Test Quality:** 5. Edge cases, subprocess runs, and a mutation check showing 9 of 9 deliberate bugs caught.
- **Documentation:** 4. Full README, log and report, but the log's line counts are estimates.

## Learning Outcomes

### Technical Skills Developed
The Strategy and Factory patterns, `typing.Protocol`, dependency injection for testing, argparse, and a `black`, `isort`, `flake8`, `mypy`, `bandit` and `pytest-cov` toolchain configured to agree with each other.

### AI Collaboration Skills
Specific, checkable requests work better than broad ones. Review needs several layers, because each catches different mistakes. AI output is a first draft to verify by running it, and decisions on ambiguous requirements belong to the human.

### Software Engineering Insights
Coverage is not quality. Test data should be as awkward as real data. Extension points need misuse tests, and failures belong at the edges with clear messages.

## Reflection

### What Worked Well
Running the quality tools after each module, and playing the real program, found problems that no single check would have. I am most pleased with the adaptive mode and the mutation check.

### What Could Be Improved
Next time I would run every tool after each module, test with realistic decks earlier, and confirm what `--stats` means before building on it.

### Future Enhancements
A spaced-repetition mode, fuzzy answer matching, deck import from CSV, and a curses-style full-screen interface.

## Conclusion

AI-assisted development changed my view of coding: the value moved from typing code to specifying, reviewing and verifying it. I will keep using layered checks, injected dependencies and written-down assumptions.

## Appendices

### Appendix A: AI Interaction Log
See [`ai_edit_log.md`](ai_edit_log.md) for all ten entries.

### Appendix B: Code Statistics
See [`coverage_report.txt`](coverage_report.txt) and [`quality_report.txt`](quality_report.txt).

### Appendix C: Additional Resources
`ai_guidance/code_review_checklist.md`, `docs/design_patterns.md`, and the pytest and mypy documentation.
