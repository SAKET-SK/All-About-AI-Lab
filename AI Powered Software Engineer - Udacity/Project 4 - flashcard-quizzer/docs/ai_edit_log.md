# AI Edit Log

**Project:** Flashcard Quizzer CLI
**AI tool used throughout:** Claude (the claude.ai chat assistant), not the Claude Code workspace.
**How the work was done:** The full project brief was pasted into one chat session and the AI
built the application in the three phases the brief describes (data layer, Strategy and
Factory engine, CLI), writing the tests alongside the code. Code was written and run in the
AI's own sandbox, so every problem below was found by running the tools (`pytest`, `black`,
`flake8`, `mypy`, `bandit`), by playing the real application, or by re-reading the code against
`ai_guidance/code_review_checklist.md`.

> **Honesty note.** The entries below record what actually happened in that session. Entries 2
> to 9 are the AI reviewing and correcting its own first drafts, so "Changes Made" describes
> the AI's fixes during review. Nothing here was invented to reach the required count.

---

## 2026-11-11 - Entry 1: Reading the brief and designing the architecture

**Context:** Turn the brief and the starter repository into a plan before writing code.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** The complete project brief and rubric, with the request to build the
application and meet every deliverable. The AI first read the starter repo (README,
`CLAUDE.md`, the review checklist, the design-patterns guide and the two sample decks).

**AI Response:** A plan with six modules (`models`, `data_loader`, `quiz_engine`, `ui`,
`history`, `main`), the Strategy pattern for the modes, a Factory to create them, and
dependency injection for input and output so the quiz loop is testable. The adaptive mode
was designed as a queue that re-inserts a missed card two questions later.

**Changes Made:**
- Considered and **rejected** a weighted-random adaptive mode. It is hard to test, can ask
  the same card many times in a row, and has no natural end.
- Chose the queue design, with `max_retries=3` so a card the user never learns cannot
  cause an endless quiz.
- The brief never says what `--stats` does. It was interpreted as "show lifetime
  statistics from saved sessions", which is why a history module exists. This is an
  interpretation of an ambiguous requirement, not something the brief states.

**Reasoning:** The adaptive mode is the "challenge feature", so it needed a deterministic,
terminating algorithm that tests can assert on. Choosing the design before coding avoided
rewriting the engine later.

**Outcome:** The architecture in the README. All later entries are fixes made inside it.

**Lessons Learned:**
- Ambiguous requirements (`--stats`) should be flagged and confirmed, not silently decided.
- Choosing an algorithm that can be tested deterministically matters as much as choosing one
  that sounds smart.

---

## 2026-11-11 - Entry 2: Unnecessary field left in the first UI draft

**Context:** Reviewing `utils/ui.py` against the checklist's readability section.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** The brief's requirement to review all AI-generated code with the
checklist ("Is the code easy to understand? Is anything unnecessary?").

**AI Response:** The first draft of the `Console` dataclass contained a meaningless
`_unused: list[str]` field and a matching extra import.

**Changes Made:** Deleted the field and the unused `field` import.

**Reasoning:** The code was valid, so `flake8`, `mypy` and every test were happy. Only a human-style
read of the code found it. Leftover scaffolding confuses the next developer.

**Outcome:** `Console` has four fields, all used.

**Lessons Learned:** Tools do not catch "pointless but valid" code. The checklist read is a
separate, necessary step.

---

## 2026-11-11 - Entry 3: A test exposed a real bug in the factory

**Context:** Writing tests for `QuizModeFactory.register()`, the hook that lets new modes be
added (for example a future spaced-repetition mode).

**AI Tool Used:** Claude (chat)

**Prompt/Request:** Write a test that registering a mode without a name is rejected.

**AI Response:** The test used a subclass of `SequentialMode` that did not set `name`. It
**failed** ("DID NOT RAISE"). The cause was in the AI's own code: the subclass inherited
`name = "sequential"`, so `register()` silently **replaced the built-in sequential mode**.

**Changes Made:**
- `register()` now raises `ValueError` if the name is already used by a different class.
- The nameless-mode test now subclasses `QuizMode` directly.
- Added tests proving a built-in mode cannot be replaced and that re-registering the same
  class is harmless.

**Reasoning:** Silently swapping a core mode is the kind of surprising behaviour that is
miserable to debug. Failing loudly is safer for an extension point.

**Outcome:** Three new tests pass, and the registry is protected.

**Lessons Learned:** A test written for one purpose (nameless modes) exposed a different,
real bug. Extension points need tests for misuse, not only for the happy path.

---

## 2026-11-11 - Entry 4: pytest was green, but mypy and flake8 were not

**Context:** Running the full quality gate after the first test files were written.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** The brief requires `mypy` and `flake8` to pass, with type hints on all
functions.

**AI Response:** `pytest` passed, but `mypy` reported 15 errors in the tests. The `write_deck`
helper was typed as `Callable[[object, str], Path]` yet was called with one argument, and one
test unpacked `**dict[str, int]` into `AdaptiveMode`. Later `flake8` also found an unused
`Callable` import in `test_cli.py`.

**Changes Made:**
- Replaced the helper's type with a `typing.Protocol` (`DeckWriter`) that has a default
  argument.
- Changed the parametrized test to take explicit `retry_gap` and `max_retries` arguments.
- Removed the unused import.

**Reasoning:** Green tests only prove behaviour. The type errors were real mistakes in the
helper's declared contract, and keeping the tests typed is part of "all functions must have
type hints".

**Outcome:** `mypy` reports no issues across 15 files and `flake8` is clean.

**Lessons Learned:** Always run every tool, not just the test runner. Add the linters to the
same command as the tests.

---

## 2026-11-11 - Entry 5: A wrong test, not wrong code

**Context:** `test_render_lifetime_stats_with_history` failed after the UI tests were added.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** Check that the lifetime statistics table shows sessions, accuracy and the
hardest cards.

**AI Response:** The assertion expected `"Sessions played : 2"` with one space. The table pads
labels so the colons line up, so the real text is `"Sessions played   : 2"`.

**Changes Made:** Kept the code as it was and changed the assertions to a regex that tolerates
the padding.

**Reasoning:** The output was correct and readable, so the test's expectation was the thing at
fault. Changing good code to satisfy a bad test would have made the output worse.

**Outcome:** Test passes, and the aligned table is kept.

**Lessons Learned:** When a test fails, decide first which side is wrong before editing
anything. Assert on meaning (a regex) rather than exact spacing.

---

## 2026-11-11 - Entry 6: Security scan, and a reviewed false positive

**Context:** The rubric's "stand out" list asks for security practices, so `bandit` was run.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** Run a security scan over `main.py` and `utils/`.

**AI Response:** `bandit` reported two findings, rule B311 (the `random` module is not
cryptographically secure). The summary line "High: 2" is bandit's *confidence*; the *severity*
was Low.

**Changes Made:** Kept `random.Random`, because seeding is needed for repeatable runs and
tests, and added `# nosec B311` with a comment saying why. The first attempt wrote the
explanation inside the `nosec` comment, and bandit warned that it was parsing the words as test
IDs, so the explanation was moved to its own comment line.

**Reasoning:** Shuffling flashcards has no security role. Silencing a tool is only acceptable
when the reason is written down next to the suppression.

**Outcome:** `bandit`: 0 issues, with 2 reviewed and documented suppressions.

**Lessons Learned:** Read what the severity and confidence labels really mean. A suppression
needs a human reason, and tools can misparse comment text.

---

## 2026-11-11 - Entry 7: Input function captured at import time

**Context:** Adding a test that answers the quiz through the real `input()` function.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** Cover the default console path in `main.py` (the code used when no test
console is injected).

**AI Response:** The new test **failed** with "reading from stdin while output is captured".
The cause was a design flaw in the AI's code: `Console.input_fn` defaulted to the built-in
`input` object, fixed when the class was defined, while `output_fn` used a small wrapper that
looks up `print` on every call. So replacing `input` later had no effect.

**Changes Made:** Added a `_default_input` wrapper, matching the existing `_default_output`.

**Reasoning:** Two defaults that behave differently is an inconsistency waiting to cause
confusion. Resolving at call time keeps both replaceable.

**Outcome:** The test passes, and `main.py` is 100% covered.

**Lessons Learned:** Defaults that bind a function at definition time quietly break
substitution. Asymmetric code for the same job is a smell worth checking.

---

## 2026-11-11 - Entry 8: Playing the real app found a layout bug the tests missed

**Context:** A full adaptive game on `data/python_basics.json`, run from the command line.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** Run the commands from the brief's "Definition of Done" and look at the
actual output.

**AI Response:** The game worked, but the summary table was about 130 characters wide. That
deck's card fronts are full questions, and the first version joined every missed term into one
cell. It would wrap badly in an 80-column terminal. No unit test noticed, because their sample
terms were short.

**Changes Made:**
- The table now lists each missed term on its own row.
- Long text wraps at 76 columns.
- Added tests for long terms and for an unbroken 200-character word.

**Reasoning:** The brief asks for "a list of terms the user missed". A list reads as one item
per line.

**Outcome:** The same game now prints a 65-column table. Tests assert the width limit.

**Lessons Learned:** Test data should be as awkward as real data. Always run the finished
program as a user would, not only its tests.

---

## 2026-11-11 - Entry 9: Final review pass

**Context:** A last read of the finished source against the checklist, thinking about "what
could go wrong".

**AI Tool Used:** Claude (chat)

**Prompt/Request:** The checklist sections on correctness, error handling and unnecessary code.

**AI Response:** Two findings. `utils/ui.py` held an unused `BOLD` colour constant (dead code
that no tool flags). And `history.DEFAULT_HISTORY_PATH` was computed at import time with
`Path.home()`, which can raise `RuntimeError` in unusual environments and would crash the app
with a traceback before it even read its arguments, against the "no raw tracebacks" rule.

**Changes Made:** Removed `BOLD`. Replaced the constant with `default_history_path()`, which
falls back to the current directory, and added three tests (normal home, home unknown, store
using the default).

**Reasoning:** Import-time work that can fail is the worst place for a failure, because
nothing has been caught or explained yet.

**Outcome:** 151 tests pass and coverage is still 100%.

**Lessons Learned:** Do risky lookups lazily, inside code that has error handling.

---

## 2026-11-11 - Entry 10: Checking that the tests can fail (mutation check)

**Context:** The brief asks for tests of the AI-generated code, and 100% coverage only proves
lines were executed, not that bugs would be caught.

**AI Tool Used:** Claude (chat)

**Prompt/Request:** Prove the tests catch real mistakes.

**AI Response:** A script temporarily broke the code in nine ways, ran the suite after each
break, and restored the file. Breakages included adaptive mode never re-asking, case-sensitive
matching, the loader ignoring `back`, a wrong accuracy formula, `exit` not working, random
mode not shuffling, the factory accepting any name, the summary dropping missed terms, and
history mixing decks.

**Changes Made:** No code changes were needed. All nine were caught (9/9) and the restored
code passed all 151 tests. An earlier run printed a failure on its last line; that was an
unrelated new test from Entry 7 that had not yet been fixed, not a missed mutant.

**Reasoning:** Passing tests are only meaningful if they would fail when the code is wrong.

**Outcome:** Evidence that the suite checks behaviour, not just coverage.

**Lessons Learned:** Coverage measures what ran. A mutation check measures whether the tests
would notice a bug.

---

## Reflection Questions

1. **What types of tasks did AI help with most effectively?** Generating the module structure,
   the Strategy and Factory classes, docstrings and type hints, and a large, varied test
   suite quickly, including edge cases.
2. **Where did the most modifications to AI suggestions come from?** Edge cases and
   consistency: the factory's silent overwrite, import-time work, and the table layout. The
   happy path was right the first time, but the unusual paths were not.
3. **What patterns showed in AI strengths and weaknesses?** Strong on structure and breadth;
   weaker at noticing leftover code, hidden coupling (a default bound at import) and
   real-world data shapes. Running things found nearly every problem.
4. **How did the prompting technique improve over time?** Entry 1's brief was broad. Later
   passes used specific, checkable asks: "run the commands in the Definition of Done", "check
   whether the tests would fail if this line were wrong".
5. **What would be done differently next time?** Ask for the quality tools to run after every
   module rather than at the end, test with realistic data from the start, and confirm
   ambiguous requirements such as `--stats` before building on an interpretation.

## Summary Statistics

- **Total AI interactions documented:** 10 entries, from one continuous chat session
- **Lines of AI-generated code used:** all of it: 1,774 non-blank lines of Python (814 in the
  application, 960 in the tests)
- **Lines of AI-generated code modified after the first draft:** roughly 200 (an estimate,
  because changes were not tracked in version control)
- **Most helpful AI interaction:** Entry 8, running the real program, which found a layout
  problem that 150 passing tests missed
- **Most challenging AI interaction:** Entry 3, a test failure whose cause was not the
  assumption being tested
- **Biggest lesson learned:** Green tests are not the finish line. Run every tool, run the real
  program, and check that tests can fail.

---

**Related files:** [`final_report.md`](final_report.md), [`quality_report.txt`](quality_report.txt),
[`coverage_report.txt`](coverage_report.txt)
