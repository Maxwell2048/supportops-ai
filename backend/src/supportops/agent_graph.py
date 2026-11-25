"""Optional LangGraph orchestration of the analysis tool loop.

The graph expresses the same bounded flow as ``agent_tools.gather`` as an explicit state machine:

    START -> plan -> execute -> plan ... -> finish -> END

LangGraph owns only the control flow. Every node delegates to the shared ``agent_tools.ToolLoop``,
so tool calls still go through ``run_call`` (lease renewal plus current role and object checks),
the call budget and the audit trace live in the server-side ledger, and model output and tool
results remain untrusted data. No checkpointer is attached: a job's state never leaves the worker
process, and a recovered job restarts from its lease as before.
"""
import os
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from supportops.agent_tools import MAX_ROUNDS, ToolLoop, ToolStopped

# LangChain components export runs to LangSmith when these variables are set. Ticket text and
# retrieved passages must not leave the deployment, so the graph refuses to run with them enabled.
TRACING_VARIABLES = ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2")

# LangGraph counts the input as a step, each round adds two (plan, execute) and ``finish`` adds one, so the
# longest normal run needs exactly 2 * MAX_ROUNDS + 2. The round counter in the state is the real bound; this
# limit is a tight backstop, so any extra step caused by a routing defect stops the job.
RECURSION_LIMIT = 2 * MAX_ROUNDS + 2
# Job error code (at most 32 characters) recorded when the backstop fires.
LIMIT_ERROR = "tool_loop_limit"


class LoopState(TypedDict):
    """Control-flow state only. The budget and evidence are deliberately not graph channels,
    so no node update can reset the call count or inject evidence."""

    round: int
    last_round: int
    requested: list


def ensure_no_external_tracing():
    enabled = [name for name in TRACING_VARIABLES if os.getenv(name, "").strip().lower() not in {"", "0", "false", "no"}]
    if enabled:
        raise RuntimeError("External LangChain tracing must stay disabled for analysis jobs: " + ", ".join(enabled))


def _loop(config: RunnableConfig) -> ToolLoop:
    return config["configurable"]["tool_loop"]


def _plan(state: LoopState, config: RunnableConfig):
    # Stored as returned so that routing applies the same truthiness test as the hand-written loop.
    return {"requested": _loop(config).plan(state["round"])}


def _execute(state: LoopState, config: RunnableConfig):
    _loop(config).run_round(state["round"], state["requested"])
    return {"last_round": state["round"], "round": state["round"] + 1, "requested": []}


def _finish(state: LoopState, config: RunnableConfig):
    _loop(config).finish(state["last_round"])
    return {}


def _next_round(state: LoopState, config: RunnableConfig):
    # Same stop conditions, checked in the same place, as the hand-written loop.
    if state["round"] > MAX_ROUNDS or _loop(config).exhausted:
        return "finish"
    return "plan"


def _after_plan(state: LoopState):
    return "execute" if state["requested"] else "finish"


def build_graph():
    graph = StateGraph(LoopState)
    graph.add_node("plan", _plan)
    graph.add_node("execute", _execute)
    graph.add_node("finish", _finish)
    graph.add_conditional_edges(START, _next_round, ["plan", "finish"])
    graph.add_conditional_edges("plan", _after_plan, ["execute", "finish"])
    graph.add_conditional_edges("execute", _next_round, ["plan", "finish"])
    graph.add_edge("finish", END)
    return graph.compile()


GRAPH = build_graph()


def gather(engine, job_id, token, provider, ticket_text, title):
    """Drop-in replacement for ``agent_tools.gather`` that runs the loop as a LangGraph graph."""
    ensure_no_external_tracing()
    loop = ToolLoop(engine, job_id, token, provider, ticket_text, title)
    try:
        GRAPH.invoke({"round": 1, "last_round": 0, "requested": []},
                     config={"configurable": {"tool_loop": loop}, "recursion_limit": RECURSION_LIMIT})
    except GraphRecursionError:
        # Normal routing always fits RECURSION_LIMIT, so this means a routing defect. Stop the job
        # as a defined, non-transient failure that keeps the calls already recorded; retrying would repeat it.
        raise ToolStopped(LIMIT_ERROR, loop.trace) from None
    # ``finish`` ran inside the graph; read the result from the ledger rather than from graph state.
    return loop.result
