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

## Recursion backstop follow-up on 2026-11-25

- Change: `agent_graph.gather` converts LangGraph's `GraphRecursionError` into `ToolStopped("tool_loop_limit", trace)`, which `execute_job` records as a failed, non-transient job with the trace gathered so far. Before this change the error would have escaped `execute_job` and the worker loop.
- Measurement: with the worst-case scenario (all three rounds used), the graph ran 7 node steps and needed a recursion limit of at least 8 because LangGraph also counts the input step. The configured limit of 8 is therefore exactly the minimum. The earlier code comment did not count the input step; it now states the exact count, and a test pins that 8 passes and 7 fires.
- `cd backend; uv run pytest`: 113 passed, 265 skipped. All 265 skips report "Set TEST_DATABASE_URL to a dedicated PostgreSQL test database". The 3 new unit tests force the backstop through `gather` and through `execute_job` with fake database access, and check the exact bound. Replacing the `except GraphRecursionError` clause with an unrelated exception made those 3 tests fail; the file was restored. The fresh-interpreter test that the default path imports no LangGraph or LangChain module still passes.
- Database: not reachable. `TEST_DATABASE_URL` was unset, the Docker engine was still not running, and nothing was listening on the configured local PostgreSQL port. The 20 tool-loop integration cases and the new `test_agent_graph_limit.py` case did not run, and no database result is claimed.
