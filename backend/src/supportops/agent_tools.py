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


def gather(engine, job_id, token, provider, ticket_text, title):
    """Run the bounded planning loop and return authorized evidence, context and a trace."""
    planner = getattr(provider, "plan", None)
    specs = tool_specs()
    trace, observations, context, hits = [], [], [], {}
    used, baseline_done, baseline_ids = 0, False, []

    def execute(call, round_number, source, *, budgeted=True):
        nonlocal used, baseline_done
        entry = {"round": round_number, "planner": source, "tool": call.name[:64], "status": "ok", "result_count": 0}
        trace.append(entry)
        if budgeted:
            if used >= MAX_CALLS:
                entry["status"] = "budget_exceeded"
                return
            used += 1
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
            observations.append({"tool": entry["tool"], "error": entry["reason"], **({"details": entry["errors"]} if "errors" in entry else {})})
            return
        entry["arguments"] = args.model_dump()
        try:
            observation, found, rows = run_call(engine, job_id, token, call.name, args)
        except ToolStopped as stop:
            entry["status"] = "stopped"
            raise ToolStopped(stop.code, trace) from None
        is_baseline = call.name == "search_knowledge" and args.query.strip() == title.strip() and args.limit == 5
        for hit in found:
            hits.setdefault(hit.chunk_id, hit)
            if is_baseline and hit.chunk_id not in baseline_ids:
                baseline_ids.append(hit.chunk_id)
        context.extend(rows)
        baseline_done = baseline_done or is_baseline
        entry["result_count"] = len(found) if call.name == "search_knowledge" else len(rows)
        observations.append({"tool": call.name, "arguments": entry["arguments"], "result": observation})

    last_round = 0
    for round_number in range(1, MAX_ROUNDS + 1):
        if used >= MAX_CALLS:
            break
        if planner is None:
            requested = [ToolCall(name="search_knowledge", arguments={"query": title})] if round_number == 1 else []
        else:
            requested = planner(ticket_text, observations, specs)
        if not requested:
            break
        last_round = round_number
        for call in requested:
            execute(call, round_number, "model" if planner else "system")
    if not baseline_done:
        # The planner may add evidence and context but cannot replace the baseline authorized title search,
        # so tool use never yields less evidence than the fixed pipeline.
        execute(ToolCall(name="search_knowledge", arguments={"query": title}), last_round + 1, "system", budgeted=False)
    # Baseline passages are kept first so the 20-passage evidence cap can never drop them.
    ordered = [hits[chunk_id] for chunk_id in baseline_ids] + [hit for chunk_id, hit in hits.items() if chunk_id not in baseline_ids]
    return Gathered(hits=ordered[:20], context=list(dict.fromkeys(context))[-20:], trace=trace)
