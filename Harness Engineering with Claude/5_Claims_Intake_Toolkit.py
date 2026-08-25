"""
claims_intake_toolkit.py

Claims Intake Agent -- Exercise 2 (single-file edition).

Builds on the finished Exercise 1 loop (included below, unmodified) and
adds the tool kit: four fact-gathering / classification tool schemas,
the Graceful Tool Failure helpers (_err / _ok), their matching
dispatchers, and four AST audits that statically catch decision logic
leaking back into the loop.

THE CORE RULE THIS FILE ENFORCES
---------------------------------
The tool schemas ARE the agent's API. The set of tools registered is the
set of actions the model can take. When the model chooses between
"ask a clarifying question" and "commit to a classification," it is
choosing between two tool schemas -- not triggering an if/else branch
you wrote in Python. The moment loop.py reads the model's text and
branches on it, the decision has moved out of the model and into your
code, which is exactly the anti-pattern this exercise guards against.

Four anti-patterns, four AST audits:
  1. Natural-language termination      -- "done" in text
  2. Integer-literal iteration caps    -- for _ in range(10) / while turn < N
  3. Text-content completion checks    -- branching on .text instead of stop_reason
  4. if claim_type == "..." branching  -- Python deciding based on what the model said

RUNNING
-------
    python claims_intake_toolkit.py         # no installs needed
    pytest claims_intake_toolkit.py -v      # optional, nicer output
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


# =============================================================================
# PART 1: THE AGENTIC LOOP (Exercise 1, unmodified -- this is what gets audited)
# =============================================================================

class UnexpectedStopReason(Exception):
    def __init__(self, stop_reason: str | None):
        self.stop_reason = stop_reason
        super().__init__(f"Unexpected stop_reason: {stop_reason!r}")


@dataclass
class TurnRecord:
    turn: int
    stop_reason: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    text: str | None = None


@dataclass
class FinalState:
    text: str
    num_turns: int
    trace: list[TurnRecord]
    messages: list[dict[str, Any]]


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
    The stop_reason-driven loop. This function's source is exactly what
    the four AST audits below inspect. Notice: no "done" in text, no
    bare-integer iteration cap (max_turns is a named, configurable
    parameter, not an inline literal), no branching on .text content,
    and no reference to claim_type anywhere. That's not a coincidence --
    it's the property the audits verify mechanically.
    """
    trace: list[TurnRecord] = []

    for turn in range(1, max_turns + 1):
        response = client.messages.create(
            model=model,
            system=system,
            tools=list(tools),
            messages=messages,
            max_tokens=1024,
        )

        if response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            trace.append(
                TurnRecord(turn=turn, stop_reason="end_turn", text=final_text)
            )
            messages.append({"role": "assistant", "content": response.content})
            return FinalState(
                text=final_text, num_turns=turn, trace=trace, messages=messages
            )

        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            tool_results: list[dict[str, Any]] = []
            calls_for_trace: list[dict[str, Any]] = []
            for block in tool_use_blocks:
                result = dispatch_tool(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
                calls_for_trace.append({"name": block.name, "input": block.input})

            trace.append(
                TurnRecord(turn=turn, stop_reason="tool_use", tool_calls=calls_for_trace)
            )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        raise UnexpectedStopReason(response.stop_reason)

    raise RuntimeError(f"Exceeded max_turns ({max_turns}) without reaching end_turn")


# =============================================================================
# PART 2: DOMAIN CONSTANTS
# =============================================================================

CLAIM_TYPES = ["property_damage", "theft", "liability", "auto"]
SEVERITIES = ["low", "medium", "high"]
FACT_FIELDS = [
    "incident_date",
    "location",
    "description",
    "parties_involved",
    "estimated_loss_amount",
    "witnesses",
]

# Stand-in for data/policies.json. In the real project this is loaded
# from disk; it's embedded here as a plain dict so the whole exercise
# stays in one file.
POLICIES: dict[str, dict[str, Any]] = {
    "POL-1001": {
        "policy_holder": "Jamie Rivera",
        "coverage": "homeowners",
        "deductible": 1000,
        "status": "active",
    },
    "POL-2002": {
        "policy_holder": "Sam Okafor",
        "coverage": "auto",
        "deductible": 500,
        "status": "active",
    },
    "POL-3003-LAPSED": {
        "policy_holder": "Riley Chen",
        "coverage": "homeowners",
        "deductible": 1000,
        "status": "lapsed",
    },
}

# The in-memory "case file" that record_claim_fact appends to. In a real
# system this would be per-claim, keyed by claim/session id; kept as a
# simple module-level list here to match the single-file scope of this
# exercise.
CASE_FILE_FACTS: list[dict[str, str]] = []


# =============================================================================
# PART 3: GRACEFUL TOOL FAILURE HELPERS
# =============================================================================
# Tool errors are part of the conversation, not exceptions to the loop.
# Both _err and _ok return JSON STRINGS (not dicts) -- this is what gets
# placed directly into a tool_result's "content" field.

def _err(error_category: str, is_retryable: bool, message: str) -> str:
    """
    error_category is "permanent" (retrying will never help -- the model
    should change tack, e.g. ask a clarifying question) or "transient"
    (worth retrying).
    """
    return json.dumps(
        {
            "is_error": True,
            "error_category": error_category,
            "is_retryable": is_retryable,
            "message": message,
        }
    )


def _ok(data: dict[str, Any]) -> str:
    return json.dumps({"is_error": False, **data})


# =============================================================================
# PART 4: TOOL SCHEMAS -- the model's entire action space
# =============================================================================

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "lookup_policy",
        "description": (
            "Look up a policyholder's coverage record by policy ID. Use "
            "this early in the conversation to confirm the policy exists "
            "before gathering further facts. Returns policy_holder, "
            "coverage, deductible, and status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_id": {
                    "type": "string",
                    "description": "Policy identifier, e.g. POL-1001",
                }
            },
            "required": ["policy_id"],
        },
    },
    {
        "name": "record_claim_fact",
        "description": (
            "Record one normalized fact about the incident into the case "
            "file. Call this once per distinct fact as you learn it from "
            "the claimant (e.g. when they tell you the incident date, "
            "call this with field='incident_date')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": FACT_FIELDS,
                    "description": "Which fact this is.",
                },
                "value": {
                    "type": "string",
                    "description": "The fact's value, in your own normalized wording.",
                },
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "classify_claim",
        "description": (
            "Commit to a classification for this claim once you have "
            "gathered enough facts. Call this only when confident -- it "
            "commits your decision rather than fetching new information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_type": {
                    "type": "string",
                    "enum": CLAIM_TYPES,
                    "description": "The single best-fitting claim category.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in this classification, between 0 and 1.",
                },
                "rationale": {
                    "type": "string",
                    "description": "One or two sentences explaining the classification.",
                },
            },
            "required": ["claim_type", "confidence", "rationale"],
        },
    },
    {
        "name": "assess_severity",
        "description": (
            "Commit to a severity assessment for a claim you have already "
            "classified. Call this once you have enough detail about the "
            "extent of loss."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": SEVERITIES,
                    "description": "Overall severity of the claim.",
                },
                "rationale": {
                    "type": "string",
                    "description": "One or two sentences explaining the severity call.",
                },
            },
            "required": ["severity", "rationale"],
        },
    },
]


# =============================================================================
# PART 5: DISPATCHERS -- one per tool, each validates input and returns
# _err(...) on bad input rather than raising.
# =============================================================================

def dispatch_lookup_policy(tool_input: dict[str, Any]) -> str:
    policy_id = tool_input.get("policy_id")
    if not policy_id or not isinstance(policy_id, str):
        return _err("permanent", False, "policy_id is required and must be a string.")

    record = POLICIES.get(policy_id)
    if record is None:
        # Permanent + not retryable: retrying won't make the policy exist.
        return _err("permanent", False, f"policy_id '{policy_id}' not found.")

    return _ok({"policy_id": policy_id, **record})


def dispatch_record_claim_fact(tool_input: dict[str, Any]) -> str:
    fact_field = tool_input.get("field")
    value = tool_input.get("value")

    if fact_field not in FACT_FIELDS:
        # Defense in depth: the JSON schema enum should prevent this, but
        # the dispatcher never trusts the schema alone.
        return _err(
            "permanent", False, f"field '{fact_field}' is not a recognized fact field."
        )
    if not value or not isinstance(value, str):
        return _err("permanent", False, "value is required and must be a non-empty string.")

    CASE_FILE_FACTS.append({"field": fact_field, "value": value})
    return _ok({"recorded": True, "field": fact_field, "value": value})


def dispatch_classify_claim(tool_input: dict[str, Any]) -> str:
    claim_type = tool_input.get("claim_type")
    confidence = tool_input.get("confidence")
    rationale = tool_input.get("rationale")

    if claim_type not in CLAIM_TYPES:
        return _err(
            "permanent", False, f"claim_type '{claim_type}' is not a recognized category."
        )
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        return _err("permanent", False, "confidence must be a number between 0.0 and 1.0.")
    if not rationale or not isinstance(rationale, str):
        return _err("permanent", False, "rationale is required and must be a non-empty string.")

    return _ok({"recorded": True, "claim_type": claim_type, "confidence": confidence})


def dispatch_assess_severity(tool_input: dict[str, Any]) -> str:
    severity = tool_input.get("severity")
    rationale = tool_input.get("rationale")

    if severity not in SEVERITIES:
        return _err("permanent", False, f"severity '{severity}' is not a recognized level.")
    if not rationale or not isinstance(rationale, str):
        return _err("permanent", False, "rationale is required and must be a non-empty string.")

    return _ok({"recorded": True, "severity": severity})


_DISPATCHERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "lookup_policy": dispatch_lookup_policy,
    "record_claim_fact": dispatch_record_claim_fact,
    "classify_claim": dispatch_classify_claim,
    "assess_severity": dispatch_assess_severity,
}


def dispatch_tool(name: str, tool_input: dict[str, Any]) -> str:
    """
    The dispatch_tool passed into run_agent_loop. Second, generic layer
    of Graceful Tool Failure: even an unanticipated bug in a specific
    dispatcher is caught here and returned as a JSON error string,
    instead of propagating into the loop as an exception.
    """
    handler = _DISPATCHERS.get(name)
    if handler is None:
        return _err("permanent", False, f"Unknown tool '{name}'.")

    try:
        return handler(tool_input)
    except Exception as exc:  # noqa: BLE001 -- intentional safety net
        return _err("permanent", False, f"Unhandled error in tool '{name}': {exc}")


# =============================================================================
# PART 6: THE FOUR AST ANTI-PATTERN AUDITS
# =============================================================================

def _get_loop_source_tree() -> ast.AST:
    """Parses run_agent_loop's own source -- this is 'loop.py' for audit purposes."""
    return ast.parse(inspect.getsource(run_agent_loop))


def audit_no_natural_language_termination(tree: ast.AST) -> list[str]:
    """Anti-pattern 1: using "done" in text to decide whether to stop."""
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if (
                    isinstance(op, ast.In)
                    and isinstance(node.left, ast.Constant)
                    and isinstance(node.left.value, str)
                ):
                    offenders.append(ast.unparse(node))
    return offenders


def audit_no_integer_literal_iteration_cap(tree: ast.AST) -> list[str]:
    """
    Anti-pattern 2: for _ in range(10) or while turn < N as the PRIMARY
    stop mechanism -- a bare integer literal used directly as a loop
    bound. A named, configurable value (e.g. max_turns, sourced from a
    parameter/config) is fine; a hardcoded literal is not.
    """
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
            call = node.iter
            if isinstance(call.func, ast.Name) and call.func.id == "range":
                args = call.args
                if args:
                    stop_arg = args[0] if len(args) == 1 else args[1]
                    if isinstance(stop_arg, ast.Constant) and isinstance(stop_arg.value, int):
                        offenders.append(ast.unparse(call))
        if isinstance(node, ast.While):
            for cmp_node in ast.walk(node.test):
                if isinstance(cmp_node, ast.Compare):
                    for comparator in cmp_node.comparators:
                        if isinstance(comparator, ast.Constant) and isinstance(
                            comparator.value, int
                        ):
                            offenders.append(ast.unparse(node.test))
    return offenders


def audit_no_text_content_completion_check(tree: ast.AST) -> list[str]:
    """
    Anti-pattern 3: branching on whether response text "looks finished"
    (any .text attribute access inside an if-condition) instead of
    checking stop_reason == "end_turn".
    """
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Attribute) and sub.attr == "text":
                    offenders.append(ast.unparse(node.test))
                    break
    return offenders


def audit_no_claim_type_string_branching(tree: ast.AST) -> list[str]:
    """
    Anti-pattern 4: if claim_type == "...": branching -- Python deciding
    what to do based on what the model said, instead of that decision
    living in a tool schema / the model itself.
    """
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(op, ast.Eq):
                    left_is_claim_type = (
                        isinstance(node.left, ast.Name) and node.left.id == "claim_type"
                    )
                    right_is_claim_type = (
                        isinstance(comparator, ast.Name) and comparator.id == "claim_type"
                    )
                    other = comparator if left_is_claim_type else node.left
                    if (
                        (left_is_claim_type or right_is_claim_type)
                        and isinstance(other, ast.Constant)
                        and isinstance(other.value, str)
                    ):
                        offenders.append(ast.unparse(node))
    return offenders


# =============================================================================
# PART 7: TESTS
# =============================================================================

# ---- 7a. Tool schema structure -------------------------------------------

def test_all_schemas_registered_with_name_description_input_schema():
    for schema in TOOL_SCHEMAS:
        assert "name" in schema and schema["name"]
        assert "description" in schema and len(schema["description"]) > 20
        assert "input_schema" in schema
        assert "required" in schema["input_schema"]


def test_required_lists_match_what_each_dispatcher_reads():
    expected_required = {
        "lookup_policy": {"policy_id"},
        "record_claim_fact": {"field", "value"},
        "classify_claim": {"claim_type", "confidence", "rationale"},
        "assess_severity": {"severity", "rationale"},
    }
    for schema in TOOL_SCHEMAS:
        name = schema["name"]
        required = set(schema["input_schema"]["required"])
        assert required == expected_required[name], (
            f"{name}: required={required}, expected={expected_required[name]}"
        )


def test_categorical_fields_use_enum():
    by_name = {s["name"]: s for s in TOOL_SCHEMAS}
    assert by_name["classify_claim"]["input_schema"]["properties"]["claim_type"]["enum"] == CLAIM_TYPES
    assert by_name["assess_severity"]["input_schema"]["properties"]["severity"]["enum"] == SEVERITIES


# ---- 7b. Dispatcher behavior: success + graceful failure -----------------

def test_lookup_policy_success():
    result = json.loads(dispatch_tool("lookup_policy", {"policy_id": "POL-1001"}))
    assert result["is_error"] is False
    assert result["policy_holder"] == "Jamie Rivera"


def test_lookup_policy_not_found_is_graceful_json_not_an_exception():
    result = json.loads(dispatch_tool("lookup_policy", {"policy_id": "POL-NOPE"}))
    assert result["is_error"] is True
    assert result["error_category"] == "permanent"
    assert result["is_retryable"] is False
    assert "POL-NOPE" in result["message"]


def test_lookup_policy_missing_field_is_graceful():
    result = json.loads(dispatch_tool("lookup_policy", {}))
    assert result["is_error"] is True


def test_record_claim_fact_success():
    before = len(CASE_FILE_FACTS)
    result = json.loads(
        dispatch_tool("record_claim_fact", {"field": "incident_date", "value": "2026-07-14"})
    )
    assert result["is_error"] is False
    assert len(CASE_FILE_FACTS) == before + 1


def test_record_claim_fact_invalid_field_is_graceful():
    result = json.loads(
        dispatch_tool("record_claim_fact", {"field": "not_a_real_field", "value": "x"})
    )
    assert result["is_error"] is True


def test_classify_claim_success():
    result = json.loads(
        dispatch_tool(
            "classify_claim",
            {"claim_type": "auto", "confidence": 0.9, "rationale": "Rear-end collision."},
        )
    )
    assert result["is_error"] is False
    assert result["claim_type"] == "auto"


def test_classify_claim_bad_confidence_is_graceful():
    result = json.loads(
        dispatch_tool(
            "classify_claim",
            {"claim_type": "auto", "confidence": 5.0, "rationale": "x"},
        )
    )
    assert result["is_error"] is True


def test_classify_claim_bad_category_is_graceful():
    result = json.loads(
        dispatch_tool(
            "classify_claim",
            {"claim_type": "not_real", "confidence": 0.5, "rationale": "x"},
        )
    )
    assert result["is_error"] is True


def test_assess_severity_success():
    result = json.loads(
        dispatch_tool("assess_severity", {"severity": "high", "rationale": "Total loss."})
    )
    assert result["is_error"] is False
    assert result["severity"] == "high"


def test_assess_severity_bad_level_is_graceful():
    result = json.loads(
        dispatch_tool("assess_severity", {"severity": "catastrophic", "rationale": "x"})
    )
    assert result["is_error"] is True


def test_unknown_tool_is_graceful_not_a_crash():
    result = json.loads(dispatch_tool("delete_everything", {}))
    assert result["is_error"] is True
    assert "Unknown tool" in result["message"]


def test_errors_are_json_strings_never_raised_exceptions():
    # This is the contract: dispatch_tool NEVER raises for bad input.
    try:
        result_str = dispatch_tool("lookup_policy", {"policy_id": "NOPE"})
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"dispatch_tool raised instead of returning gracefully: {exc}")
    assert isinstance(result_str, str)
    parsed = json.loads(result_str)  # must be valid JSON
    assert parsed["is_error"] is True


# ---- 7c. The four required AST audit tests, named for their anti-pattern -

def test_no_natural_language_termination():
    tree = _get_loop_source_tree()
    offenders = audit_no_natural_language_termination(tree)
    assert offenders == [], f"Natural-language termination found: {offenders}"


def test_no_integer_literal_iteration_cap():
    tree = _get_loop_source_tree()
    offenders = audit_no_integer_literal_iteration_cap(tree)
    assert offenders == [], f"Integer-literal iteration cap found: {offenders}"


def test_no_text_content_completion_check():
    tree = _get_loop_source_tree()
    offenders = audit_no_text_content_completion_check(tree)
    assert offenders == [], f"Text-content completion check found: {offenders}"


def test_no_claim_type_string_branching():
    tree = _get_loop_source_tree()
    offenders = audit_no_claim_type_string_branching(tree)
    assert offenders == [], f"claim_type string branching found: {offenders}"


# ---- 7d. Positive controls: prove each audit actually catches its pattern

def test_audit_catches_natural_language_termination_regression():
    bad = 'def f(text):\n    if "done" in text:\n        return "finished"\n'
    offenders = audit_no_natural_language_termination(ast.parse(bad))
    assert offenders != []


def test_audit_catches_integer_literal_iteration_cap_regression():
    bad = "def f():\n    for i in range(10):\n        pass\n"
    offenders = audit_no_integer_literal_iteration_cap(ast.parse(bad))
    assert offenders != []


def test_audit_catches_text_content_completion_check_regression():
    bad = 'def f(response):\n    if response.text:\n        return "done"\n'
    offenders = audit_no_text_content_completion_check(ast.parse(bad))
    assert offenders != []


def test_audit_catches_claim_type_branching_regression():
    bad = 'def f(claim_type):\n    if claim_type == "theft":\n        route_to_theft_queue()\n'
    offenders = audit_no_claim_type_string_branching(ast.parse(bad))
    assert offenders != []


# =============================================================================
# STANDALONE TEST RUNNER
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
