"""
claims_intake_loop.py

Lesson 8, Exercise 1 (single-file edition): the stop_reason-driven
agentic loop, a scripted test client that mimics the Anthropic SDK with
no live API calls, and the full test suite -- all in one file.

Four moments, every turn:
  1. Send        - client.messages.create(...)
  2. Inspect     - response.stop_reason decides what happens next
  3. Execute     - run every tool_use block if stop_reason == "tool_use"
  4. Thread back - append assistant turn + one user turn of tool_results

This file has NO knowledge of claims, adjusters, or insurance. That's
deliberate: the loop is domain-agnostic by design. Tools and domain
logic belong elsewhere (later exercises), never in the loop itself.

RUNNING
-------
As a script (runs all tests, no pytest required):
    python claims_intake_loop.py

With pytest (same tests, nicer output):
    pip install pytest
    pytest claims_intake_loop.py -v
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


# =============================================================================
# PART 1: THE AGENTIC LOOP
# =============================================================================

class UnexpectedStopReason(Exception):
    """
    Raised when response.stop_reason is anything other than the two
    values this loop knows how to handle: "tool_use" and "end_turn".

    The API can also return "max_tokens", "pause_turn", "refusal", or
    "stop_sequence". These are unplanned states -- the harness should
    never silently guess what to do with them. Raise loudly, name the
    value, and let a human decide.
    """

    def __init__(self, stop_reason: str | None):
        self.stop_reason = stop_reason
        super().__init__(f"Unexpected stop_reason: {stop_reason!r}")


@dataclass
class TurnRecord:
    """One entry in the trace -- the lifecycle artifact for a single turn."""

    turn: int
    stop_reason: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    text: str | None = None


@dataclass
class FinalState:
    """Returned once the model reaches end_turn."""

    text: str
    num_turns: int
    trace: list[TurnRecord]
    messages: list[dict[str, Any]]


# A dispatcher maps (tool_name, tool_input) -> a JSON-serializable result.
# It is expected to implement Graceful Tool Failure itself: catch its own
# errors and return a result describing the failure, rather than raising.
# A raised exception here would kill the whole loop instead of letting
# the model see the failure and decide what to do next.
ToolDispatcher = Callable[[str, dict[str, Any]], Any]


def run_agent_loop(
    client: Any,
    messages: list[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
    system: str,
    dispatch_tool: ToolDispatcher,
    model: str = "claude-sonnet-5",
    max_turns: int = 20,
) -> FinalState:
    """
    Runs the four-moments loop until the model signals end_turn.

    client must expose .messages.create(**kwargs) -> object with
    .stop_reason (str) and .content (list of blocks with .type, and
    depending on type: .text, or .id/.name/.input). In production this
    is anthropic.Anthropic(); in tests it's the ScriptedClient below.

    Raises UnexpectedStopReason for any unplanned stop_reason, and
    RuntimeError if max_turns is exceeded without reaching end_turn --
    a harness-level safety net that exists independently of anything
    the model decides.
    """
    trace: list[TurnRecord] = []

    for turn in range(1, max_turns + 1):
        # ---- 1. Send -------------------------------------------------
        response = client.messages.create(
            model=model,
            system=system,
            tools=list(tools),
            messages=messages,
            max_tokens=1024,
        )

        # ---- 2. Inspect stop_reason -----------------------------------
        if response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            trace.append(
                TurnRecord(turn=turn, stop_reason="end_turn", text=final_text)
            )
            messages.append({"role": "assistant", "content": response.content})
            return FinalState(
                text=final_text,
                num_turns=turn,
                trace=trace,
                messages=messages,
            )

        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            # ---- 3. Execute tools --------------------------------------
            tool_results: list[dict[str, Any]] = []
            calls_for_trace: list[dict[str, Any]] = []
            for block in tool_use_blocks:
                result = dispatch_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
                calls_for_trace.append({"name": block.name, "input": block.input})

            trace.append(
                TurnRecord(
                    turn=turn, stop_reason="tool_use", tool_calls=calls_for_trace
                )
            )

            # ---- 4. Thread results back ---------------------------------
            # One assistant turn (the model's own content, unchanged),
            # then ONE user turn holding ALL tool_result blocks from this
            # round -- never one user turn per tool.
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # ---- Unplanned state: raise, don't guess -----------------------
        raise UnexpectedStopReason(response.stop_reason)

    raise RuntimeError(f"Exceeded max_turns ({max_turns}) without reaching end_turn")


# =============================================================================
# PART 2: SCRIPTED TEST CLIENT (no live API calls)
# =============================================================================

@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class ScriptedResponse:
    """Mimics the shape of an anthropic.types.Message enough for the loop."""

    stop_reason: str
    content: list[Any] = field(default_factory=list)


class _ScriptedMessages:
    def __init__(self, responses: list[ScriptedResponse]):
        self._responses = list(responses)
        # Records every kwargs dict passed to create(), so tests can
        # assert on exactly what the loop sent (model, tools, etc.).
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> ScriptedResponse:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError(
                "ScriptedClient ran out of scripted responses -- the loop "
                "called .create() more times than the test expected."
            )
        return self._responses.pop(0)


class ScriptedClient:
    """Mimics anthropic.Anthropic()'s shape: client.messages.create(...)."""

    def __init__(self, responses: list[ScriptedResponse]):
        self.messages = _ScriptedMessages(responses)


# =============================================================================
# PART 3: TESTS (pytest-discoverable; also runnable standalone, see __main__)
# =============================================================================

def make_dispatcher(fixed_result=None):
    calls = []

    def dispatch(name, tool_input):
        calls.append((name, tool_input))
        return fixed_result if fixed_result is not None else {"ok": True}

    dispatch.calls = calls
    return dispatch


def test_end_turn_on_first_response_returns_immediately():
    client = ScriptedClient(
        [ScriptedResponse(stop_reason="end_turn", content=[TextBlock(text="Claim received.")])]
    )
    messages = [{"role": "user", "content": "Hi"}]

    result = run_agent_loop(
        client=client,
        messages=messages,
        tools=[],
        system="test system prompt",
        dispatch_tool=make_dispatcher(),
    )

    assert isinstance(result, FinalState)
    assert result.text == "Claim received."
    assert result.num_turns == 1
    assert len(result.trace) == 1
    assert result.trace[0].stop_reason == "end_turn"
    assert len(client.messages.calls) == 1
    sent = client.messages.calls[0]
    assert sent["system"] == "test system prompt"
    assert sent["messages"] == messages or sent["messages"] is messages


def test_single_tool_use_then_end_turn():
    client = ScriptedClient(
        [
            ScriptedResponse(
                stop_reason="tool_use",
                content=[ToolUseBlock(id="call_1", name="lookup_forecast", input={"city": "New York"})],
            ),
            ScriptedResponse(stop_reason="end_turn", content=[TextBlock(text="It's sunny.")]),
        ]
    )
    dispatch = make_dispatcher(fixed_result={"forecast": "sunny"})

    result = run_agent_loop(
        client=client,
        messages=[{"role": "user", "content": "Weather in NY?"}],
        tools=[{"name": "lookup_forecast"}],
        system="sys",
        dispatch_tool=dispatch,
    )

    assert result.text == "It's sunny."
    assert result.num_turns == 2
    assert dispatch.calls == [("lookup_forecast", {"city": "New York"})]
    assert result.trace[0].stop_reason == "tool_use"
    assert result.trace[0].tool_calls == [{"name": "lookup_forecast", "input": {"city": "New York"}}]
    assert result.trace[1].stop_reason == "end_turn"


def test_multiple_tool_use_blocks_in_one_turn_all_executed_and_threaded_together():
    # Multiple tool_use blocks in ONE assistant turn must all be
    # executed, with all results threaded back in a SINGLE following
    # user turn.
    client = ScriptedClient(
        [
            ScriptedResponse(
                stop_reason="tool_use",
                content=[
                    ToolUseBlock(id="call_1", name="lookup_forecast", input={"city": "New York"}),
                    ToolUseBlock(id="call_2", name="lookup_forecast", input={"city": "Boston"}),
                ],
            ),
            ScriptedResponse(stop_reason="end_turn", content=[TextBlock(text="Both checked.")]),
        ]
    )
    dispatch = make_dispatcher(fixed_result={"forecast": "cloudy"})

    result = run_agent_loop(
        client=client,
        messages=[{"role": "user", "content": "Weather in NY and Boston?"}],
        tools=[{"name": "lookup_forecast"}],
        system="sys",
        dispatch_tool=dispatch,
    )

    assert len(dispatch.calls) == 2
    assert result.trace[0].tool_calls == [
        {"name": "lookup_forecast", "input": {"city": "New York"}},
        {"name": "lookup_forecast", "input": {"city": "Boston"}},
    ]

    # messages layout: [user, assistant(tool_use), user(tool_results), assistant(end_turn)]
    threaded_user_turn = result.messages[2]
    assert threaded_user_turn["role"] == "user"
    tool_use_ids = [block["tool_use_id"] for block in threaded_user_turn["content"]]
    assert tool_use_ids == ["call_1", "call_2"]


def test_unexpected_stop_reason_raises_and_names_the_value():
    for bad_reason in ["max_tokens", "pause_turn", "refusal", "stop_sequence"]:
        client = ScriptedClient([ScriptedResponse(stop_reason=bad_reason, content=[])])

        raised = None
        try:
            run_agent_loop(
                client=client,
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system="sys",
                dispatch_tool=make_dispatcher(),
            )
        except UnexpectedStopReason as e:
            raised = e

        assert raised is not None, f"expected UnexpectedStopReason for {bad_reason!r}"
        assert raised.stop_reason == bad_reason
        assert bad_reason in str(raised)


def test_max_turns_ceiling_raises_runtime_error_on_runaway_loop():
    # Script more tool_use turns than max_turns allows -- the loop must
    # stop itself even though the model "wants" to keep going.
    responses = [
        ScriptedResponse(
            stop_reason="tool_use",
            content=[ToolUseBlock(id=f"call_{i}", name="noop", input={})],
        )
        for i in range(5)
    ]
    client = ScriptedClient(responses)

    raised = None
    try:
        run_agent_loop(
            client=client,
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system="sys",
            dispatch_tool=make_dispatcher(),
            max_turns=3,
        )
    except RuntimeError as e:
        raised = e

    assert raised is not None
    assert "Exceeded max_turns" in str(raised)


def test_trace_has_one_record_per_turn_in_order():
    client = ScriptedClient(
        [
            ScriptedResponse(
                stop_reason="tool_use",
                content=[ToolUseBlock(id="call_1", name="lookup_forecast", input={"city": "NY"})],
            ),
            ScriptedResponse(
                stop_reason="tool_use",
                content=[ToolUseBlock(id="call_2", name="lookup_forecast", input={"city": "Boston"})],
            ),
            ScriptedResponse(stop_reason="end_turn", content=[TextBlock(text="Done.")]),
        ]
    )

    result = run_agent_loop(
        client=client,
        messages=[{"role": "user", "content": "Hi"}],
        tools=[{"name": "lookup_forecast"}],
        system="sys",
        dispatch_tool=make_dispatcher(fixed_result={"forecast": "n/a"}),
    )

    assert [t.turn for t in result.trace] == [1, 2, 3]
    assert [t.stop_reason for t in result.trace] == ["tool_use", "tool_use", "end_turn"]


# =============================================================================
# STANDALONE TEST RUNNER (so this file needs no pytest installation to verify)
# =============================================================================

def _run_all_tests() -> int:
    test_functions = [
        obj
        for name, obj in list(globals().items())
        if name.startswith("test_") and callable(obj)
    ]

    passed, failed = 0, 0
    for fn in test_functions:
        try:
            fn()
            print(f"PASSED  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"FAILED  {fn.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(test_functions)} tests")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_all_tests())
