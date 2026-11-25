"""Controlled read-only tool use for analysis jobs.

A planner (the model) may only request tools from this allow-list. The server validates
every request, enforces a call budget, and runs each allowed call in its own short
transaction that first renews the job lease and re-checks the requesting staff member's
current access to the ticket. No tool can write, and tool parameters never name a ticket:
history is bound to the ticket being analyzed.
"""
from dataclasses import dataclass
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from supportops import retrieval
from supportops.dependencies import visible_ticket
from supportops.errors import ApiError
from supportops.generation import ToolCall
from supportops.models import AnalysisJob, TicketEvent, TicketMessage, User
from supportops.retrieval_schemas import SearchQuery

MAX_ROUNDS = 3
MAX_CALLS = 4
STAFF = {"agent", "manager"}


class SearchKnowledgeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=5)


class TicketHistoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int = Field(default=10, ge=1, le=10)


class ToolStopped(Exception):
    """Stops the whole job: the lease was lost or current access no longer allows reading."""

    def __init__(self, code, trace):
        self.code = code
        self.trace = trace
        super().__init__(code)


@dataclass
class Gathered:
    hits: list
    context: list[str]
    trace: list[dict]


def _search(session, actor, ticket, args):
    query = SearchQuery(q=args.query, mode="keyword", limit=args.limit)
    try:
        found = retrieval.search(session, actor, query, None)
    except ApiError:
        raise ToolStopped("retrieval_or_access_unavailable", []) from None
    if found.indexed_versions < found.available_versions:
        raise ToolStopped("retrieval_or_access_unavailable", [])
    passages = [{"chunk_id": str(hit.chunk_id), "version_id": str(hit.version_id), "title": hit.title, "text": hit.text}
                for hit in found.items]
    return {"passages": passages}, list(found.items), []


def _history(session, actor, ticket, args):
    # Internal notes are excluded: the draft becomes a public reply.
    messages = session.scalars(select(TicketMessage).where(
        TicketMessage.ticket_id == ticket.id, TicketMessage.visibility == "public",
    ).order_by(TicketMessage.created_at.desc(), TicketMessage.id.desc()).limit(args.limit)).all()
    events = session.scalars(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id)
                             .order_by(TicketEvent.ticket_version.desc()).limit(args.limit)).all()
    rows = [{"kind": "message", "from": "requester" if row.author_id == ticket.requester_id else "staff",
             "created_at": row.created_at.isoformat(), "body": row.body[:1000]} for row in reversed(messages)]
    rows += [{"kind": "event", "event_type": row.event_type, "ticket_version": row.ticket_version,
              "created_at": row.created_at.isoformat()} for row in reversed(events)]
    return {"items": rows}, [], [json.dumps(row) for row in rows]


TOOLS = {
    "search_knowledge": ("Search published support knowledge that the requesting staff member may currently read. "
                         "Returns passages; only these passages can be cited.", SearchKnowledgeArgs, _search),
    "ticket_history": ("Read public messages and status events of the ticket being analyzed. "
                       "Internal notes are never returned.", TicketHistoryArgs, _history),
}


def tool_specs():
    return [{"type": "function", "function": {"name": name, "description": description,
             "parameters": model.model_json_schema()}} for name, (description, model, _) in TOOLS.items()]


def run_call(engine, job_id, token, name, args):
    """Execute one allowed call after renewing the lease and re-checking current access."""
    from supportops.jobs import renew_lease

    with Session(engine) as session, session.begin():
        if not renew_lease(session, job_id, token):
            raise ToolStopped("lease_lost", [])
        job = session.get(AnalysisJob, job_id)
        actor = session.get(User, job.requester_id)
        if actor is None or not actor.active or actor.role not in STAFF:
            raise ToolStopped("access_or_ticket_changed", [])
        try:
            ticket = visible_ticket(session, actor, job.ticket_id)
        except ApiError:
            raise ToolStopped("access_or_ticket_changed", []) from None
        if ticket.version != job.ticket_version or ticket.archived:
            raise ToolStopped("access_or_ticket_changed", [])
        return TOOLS[name][2](session, actor, ticket, args)


class ToolLoop:
    """Server-side ledger shared by every orchestration of the analysis tool loop.

    It owns the call budget, argument validation, authorized execution through ``run_call``,
    the audit trace and the collected evidence. Orchestrators (the hand-written loop below and
    the optional LangGraph graph in ``agent_graph``) only decide which method runs next; they
    never execute tools or change the budget themselves.
    """

    def __init__(self, engine, job_id, token, provider, ticket_text, title):
        self.engine, self.job_id, self.token = engine, job_id, token
        self.ticket_text, self.title = ticket_text, title
        self.planner = getattr(provider, "plan", None)
        self.specs = tool_specs()
        self.trace, self.observations, self.context, self.hits = [], [], [], {}
        self.used, self.baseline_done, self.baseline_ids = 0, False, []
        self.result = None

    @property
    def exhausted(self):
        return self.used >= MAX_CALLS

    def plan(self, round_number):
        """Ask the planner for the next calls; its answer is untrusted until ``execute`` validates it."""
        if self.planner is None:
            return [ToolCall(name="search_knowledge", arguments={"query": self.title})] if round_number == 1 else []
        return self.planner(self.ticket_text, self.observations, self.specs)

    def run_round(self, round_number, requested):
        for call in requested:
            self.execute(call, round_number, "model" if self.planner else "system")

    def execute(self, call, round_number, source, *, budgeted=True):
        entry = {"round": round_number, "planner": source, "tool": call.name[:64], "status": "ok", "result_count": 0}
        self.trace.append(entry)
        if budgeted:
            if self.used >= MAX_CALLS:
                entry["status"] = "budget_exceeded"
                return
            self.used += 1
        tool = TOOLS.get(call.name)
        try:
            if tool is None:
                raise LookupError("tool_not_allowed")
            args = tool[1].model_validate(call.arguments)
            if call.name == "search_knowledge":
                SearchQuery(q=args.query, mode="keyword", limit=args.limit)
        except (LookupError, ValidationError) as error:
            entry["status"], entry["reason"] = "rejected", "tool_not_allowed" if tool is None else "invalid_arguments"
            if isinstance(error, ValidationError):
                # Record where validation failed, never the untrusted values themselves.
                entry["errors"] = sorted({".".join(str(part) for part in item["loc"])[:40] + ":" + item["type"]
                                          for item in error.errors()})[:5]
            # The planner learns what failed so it can correct the next call.
            self.observations.append({"tool": entry["tool"], "error": entry["reason"], **({"details": entry["errors"]} if "errors" in entry else {})})
            return
        entry["arguments"] = args.model_dump()
        try:
            observation, found, rows = run_call(self.engine, self.job_id, self.token, call.name, args)
        except ToolStopped as stop:
            entry["status"] = "stopped"
            raise ToolStopped(stop.code, self.trace) from None
        is_baseline = call.name == "search_knowledge" and args.query.strip() == self.title.strip() and args.limit == 5
        for hit in found:
            self.hits.setdefault(hit.chunk_id, hit)
            if is_baseline and hit.chunk_id not in self.baseline_ids:
                self.baseline_ids.append(hit.chunk_id)
        self.context.extend(rows)
        self.baseline_done = self.baseline_done or is_baseline
        entry["result_count"] = len(found) if call.name == "search_knowledge" else len(rows)
        self.observations.append({"tool": call.name, "arguments": entry["arguments"], "result": observation})

    def finish(self, last_round):
        if not self.baseline_done:
            # The planner may add evidence and context but cannot replace the baseline authorized title search,
            # so tool use never yields less evidence than the fixed pipeline.
            self.execute(ToolCall(name="search_knowledge", arguments={"query": self.title}), last_round + 1, "system", budgeted=False)
        # Baseline passages are kept first so the 20-passage evidence cap can never drop them.
        ordered = [self.hits[chunk_id] for chunk_id in self.baseline_ids] + [
            hit for chunk_id, hit in self.hits.items() if chunk_id not in self.baseline_ids]
        self.result = Gathered(hits=ordered[:20], context=list(dict.fromkeys(self.context))[-20:], trace=self.trace)
        return self.result


def gather(engine, job_id, token, provider, ticket_text, title):
    """Run the bounded planning loop and return authorized evidence, context and a trace."""
    loop = ToolLoop(engine, job_id, token, provider, ticket_text, title)
    last_round = 0
    for round_number in range(1, MAX_ROUNDS + 1):
        if loop.exhausted:
            break
        requested = loop.plan(round_number)
        if not requested:
            break
        last_round = round_number
        loop.run_round(round_number, requested)
    return loop.finish(last_round)


LOOPS = ("handwritten", "langgraph")


def gatherer(loop="handwritten"):
    """Select the orchestration; both share ``ToolLoop`` and therefore the same server enforcement."""
    if loop == "handwritten":
        return gather
    if loop == "langgraph":
        from supportops import agent_graph  # imported lazily so the default path never loads LangGraph

        return agent_graph.gather
    raise ValueError("unknown analysis loop")
