# Optional LangGraph orchestration of the tool loop

The analysis tool loop ([controlled read-only tool use](agent-tools.md)) has two interchangeable orchestrations. The hand-written loop is the default. An optional LangGraph `StateGraph` expresses the same flow as an explicit state machine. Both delegate every decision that matters for security to the same server-side ledger, so switching between them changes how the control flow is written, not what the model is allowed to do.

## Selecting an implementation

`ANALYSIS_LOOP=handwritten` (default) or `ANALYSIS_LOOP=langgraph`, read by `load_settings()` and passed by the worker to `execute_job(..., loop=...)`. Any other value is a configuration error at startup. The default path never imports LangGraph or LangChain; a test checks this in a fresh interpreter.

The dependency is pinned as `langgraph==1.2.24` in `backend/pyproject.toml`; `uv.lock` records the transitive packages, including `langchain-core` and `langsmith`.

## Shape

```text
START --(rounds left and budget left?)--> plan --(calls requested?)--> execute --(rounds left and budget left?)--> plan ...
  |                                         |                            |
  +---------------- no -------------------> finish <-------- no ---------+--------------> END
```

| Step | Hand-written loop (`agent_tools.gather`) | LangGraph (`agent_graph.gather`) |
|---|---|---|
| Stop before planning | `for round in 1..MAX_ROUNDS` plus `if loop.exhausted: break` | Conditional edge `_next_round` from `START` and from `execute` |
| Ask the planner | `loop.plan(round)` | `plan` node calls `loop.plan(round)` |
| Planner returned nothing | `break` | Conditional edge `_after_plan` to `finish` |
| Run requested calls | `loop.run_round(round, calls)` | `execute` node calls `loop.run_round(round, calls)` |
| Baseline search and evidence ordering | `loop.finish(last_round)` | `finish` node calls `loop.finish(last_round)` |

Generation, citation validation and `finish_job` run after either orchestration in `execute_job`, unchanged. Keeping drafting outside the graph means there is one code path for citation checks, the evidence-free handoff and job completion.

## What LangGraph gives

- The control flow is declared as nodes and edges. The graph can be inspected with `GRAPH.get_graph()`, and a test pins its exact nodes and edges, so a routing change is visible in review.
- The stop conditions are named routing functions rather than `break` statements inside a loop body.
- It is a familiar structure for extending the loop later, for example a human approval step or a separate reflection node, without restructuring the job runner.
- `recursion_limit` (set to `2 * MAX_ROUNDS + 2`) is a second, independent bound if a routing defect ever produced a cycle.

## What the server must still enforce

LangGraph does not provide authorization, budgets or input validation, and nothing in this design relies on it for them.

- **Execution goes through `ToolLoop.execute` and `run_call` only.** Graph nodes never call a tool function. Each allowed call still renews the job lease and re-checks the requester's active staff role, ticket visibility, version and archive state in its own transaction.
- **The budget is a server ledger, not graph state.** `used`, the trace, observations and evidence live in `ToolLoop`. Graph state holds only `round`, `last_round` and the pending `requested` calls, so no node update can reset the call count or insert evidence. `ToolLoop.execute` checks the budget on every call; when the graph's budget check was removed as an experiment, extra calls were still recorded as `budget_exceeded` and not executed, and the parity tests failed on the extra planner round.
- **Model output stays untrusted.** Requested calls are stored as returned and validated by the same allow-list and strict argument schemas. Unknown tools and invalid arguments are rejected, recorded and count against the budget in both implementations.
- **The baseline title search is still added by the server** outside the budget, and its passages stay first under the 20-passage cap.
- **No checkpointer is attached.** Job state never leaves the worker process. Lease recovery works exactly as before: a re-claimed job starts the loop again from the beginning.
- **No external tracing.** `langsmith` is installed transitively and exports runs when LangSmith or LangChain tracing variables are set. Ticket text and retrieved passages must not leave the deployment, so the graph refuses to run, and the worker refuses to start, while any of `LANGSMITH_TRACING`, `LANGSMITH_TRACING_V2`, `LANGCHAIN_TRACING` or `LANGCHAIN_TRACING_V2` is enabled.
- **Errors are not swallowed.** `ToolStopped` (lost lease, changed access) and provider errors such as `GenerationError` propagate out of `GRAPH.invoke` unchanged, so `execute_job` maps them to the same job outcomes.

## Equivalence checks

`backend/tests/test_agent_graph.py` runs both orchestrations against the same scripted planner and fake `run_call` and requires identical traces, executed calls, planner inputs, evidence order, context and errors. Scenarios cover normal history and search, the model running the baseline itself, an empty plan, the budget exceeded within one round and across rounds, the round limit, refused tools and arguments, rejection feedback followed by a corrected call, the evidence cap, a provider without a planner, a stopped call at two positions and a planner failure. Three deliberate graph defects (no budget check, an off-by-one round limit, a wrong last round) each made the parity tests fail.

`backend/tests/integration/test_agent_tools.py` now runs every PostgreSQL tool-loop case under both orchestrations through `execute_job`. These cases require `TEST_DATABASE_URL`; see the [evidence](evidence/2026-11-25-langgraph-tool-loop.md) for what has and has not been executed.

## Limits

The graph adds a dependency tree (`langchain-core`, `langsmith` and their packages) for structure, not capability. It does not use LangChain model wrappers, tool decorators or prebuilt agents: those would move tool execution and argument handling into the framework, which is exactly what the server must keep. No real model has been run through the LangGraph path.
