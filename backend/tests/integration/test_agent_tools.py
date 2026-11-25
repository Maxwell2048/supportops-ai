import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from supportops.agent_tools import MAX_CALLS
from supportops.generation import MockGeneration, ToolCall
from supportops.jobs import execute_job
from supportops.models import AnalysisJob, Ticket, TicketMessage, User
from supportops.reviews import get_suggestion
from supportops.seed import synthetic_id
from test_citations import enqueue, prepared, setup_source

pytestmark = pytest.mark.integration

TICKET = synthetic_id("ticket-1")
AGENT = synthetic_id("agent-a")


class Scripted(MockGeneration):
    """Replays planned rounds and records what the planner and the drafter observed."""

    def __init__(self, rounds, on_plan=None):
        self.rounds, self.on_plan = list(rounds), on_plan
        self.observations, self.context, self.tools = [], None, None

    def plan(self, ticket, observations, tools):
        self.observations.append(json.loads(json.dumps(observations)))
        self.tools = [tool["function"]["name"] for tool in tools]
        if self.on_plan:
            self.on_plan(len(self.observations))
        return self.rounds.pop(0) if self.rounds else []

    def generate(self, ticket, evidence, context=None):
        self.context = context
        return super().generate(ticket, evidence, context)


def stored(engine, job_id):
    with Session(engine) as session:
        return session.get(AnalysisJob, job_id)


def summary(trace):
    return [(row["planner"], row["tool"], row["status"], row.get("reason")) for row in trace]


def test_mock_agent_reads_history_and_cites_authorized_evidence(prepared):
    setup_source(prepared)
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, MockGeneration())
    job = stored(prepared, claim[0])
    assert job.status == "succeeded" and job.result["citations"]
    assert summary(job.tool_trace) == [("model", "ticket_history", "ok", None), ("model", "search_knowledge", "ok", None)]
    assert job.tool_trace[1]["arguments"] == {"query": "Cannot sign in to the sample product", "limit": 5}
    assert job.tool_trace[1]["result_count"] >= 1
    with Session(prepared) as session:
        body = get_suggestion(session, session.get(User, AGENT), claim[0])
    assert body["tool_calls"] == job.tool_trace


def test_history_excludes_internal_notes_and_baseline_search_still_runs(prepared):
    setup_source(prepared)
    with Session(prepared) as session, session.begin():
        session.add_all([
            TicketMessage(id=uuid4(), ticket_id=TICKET, author_id=synthetic_id("requester-a"), visibility="public", body="Public detail: the lock started today."),
            TicketMessage(id=uuid4(), ticket_id=TICKET, author_id=AGENT, visibility="internal", body="Internal note: never share this."),
        ])
    provider = Scripted([[ToolCall(name="ticket_history")]])
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, provider)
    seen = json.dumps(provider.observations) + json.dumps(provider.context)
    assert "Public detail" in seen and "Internal note" not in seen
    items = provider.observations[1][0]["result"]["items"]
    assert {row["from"] for row in items if row["kind"] == "message"} == {"requester"}
    job = stored(prepared, claim[0])
    assert job.status == "succeeded"
    # The planner skipped retrieval, so the server added its own authorized baseline search.
    assert summary(job.tool_trace) == [("model", "ticket_history", "ok", None), ("system", "search_knowledge", "ok", None)]


def test_disallowed_tools_and_arguments_are_rejected_without_side_effects(prepared):
    setup_source(prepared)
    provider = Scripted([[
        ToolCall(name="update_ticket", arguments={"status": "closed"}),
        ToolCall(name="ticket_history", arguments={"ticket_id": str(uuid4())}),
        ToolCall(name="search_knowledge", arguments={"query": 5}),
    ], [ToolCall(name="search_knowledge", arguments={"query": "account status"})]])
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, provider)
    assert provider.tools == ["search_knowledge", "ticket_history"]
    job = stored(prepared, claim[0])
    assert job.status == "succeeded"
    assert summary(job.tool_trace) == [
        ("model", "update_ticket", "rejected", "tool_not_allowed"),
        ("model", "ticket_history", "rejected", "invalid_arguments"),
        ("model", "search_knowledge", "rejected", "invalid_arguments"),
        ("model", "search_knowledge", "ok", None),
        ("system", "search_knowledge", "ok", None),
    ]
    assert "arguments" not in job.tool_trace[0]
    assert job.tool_trace[2]["errors"] == ["query:string_type"]
    assert [row.get("error") for row in provider.observations[1][:3]] == ["tool_not_allowed", "invalid_arguments", "invalid_arguments"]
    # The planner receives error locations and types so it can correct itself, but never echoed values.
    assert provider.observations[1][1]["details"] == ["ticket_id:extra_forbidden"]
    with Session(prepared) as session:
        ticket = session.get(Ticket, TICKET)
        assert (ticket.status, ticket.version, ticket.archived) == ("open", 1, False)


def test_call_budget_is_enforced(prepared):
    setup_source(prepared)
    provider = Scripted([[ToolCall(name="ticket_history")] * (MAX_CALLS + 2), [ToolCall(name="ticket_history")]])
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, provider)
    statuses = [row["status"] for row in stored(prepared, claim[0]).tool_trace]
    assert statuses == ["ok"] * MAX_CALLS + ["budget_exceeded"] * 2 + ["ok"]
    assert len(provider.observations) == 1


@pytest.mark.parametrize("change", ["reassigned", "deactivated", "ticket_changed"])
def test_each_call_rechecks_current_access(prepared, change):
    setup_source(prepared)

    def revoke(round_number):
        with Session(prepared) as session, session.begin():
            if change == "reassigned":
                session.execute(update(Ticket).where(Ticket.id == TICKET).values(assignee_id=synthetic_id("agent-b")))
            elif change == "deactivated":
                session.execute(update(User).where(User.id == AGENT).values(active=False))
            else:
                session.execute(update(Ticket).where(Ticket.id == TICKET).values(version=2))

    provider = Scripted([[ToolCall(name="search_knowledge", arguments={"query": "account status"})]], on_plan=revoke)
    claim = enqueue(prepared)
    try:
        assert execute_job(prepared, *claim, provider)
        job = stored(prepared, claim[0])
        assert (job.status, job.error_code, job.result) == ("failed", "access_or_ticket_changed", None)
        assert summary(job.tool_trace) == [("model", "search_knowledge", "stopped", None)]
        assert len(provider.observations) == 1 and provider.context is None
    finally:
        with Session(prepared) as session, session.begin():
            session.execute(update(Ticket).where(Ticket.id == TICKET).values(version=1))


def test_lost_lease_stops_tool_use_without_finishing(prepared):
    setup_source(prepared)
    claim = enqueue(prepared)

    def expire(round_number):
        with Session(prepared) as session, session.begin():
            now = session.scalar(select(func.clock_timestamp()))
            session.execute(update(AnalysisJob).where(AnalysisJob.id == claim[0]).values(lease_expires_at=now))

    assert not execute_job(prepared, *claim, Scripted([[ToolCall(name="ticket_history")]], on_plan=expire))
    job = stored(prepared, claim[0])
    assert (job.status, job.result, job.tool_trace) == ("running", None, None)


def test_provider_without_planner_uses_one_system_search(prepared):
    setup_source(prepared)
    seen = {}

    class Legacy:
        def generate(self, ticket, evidence):
            seen["evidence"] = evidence
            return MockGeneration().generate(ticket, evidence)

    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Legacy())
    job = stored(prepared, claim[0])
    assert job.status == "succeeded" and seen["evidence"]
    assert summary(job.tool_trace) == [("system", "search_knowledge", "ok", None)]


def test_restricted_source_never_reaches_the_planner(prepared):
    setup_source(prepared, scope="management", body="Restricted management procedure for escalations.")
    provider = Scripted([[ToolCall(name="search_knowledge", arguments={"query": "management procedure escalations"})]])
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, provider)
    assert provider.observations[1][0]["result"]["passages"] == []
    assert "Restricted management" not in json.dumps(provider.observations)
    job = stored(prepared, claim[0])
    assert job.status == "succeeded" and "Restricted management" not in json.dumps(job.result)
    # The model's own query was not the baseline, so the server still ran its authorized title search.
    assert summary(job.tool_trace)[-1] == ("system", "search_knowledge", "ok", None)
