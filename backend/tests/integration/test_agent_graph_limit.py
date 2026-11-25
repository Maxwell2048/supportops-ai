"""The LangGraph recursion backstop must end a real job as a stored, non-transient failure."""
import pytest
from sqlalchemy.orm import Session

from supportops import agent_graph
from supportops.generation import ToolCall
from supportops.jobs import execute_job
from supportops.models import AnalysisJob
from test_agent_tools import Scripted
from test_citations import enqueue, prepared, setup_source

pytestmark = pytest.mark.integration


def test_recursion_backstop_fails_the_job_and_keeps_the_trace(prepared, monkeypatch):
    setup_source(prepared)
    monkeypatch.setattr(agent_graph, "RECURSION_LIMIT", 2)
    provider = Scripted([[ToolCall(name="ticket_history")]] * 5)
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, provider, loop="langgraph")
    with Session(prepared) as session:
        job = session.get(AnalysisJob, claim[0])
        assert (job.status, job.error_code, job.result) == ("failed", "tool_loop_limit", None)
        assert job.lease_token is None and job.attempts == 1
        assert [(row["tool"], row["status"]) for row in job.tool_trace] == [("ticket_history", "ok")]
