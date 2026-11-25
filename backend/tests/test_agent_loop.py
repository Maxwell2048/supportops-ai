from types import SimpleNamespace
from uuid import uuid4

from supportops import agent_tools
from supportops.generation import ToolCall

TITLE = "Cannot sign in"


class Planner:
    def __init__(self, rounds):
        self.rounds = list(rounds)

    def plan(self, ticket, observations, tools):
        return self.rounds.pop(0) if self.rounds else []


def fake_calls(monkeypatch):
    baseline = SimpleNamespace(chunk_id=uuid4())
    queries = []

    def run_call(engine, job_id, token, name, args):
        queries.append((args.query, args.limit))
        found = [baseline] if args.query == TITLE else [SimpleNamespace(chunk_id=uuid4()) for _ in range(args.limit)]
        return {"passages": []}, found[:args.limit], []

    monkeypatch.setattr(agent_tools, "run_call", run_call)
    return baseline, queries


def test_baseline_evidence_survives_the_evidence_cap(monkeypatch):
    baseline, queries = fake_calls(monkeypatch)
    planner = Planner([[ToolCall(name="search_knowledge", arguments={"query": f"query {index}"}) for index in range(4)]])
    gathered = agent_tools.gather(None, None, None, planner, TITLE + "\nBody", TITLE)
    assert len(gathered.hits) == 20 and gathered.hits[0] is baseline
    assert queries[-1] == (TITLE, 5)
    assert [row["planner"] for row in gathered.trace] == ["model"] * 4 + ["system"]


def test_narrowed_title_search_does_not_replace_the_baseline(monkeypatch):
    _, queries = fake_calls(monkeypatch)
    planner = Planner([[ToolCall(name="search_knowledge", arguments={"query": TITLE, "limit": 1})]])
    agent_tools.gather(None, None, None, planner, TITLE + "\nBody", TITLE)
    assert queries == [(TITLE, 1), (TITLE, 5)]


def test_full_title_search_by_the_model_counts_as_the_baseline(monkeypatch):
    _, queries = fake_calls(monkeypatch)
    planner = Planner([[ToolCall(name="search_knowledge", arguments={"query": TITLE})]])
    gathered = agent_tools.gather(None, None, None, planner, TITLE + "\nBody", TITLE)
    assert queries == [(TITLE, 5)] and [row["planner"] for row in gathered.trace] == ["model"]


def test_offered_tools_are_exactly_the_read_only_allow_list():
    specs = agent_tools.tool_specs()
    assert [spec["function"]["name"] for spec in specs] == ["search_knowledge", "ticket_history"]
    history = specs[1]["function"]["parameters"]
    assert set(history["properties"]) == {"limit"} and history["additionalProperties"] is False
