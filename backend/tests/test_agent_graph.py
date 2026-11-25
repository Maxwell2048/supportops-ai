"""The LangGraph orchestration must behave exactly like the hand-written tool loop.

Both implementations run against the same scripted planner and the same fake ``run_call``;
every observable result (trace, executed calls, planner inputs, evidence, context, errors)
must be identical.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from supportops import agent_graph, agent_tools
from supportops.agent_tools import MAX_CALLS, MAX_ROUNDS, ToolStopped
from supportops.config import Settings
from supportops.generation import GenerationError, GenerationFailure, ToolCall

TITLE = "Cannot sign in"
TICKET = TITLE + "\nThe account locked after a password reset."
LOOPS = {"handwritten": agent_tools.gather, "langgraph": agent_graph.gather}


def search(query, **extra):
    return ToolCall(name="search_knowledge", arguments={"query": query, **extra})


HISTORY = ToolCall(name="ticket_history")

SCENARIOS = {
    "history_then_search": [[HISTORY, search("reset password lock")], []],
    "model_runs_the_baseline": [[search(TITLE)]],
    "planner_skips_tools": [[]],
    "budget_exceeded_within_a_round": [[search(f"query {index}") for index in range(MAX_CALLS + 2)], [HISTORY]],
    "budget_spent_across_rounds": [[HISTORY, HISTORY, HISTORY], [HISTORY, HISTORY], [HISTORY]],
    "round_limit": [[HISTORY]] * (MAX_ROUNDS + 2),
    "refused_calls": [[
        ToolCall(name="update_ticket", arguments={"status": "closed"}),
        ToolCall(name="ticket_history", arguments={"ticket_id": "another-ticket"}),
        search("x", limit=99),
        search(""),
    ], [search("never planned")]],
    "refused_then_corrected": [[search(5)], [search("account status")], []],
    "evidence_cap": [[search(f"query {index}") for index in range(MAX_CALLS)]],
}


class Planner:
    """Replays scripted rounds and records exactly what the planner was shown."""

    def __init__(self, rounds, fail_on=None):
        self.rounds, self.fail_on, self.seen = [list(calls) for calls in rounds], fail_on, []

    def plan(self, ticket, observations, tools):
        self.seen.append(json.loads(json.dumps({"ticket": ticket, "observations": observations,
                                                "tools": [tool["function"]["name"] for tool in tools]})))
        if self.fail_on == len(self.seen):
            raise GenerationError(GenerationFailure.TIMEOUT)
        return self.rounds.pop(0) if self.rounds else []

    def generate(self, ticket, evidence, context=None):  # pragma: no cover - not reached by gather
        raise AssertionError("gather must not draft")


class Legacy:
    """A provider without a planner."""


def fake_run_call(monkeypatch, stop_on=None):
    executed = []

    def run_call(engine, job_id, token, name, args):
        executed.append((name, args.model_dump()))
        if stop_on == len(executed):
            raise ToolStopped("access_or_ticket_changed", [])
        if name == "ticket_history":
            rows = [json.dumps({"kind": "message", "body": f"public message {index}"}) for index in range(2)]
            return {"items": [json.loads(row) for row in rows]}, [], rows
        hits = [SimpleNamespace(chunk_id=uuid5(NAMESPACE_URL, f"{args.query}/{index}")) for index in range(args.limit)]
        if args.query == TITLE:
            hits = hits[:2]
        return {"passages": [{"chunk_id": str(hit.chunk_id)} for hit in hits]}, hits, []

    monkeypatch.setattr(agent_tools, "run_call", run_call)
    return executed


def observe(monkeypatch, loop, provider_factory, stop_on=None):
    executed = fake_run_call(monkeypatch, stop_on)
    provider = provider_factory()
    try:
        gathered = LOOPS[loop](None, "job", "token", provider, TICKET, TITLE)
        outcome = {"hits": [str(hit.chunk_id) for hit in gathered.hits], "context": gathered.context,
                   "trace": gathered.trace}
    except (ToolStopped, GenerationError) as error:
        outcome = {"error": type(error).__name__, "code": getattr(error, "code", None),
                   "kind": getattr(error, "kind", None), "trace": getattr(error, "trace", None)}
    return {**outcome, "executed": executed, "planner": getattr(provider, "seen", None)}


def both(monkeypatch, provider_factory, stop_on=None):
    handwritten = observe(monkeypatch, "handwritten", provider_factory, stop_on)
    graph = observe(monkeypatch, "langgraph", provider_factory, stop_on)
    assert graph == handwritten
    return handwritten


def statuses(result):
    return [(row["round"], row["planner"], row["tool"], row["status"]) for row in result["trace"]]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_graph_matches_the_handwritten_loop(monkeypatch, scenario):
    result = both(monkeypatch, lambda: Planner(SCENARIOS[scenario]))
    assert sum(row["planner"] == "model" for row in result["trace"]) <= MAX_CALLS + 2
    assert len(result["planner"]) <= MAX_ROUNDS


def test_budget_is_enforced_identically(monkeypatch):
    result = both(monkeypatch, lambda: Planner(SCENARIOS["budget_exceeded_within_a_round"]))
    assert [row["status"] for row in result["trace"]] == ["ok"] * MAX_CALLS + ["budget_exceeded"] * 2 + ["ok"]
    # Once the budget is spent the planner is not asked again; only the unbudgeted baseline runs.
    assert len(result["planner"]) == 1
    assert statuses(result)[-1] == (2, "system", "search_knowledge", "ok")
    assert len(result["executed"]) == MAX_CALLS + 1


def test_round_limit_is_enforced_identically(monkeypatch):
    result = both(monkeypatch, lambda: Planner(SCENARIOS["round_limit"]))
    assert len(result["planner"]) == MAX_ROUNDS
    assert [row["round"] for row in result["trace"]] == list(range(1, MAX_ROUNDS + 2))


def test_refused_calls_are_identical_and_consume_budget(monkeypatch):
    result = both(monkeypatch, lambda: Planner(SCENARIOS["refused_calls"]))
    assert [(row["tool"], row["status"], row.get("reason")) for row in result["trace"]] == [
        ("update_ticket", "rejected", "tool_not_allowed"),
        ("ticket_history", "rejected", "invalid_arguments"),
        ("search_knowledge", "rejected", "invalid_arguments"),
        ("search_knowledge", "rejected", "invalid_arguments"),
        ("search_knowledge", "ok", None),
    ]
    # Rejected calls never reach run_call; only the server's baseline search executed.
    assert result["executed"] == [("search_knowledge", {"query": TITLE, "limit": 5})]
    assert result["trace"][1]["errors"] == ["ticket_id:extra_forbidden"]
    assert all("arguments" not in row for row in result["trace"][:4])
    assert len(result["planner"]) == 1


def test_planner_sees_the_same_rejection_feedback(monkeypatch):
    result = both(monkeypatch, lambda: Planner(SCENARIOS["refused_then_corrected"]))
    assert result["planner"][1]["observations"] == [
        {"tool": "search_knowledge", "error": "invalid_arguments", "details": ["query:string_type"]}]
    assert result["planner"][0]["tools"] == ["search_knowledge", "ticket_history"]


def test_baseline_evidence_survives_the_cap_in_both(monkeypatch):
    result = both(monkeypatch, lambda: Planner(SCENARIOS["evidence_cap"]))
    baseline = [str(uuid5(NAMESPACE_URL, f"{TITLE}/{index}")) for index in range(2)]
    assert len(result["hits"]) == 20 and result["hits"][:2] == baseline


def test_provider_without_planner_runs_one_system_search_in_both(monkeypatch):
    result = both(monkeypatch, Legacy)
    assert statuses(result) == [(1, "system", "search_knowledge", "ok")]


@pytest.mark.parametrize("stop_on", [1, 2])
def test_stopped_call_ends_both_loops_with_the_same_trace(monkeypatch, stop_on):
    result = both(monkeypatch, lambda: Planner(SCENARIOS["history_then_search"]), stop_on=stop_on)
    assert (result["error"], result["code"]) == ("ToolStopped", "access_or_ticket_changed")
    assert result["trace"][-1]["status"] == "stopped" and len(result["trace"]) == stop_on


def test_planner_failure_propagates_unchanged_from_both(monkeypatch):
    result = both(monkeypatch, lambda: Planner([[HISTORY], [HISTORY]], fail_on=2))
    assert (result["error"], result["kind"]) == ("GenerationError", GenerationFailure.TIMEOUT)
    assert result["executed"] == [("ticket_history", {"limit": 10})]


def test_graph_shape_and_no_persistence():
    drawn = agent_graph.GRAPH.get_graph()
    assert set(drawn.nodes) == {"__start__", "plan", "execute", "finish", "__end__"}
    assert {(edge.source, edge.target) for edge in drawn.edges} == {
        ("__start__", "plan"), ("__start__", "finish"), ("plan", "execute"), ("plan", "finish"),
        ("execute", "plan"), ("execute", "finish"), ("finish", "__end__")}
    # Job state never leaves the worker: no checkpointer is attached.
    assert agent_graph.GRAPH.checkpointer is None
    # The budget lives in the server-side ledger, not in a channel a node update could overwrite.
    assert set(agent_graph.LoopState.__annotations__) == {"round", "last_round", "requested"}


@pytest.mark.parametrize("variable", agent_graph.TRACING_VARIABLES)
def test_graph_refuses_to_run_with_external_tracing(monkeypatch, variable):
    executed = fake_run_call(monkeypatch)
    planner = Planner(SCENARIOS["history_then_search"])
    monkeypatch.setenv(variable, "true")
    with pytest.raises(RuntimeError, match=variable):
        agent_graph.gather(None, "job", "token", planner, TICKET, TITLE)
    assert executed == [] and planner.seen == []


def test_handwritten_loop_is_the_default():
    assert Settings().analysis_loop == "handwritten"
    assert agent_tools.gatherer() is agent_tools.gather
    assert agent_tools.gatherer("langgraph") is agent_graph.gather
    with pytest.raises(ValueError):
        agent_tools.gatherer("other")
    with pytest.raises(ValueError, match="ANALYSIS_LOOP"):
        Settings(analysis_loop="other")


def test_default_job_path_does_not_import_langgraph():
    source = Path(__file__).resolve().parents[1] / "src"
    code = "import sys, supportops.jobs, supportops.job_worker; print(any(name.startswith('lang') for name in sys.modules))"
    env = {**os.environ, "PYTHONPATH": str(source)}
    output = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    assert output.stdout.strip() == "False"


def test_worst_case_routing_fits_the_recursion_backstop(monkeypatch):
    # The longest normal run (every round used) needs exactly the limit: the input step, two per round and finish.
    # One step fewer must already fire, so the backstop catches any extra step a routing defect would add.
    assert agent_graph.RECURSION_LIMIT == 2 * MAX_ROUNDS + 2
    fake_run_call(monkeypatch)
    agent_graph.gather(None, "job", "token", Planner(SCENARIOS["round_limit"]), TICKET, TITLE)
    monkeypatch.setattr(agent_graph, "RECURSION_LIMIT", 2 * MAX_ROUNDS + 1)
    with pytest.raises(ToolStopped):
        agent_graph.gather(None, "job", "token", Planner(SCENARIOS["round_limit"]), TICKET, TITLE)


def test_recursion_backstop_stops_with_a_defined_code_and_the_trace(monkeypatch):
    monkeypatch.setattr(agent_graph, "RECURSION_LIMIT", 2)
    executed = fake_run_call(monkeypatch)
    planner = Planner(SCENARIOS["round_limit"])
    with pytest.raises(ToolStopped) as stopped:
        agent_graph.gather(None, "job", "token", planner, TICKET, TITLE)
    assert stopped.value.code == agent_graph.LIMIT_ERROR == "tool_loop_limit"
    # The calls that ran before the limit stay in the trace; the baseline is not added after a defect.
    assert [(row["round"], row["tool"], row["status"]) for row in stopped.value.trace] == [(1, "ticket_history", "ok")]
    assert executed == [("ticket_history", {"limit": 10})] and len(planner.seen) == 1


def test_recursion_backstop_becomes_a_non_transient_job_failure(monkeypatch):
    from supportops import jobs

    monkeypatch.setattr(agent_graph, "RECURSION_LIMIT", 2)
    fake_run_call(monkeypatch)
    job = SimpleNamespace(requester_id="agent", ticket_id="ticket", ticket_version=1)
    ticket = SimpleNamespace(version=1, archived=False, title=TITLE, body="The account locked.")

    class FakeSession:
        def __init__(self, engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def scalar(self, statement):
            return job

        def get(self, model, key):
            return SimpleNamespace(active=True, role="agent")

    finished = []
    monkeypatch.setattr(jobs, "Session", FakeSession)
    monkeypatch.setattr(jobs, "visible_ticket", lambda session, actor, ticket_id: ticket)
    monkeypatch.setattr(jobs, "finish_job", lambda *args, **kwargs: finished.append((args, kwargs)) or True)
    assert jobs.execute_job(None, "job", "token", Planner(SCENARIOS["round_limit"]), loop="langgraph")
    (args, kwargs), = finished
    assert args == (None, "job", "token")
    assert kwargs["error"] == "tool_loop_limit" and not kwargs.get("transient", False)
    assert [row["tool"] for row in kwargs["tool_trace"]] == ["ticket_history"]
    assert "result" not in kwargs and kwargs["provider_info"] == ("custom", None, None)
