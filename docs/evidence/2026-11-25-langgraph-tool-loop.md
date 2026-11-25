# Optional LangGraph tool loop verification

Implemented: a shared `ToolLoop` ledger in `agent_tools.py` used by both the hand-written loop and a new LangGraph `StateGraph` in `agent_graph.py`, an `ANALYSIS_LOOP` setting (default `handwritten`), a tracing guard, parity tests and integration cases parametrized over both orchestrations. See [design](../langgraph-tool-loop.md).

## Automated checks on 2026-11-25

- `cd backend; uv run pytest`: 110 passed, 264 skipped. Every skip is a PostgreSQL integration test with the reason "Set TEST_DATABASE_URL to a dedicated PostgreSQL test database". No PostgreSQL server was reachable in this session (the Docker engine was not running and no local server was listening), so no integration test ran.
- The 110 passing tests include 25 new tests in `tests/test_agent_graph.py` and the 4 existing hand-written loop tests in `tests/test_agent_loop.py`, which pass unchanged after the loop body moved into `ToolLoop`.
- Parity tests compare traces, executed calls, planner inputs, evidence order, context and raised errors between the two orchestrations across 12 scenarios, plus graph shape, the absence of a checkpointer, the four tracing variables, default selection, invalid configuration and a fresh-interpreter check that the default job path imports no LangGraph or LangChain module.
- Mutation check: removing the graph's budget check, shifting its round limit by one, or recording the wrong last round each made the parity tests fail (7, 2 and 12 failures). The original file was restored and all 25 tests passed again.

## Not verified

- The 20 PostgreSQL tool-loop integration cases (10 cases, each under both orchestrations) and the rest of the database suite were not executed in this session.
- No real model, including the pinned local Ollama model, was run through the LangGraph path. The frontend was not rebuilt because no frontend file changed.
- No remote CI ran for this change.
