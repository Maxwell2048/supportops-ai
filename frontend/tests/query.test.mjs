import assert from "node:assert/strict";
import test from "node:test";
import { QueryObserver, timeoutManager } from "@tanstack/react-query";
import { ApiError, createApi } from "../src/api/client.ts";
import {
  createSessionClient,
  detailOptions,
  invalidateTickets,
  listOptions,
  queryView,
  ticketRoot,
} from "../src/state/queries.ts";
import {
  emptyFilters,
  filterKey,
  listHref,
  normalizeFilters,
  routeFromHash,
} from "../src/state/ticketState.ts";

// Query GC timers must not keep a headless Node test process alive after assertions.
timeoutManager.setTimeoutProvider({
  setTimeout: (callback, delay) => {
    const timer = setTimeout(callback, delay);
    timer.unref();
    return timer;
  },
  clearTimeout: (timer) => clearTimeout(timer),
  setInterval: (callback, delay) => {
    const timer = setInterval(callback, delay);
    timer.unref();
    return timer;
  },
  clearInterval: (timer) => clearInterval(timer),
});

const session = {
  key: "synthetic-login-1",
  token: "synthetic-bearer-not-for-keys",
  user: { id: "11111111-1111-4111-8111-111111111111", role: "manager" },
};
const id = "22222222-2222-4222-8222-222222222222";
test("write 401 expires the session without retrying or queuing offline mutations", async (t) => {
  let expired = 0,
    calls = 0;
  const client = clientFor(t, () => {
    expired++;
  });
  const mutation = client.getMutationCache().build(client, {
    mutationFn: async () => {
      calls++;
      throw new ApiError(401, "invalid_session", "Session expired");
    },
  });
  await assert.rejects(mutation.execute(undefined));
  assert.equal(expired, 1);
  assert.equal(calls, 1);
  assert.equal(client.getDefaultOptions().mutations.networkMode, "always");
  assert.equal(client.getDefaultOptions().mutations.retry, false);
});
function clientFor(t, onExpired) {
  const client = createSessionClient(onExpired);
  t.after(() => client.clear());
  return client;
}

test("query keys bind login, identity, role, resource, filters and cursor without tokens", () => {
  const base = listOptions(session, emptyFilters, null).queryKey;
  for (const changed of [
    { ...session, key: "another-login" },
    { ...session, user: { ...session.user, id } },
    { ...session, user: { ...session.user, role: "requester" } },
  ])
    assert.notDeepEqual(
      base,
      listOptions(changed, emptyFilters, null).queryKey,
    );
  assert.notDeepEqual(
    base,
    listOptions(session, { ...emptyFilters, q: "new query" }, null).queryKey,
  );
  assert.notDeepEqual(
    base,
    listOptions(session, emptyFilters, "next-page").queryKey,
  );
  assert.notDeepEqual(base, detailOptions(session, id).queryKey);
  assert.equal(JSON.stringify(base).includes(session.token), false);
  assert.deepEqual(
    base,
    listOptions(session, { ...emptyFilters, q: "   " }, null).queryKey,
  );
});

test("fresh identical fetches deduplicate, while filter changes use independent data", async (t) => {
  const client = clientFor(t);
  let calls = 0;
  const options = {
    ...listOptions(session, emptyFilters, null),
    queryFn: async () => {
      calls++;
      return "first-page";
    },
  };
  assert.deepEqual(
    await Promise.all([client.fetchQuery(options), client.fetchQuery(options)]),
    ["first-page", "first-page"],
  );
  await client.fetchQuery(options);
  assert.equal(calls, 1);
  await client.fetchQuery({
    ...listOptions(session, { ...emptyFilters, q: "another" }, null),
    queryFn: async () => {
      calls++;
      return "filtered";
    },
  });
  assert.equal(calls, 2);
  assert.equal(client.getQueryData(options.queryKey), "first-page");
});

test("new sessions have no old cache and clear aborts late responses", async (t) => {
  const old = clientFor(t),
    next = clientFor(t);
  let finish, signal;
  const key = detailOptions(session, id).queryKey;
  old.setQueryData(listOptions(session, emptyFilters, null).queryKey, {
    private: true,
  });
  const pending = old
    .fetchQuery({
      queryKey: key,
      queryFn: (context) => {
        signal = context.signal;
        return new Promise((resolve) => {
          finish = resolve;
        });
      },
    })
    .catch((error) => error);
  old.clear();
  assert.equal(signal.aborted, true);
  finish("late private result");
  await pending;
  assert.equal(old.getQueryCache().getAll().length, 0);
  assert.equal(next.getQueryCache().getAll().length, 0);
});

test("mount revalidates fresh cached content and hides it until a successful reply", async (t) => {
  const client = clientFor(t);
  const options = detailOptions(session, id);
  client.setQueryData(options.queryKey, "previously-authorized");
  let finish;
  const observer = new QueryObserver(client, {
    ...options,
    queryFn: ({ signal }) => {
      void signal;
      return new Promise((resolve) => {
        finish = resolve;
      });
    },
  });
  let complete;
  const done = new Promise((resolve) => {
    complete = resolve;
  });
  const unsubscribe = observer.subscribe((result) => {
    if (result.isSuccess && !result.isFetching) complete();
  });
  assert.equal(queryView(observer.getCurrentResult()).status, "loading");
  finish("freshly-authorized");
  await done;
  assert.deepEqual(queryView(observer.getCurrentResult()), {
    status: "success",
    data: "freshly-authorized",
  });
  unsubscribe();
});

test("failed revalidation does not display previously cached data", async (t) => {
  const client = clientFor(t),
    options = detailOptions(session, id);
  client.setQueryData(options.queryKey, "old private details");
  await assert.rejects(
    client.fetchQuery({
      ...options,
      staleTime: 0,
      queryFn: async () => {
        throw new ApiError(404, "not_found", "Unavailable");
      },
    }),
  );
  const cached = client.getQueryState(options.queryKey);
  assert.equal(cached.data, "old private details");
  assert.equal(
    queryView({
      isPending: false,
      isFetching: false,
      isError: true,
      error: cached.error,
      data: cached.data,
    }).status,
    "error",
  );
});

test("refresh invalidates all ticket lists/details for one session only", async (t) => {
  const client = clientFor(t);
  const keys = [
    listOptions(session, emptyFilters, null).queryKey,
    listOptions(session, { ...emptyFilters, priority: "high" }, "cursor")
      .queryKey,
    detailOptions(session, id).queryKey,
  ];
  const otherKey = detailOptions(
    { ...session, key: "another-login" },
    id,
  ).queryKey;
  for (const key of [...keys, otherKey]) client.setQueryData(key, "cached");
  await invalidateTickets(client, session);
  for (const key of keys)
    assert.equal(client.getQueryState(key).isInvalidated, true);
  assert.equal(client.getQueryState(otherKey).isInvalidated, false);
});

test("401 expires the session once without automatic retries", async (t) => {
  let expired = 0,
    calls = 0,
    client;
  client = clientFor(t, () => {
    expired++;
    client.clear();
  });
  await assert.rejects(
    client.fetchQuery({
      queryKey: ticketRoot(session),
      queryFn: async () => {
        calls++;
        throw new ApiError(401, "invalid_session", "Expired");
      },
    }),
  );
  assert.equal(calls, 1);
  assert.equal(expired, 1);
  assert.equal(client.getQueryCache().getAll().length, 0);
});

test("query defaults bound memory lifetime and revalidate on focus/reconnect/mount", (t) => {
  const options = clientFor(t).getDefaultOptions().queries;
  assert.equal(options.gcTime, 120000);
  assert.equal(options.staleTime, 15000);
  assert.equal(options.refetchOnWindowFocus, "always");
  assert.equal(options.refetchOnReconnect, "always");
  assert.equal(options.refetchOnMount, "always");
  assert.equal(options.networkMode, "always");
  assert.equal(options.retry, false);
});

test("filter URLs roundtrip reserved characters, normalize whitespace and exclude credentials", () => {
  const filters = normalizeFilters({
    q: "  literal %_ &? phrase  ",
    status: "open",
    priority: "high",
  });
  assert.deepEqual(routeFromHash(listHref(filters)), { kind: "list", filters });
  assert.equal(
    filterKey(filters),
    filterKey({ ...filters, q: " " + filters.q + " " }),
  );
  assert.equal(listHref(emptyFilters), "#/tickets");
  assert.equal(routeFromHash("#/tickets?priority=unknown").kind, "missing");
  assert.equal(routeFromHash("#/tickets?token=secret").kind, "missing");
  assert.throws(() => normalizeFilters({ q: "x".repeat(201) }));
});

test("filters reach the API as separate encoded parameters", async () => {
  const api = createApi(async (url) => {
    const params = new URL(url, "http://localhost").searchParams;
    assert.equal(params.get("q"), "literal &? %_");
    assert.equal(params.get("status"), "closed");
    assert.equal(params.get("priority"), "high");
    assert.equal(params.size, 4);
    return new Response(JSON.stringify({ items: [], next_cursor: null }), {
      headers: { "Content-Type": "application/json" },
    });
  });
  await api.tickets("synthetic-token", null, undefined, {
    q: " literal &? %_ ",
    status: "closed",
    priority: "high",
  });
});
