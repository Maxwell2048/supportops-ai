import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supportops.idempotency import canonical_hash
from supportops.models import IdempotencyRecord, KnowledgeArticle, KnowledgeEvent, KnowledgeVersion, User
from supportops.seed import synthetic_id
from test_tickets import call, env

pytestmark = pytest.mark.integration
ROOT = "/api/knowledge"
CONTENT = {"title": "Synthetic access checklist", "body": "Check the synthetic account flag. Do not use real credentials.",
    "scope": "support", "source_kind": "synthetic", "source_reference": "supportops.synthetic/access-v1",
    "license_note": "Original synthetic project example; no external data."}


def create(env, **changes):
    response = call(env, "POST", ROOT + "/articles", payload={**CONTENT, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def change(env, article, action="publish", **changes):
    return call(env, "POST", f"{ROOT}/articles/{article['id']}/{action}", payload={"version_id": article["version"]["id"], "expected_revision": article["revision"], **changes})


def version_path(article):
    return ROOT + "/versions/" + article["version"]["id"]


def totals(env):
    return [env[1].scalar(select(func.count()).select_from(model)) for model in (KnowledgeArticle, KnowledgeVersion, KnowledgeEvent, IdempotencyRecord)]


def test_draft_snapshot_has_provenance_hash_actor_and_one_redacted_audit(env):
    payload = {**CONTENT, "title": "  Synthetic access checklist  "}
    response = call(env, "POST", ROOT + "/articles", payload=payload, key="first-draft")
    assert response.status_code == 201
    item = response.json()
    assert item["revision"] == item["version"]["number"] == 1
    assert item["version"]["content_hash"] == canonical_hash(CONTENT)
    assert item["version"]["created_by"] == str(synthetic_id("manager"))
    assert item["published_version_id"] is None and item["version"]["status"] == "draft"
    replay = call(env, "POST", ROOT + "/articles", payload=payload, key="first-draft")
    assert replay.status_code == 201 and replay.json() == item and totals(env) == [1, 1, 1, 1]
    history = call(env, "GET", f"{ROOT}/articles/{item['id']}/events").json()["items"]
    assert history[0]["request_id"] == response.headers["x-request-id"]
    assert history[0]["result"] == "success" and history[0]["action"] == "draft_created"
    assert CONTENT["body"] not in json.dumps(history) and CONTENT["title"] not in json.dumps(history)
    assert CONTENT["license_note"] not in json.dumps(history)
    assert call(env, "POST", ROOT + "/articles", payload={**CONTENT, "body": "Changed"}, key="first-draft").status_code == 409
    assert totals(env) == [1, 1, 1, 1]


@pytest.mark.parametrize("who", ["requester-a", "agent-a"])
@pytest.mark.parametrize("operation", ["create", "publish", "archive"])
def test_only_current_managers_can_write_and_replay(env, who, operation):
    article = create(env)
    path = ROOT + "/articles" if operation == "create" else f"{ROOT}/articles/{article['id']}/{operation}"
    payload = CONTENT if operation == "create" else {"version_id": article["version"]["id"], "expected_revision": 1}
    before = totals(env)
    assert call(env, "POST", path, who=who, payload=payload).status_code == 403
    assert totals(env) == before


@pytest.mark.parametrize("suffix", ["/articles", "/articles/{id}", "/versions/{id}", "/articles/{id}/versions", "/articles/{id}/events"])
def test_requesters_cannot_read_any_knowledge_surface(env, suffix):
    path = ROOT + suffix.format(id=uuid4())
    assert call(env, "GET", path, who="requester-a").status_code == 403


def test_missing_session_rejected(env):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=env[0]), base_url="http://test") as client:
            assert (await client.get(ROOT + "/articles")).status_code == 401
    asyncio.run(scenario())


def test_drafts_never_leak_or_displace_the_active_agent_publication(env):
    first = create(env)
    assert call(env, "GET", ROOT + "/articles", who="agent-a").json()["items"] == []
    assert call(env, "GET", version_path(first), who="agent-a").status_code == 404
    published = change(env, first).json()
    assert published["revision"] == 2 and published["version"]["status"] == "published"
    draft = create(env, article_id=first["id"], expected_revision=2, body="Unpublished management draft", scope="management")
    assert draft["revision"] == 3 and draft["version"]["number"] == 2
    current = call(env, "GET", ROOT + "/articles/" + first["id"], who="agent-a").json()
    assert "revision" not in current and current["version"] == published["version"]
    assert call(env, "GET", version_path(draft), who="agent-a").status_code == 404
    listed = call(env, "GET", ROOT + "/articles", who="agent-a").json()["items"]
    assert [row["version_id"] for row in listed] == [first["version"]["id"]]


def test_old_citations_are_immutable_but_subject_to_current_scope_and_archive(env):
    first = create(env)
    original = dict(first["version"])
    active = change(env, first).json()
    private = create(env, article_id=first["id"], expected_revision=active["revision"], scope="management", body="Management-only synthetic source")
    private = change(env, private).json()
    assert call(env, "GET", version_path(first), who="agent-a").status_code == 404
    assert call(env, "GET", version_path(private), who="agent-a").status_code == 404
    assert call(env, "GET", ROOT + "/articles", who="agent-a").json()["items"] == []
    support = create(env, article_id=first["id"], expected_revision=private["revision"], body="A newer support procedure")
    support = change(env, support).json()
    old = call(env, "GET", version_path(first), who="agent-a").json()
    assert old == {**original, "status": "archived"}
    assert call(env, "GET", version_path(private), who="agent-a").status_code == 404
    archived = change(env, support, "archive").json()
    assert archived["archived"] is True
    assert call(env, "GET", version_path(first), who="agent-a").status_code == 404
    assert call(env, "GET", version_path(support), who="agent-a").status_code == 404
    assert call(env, "GET", version_path(first)).json() == {**original, "status": "archived"}
    # Explicit publication can restore a historical immutable snapshot without copying content.
    restored = change(env, {**archived, "version": first["version"]}).json()
    assert restored["version"] == {**original, "status": "published"} and not restored["archived"]
    assert call(env, "GET", version_path(first), who="agent-a").json() == restored["version"]


def test_publish_archive_validation_and_stale_revision_leave_no_partial_state(env):
    first, other = create(env), create(env)
    assert change(env, first, version_id=other["version"]["id"]).status_code == 404
    assert change(env, first, "archive").status_code == 409
    assert change(env, first, expected_revision=20).status_code == 409
    active = change(env, first).json()
    assert change(env, active).status_code == 422
    assert change(env, active, "archive").status_code == 200
    assert change(env, {**active, "revision": 3}, "archive").status_code == 409
    assert totals(env)[:3] == [2, 2, 4]


@pytest.mark.parametrize("changes", [
    {"scope": "public"}, {"body": " "}, {"body": "bad\x00text"}, {"title": "x" * 201},
    {"body": "x" * 50001}, {"source_kind": "unknown"}, {"source_reference": ""},
    {"license_note": ""}, {"expected_revision": 1}, {"article_id": str(uuid4())},
    {"expected_revision": True, "article_id": str(uuid4())}, {"status": "published"}, {"created_by": str(uuid4())},
])
def test_input_constraints_and_forbidden_fields(env, changes):
    assert call(env, "POST", ROOT + "/articles", payload={**CONTENT, **changes}).status_code == 422
    assert totals(env) == [0, 0, 0, 0]


def test_missing_key_and_malformed_publish_input(env):
    assert call(env, "POST", ROOT + "/articles", payload=CONTENT, omit_key=True).status_code == 422
    article = create(env)
    for bad in ({"expected_revision": "1"}, {"expected_revision": True}, {"version_id": None}, {"scope": "management"}):
        assert change(env, article, **bad).status_code == 422


@pytest.mark.parametrize("table", ["knowledge_versions", "knowledge_events"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
def test_database_rejects_mutation_of_snapshot_and_audit_history(env, table, operation):
    article = create(env)
    statement = f"UPDATE {table} SET id = id" if operation == "UPDATE" else f"{operation} {'FROM ' if operation == 'DELETE' else ''}{table}"
    if operation == "TRUNCATE":
        # The isolated schema owns these tables. CASCADE reaches the trigger rather than stopping at FK preflight.
        statement += " CASCADE"
    with pytest.raises(IntegrityError) as failure, env[1].begin_nested():
        env[1].execute(text(statement))
    assert failure.value.orig.sqlstate == "23514"
    assert totals(env) == [1, 1, 1, 1]
    assert call(env, "GET", version_path(article)).json()["body"] == CONTENT["body"]


def test_database_rejects_a_cross_article_publication_pointer(env):
    first, second = create(env), create(env)
    with pytest.raises(IntegrityError), env[1].begin_nested():
        env[1].execute(update(KnowledgeArticle).where(KnowledgeArticle.id == UUID(first["id"])).values(published_version_id=UUID(second["version"]["id"])))


@pytest.mark.parametrize("operation", ["create", "publish", "archive"])
def test_audit_failure_rolls_back_all_knowledge_and_idempotency_changes(env, operation):
    article = create(env) if operation != "create" else None
    if operation == "archive":
        article = change(env, article).json()
    before = totals(env)
    def fail_audit(session, context, instances):
        for obj in session.new:
            if isinstance(obj, KnowledgeEvent):
                obj.result = "invalid-result"
    path = ROOT + "/articles" if operation == "create" else f"{ROOT}/articles/{article['id']}/{operation}"
    payload = CONTENT if operation == "create" else {"version_id": article["version"]["id"], "expected_revision": article["revision"]}
    event.listen(Session, "before_flush", fail_audit)
    try:
        failed = call(env, "POST", path, payload=payload, key="audit-rollback")
        assert failed.status_code == 503
    finally:
        event.remove(Session, "before_flush", fail_audit)
    assert totals(env) == before
    if article:
        current = call(env, "GET", ROOT + "/articles/" + article["id"]).json()
        assert current["revision"] == article["revision"] and current["archived"] == article["archived"]
    assert call(env, "POST", path, payload=payload, key="audit-rollback").status_code == (201 if operation == "create" else 200)


def test_current_manager_role_and_active_state_precede_cached_replay(env):
    assert call(env, "POST", ROOT + "/articles", payload=CONTENT, key="role-check").status_code == 201
    env[1].execute(update(User).where(User.id == synthetic_id("manager")).values(role="agent"))
    assert call(env, "POST", ROOT + "/articles", payload=CONTENT, key="role-check").status_code == 403
    env[1].execute(update(User).where(User.id == synthetic_id("manager")).values(active=False))
    assert call(env, "POST", ROOT + "/articles", payload=CONTENT, key="role-check").status_code == 401
    assert totals(env) == [1, 1, 1, 1]


def test_pagination_uses_current_scope_and_binds_cursor_identity_limit_and_article(env):
    articles = [create(env, title=f"Synthetic article {number}", scope="support" if number < 3 else "management") for number in range(4)]
    for article in articles:
        assert change(env, article).status_code == 200
    first = call(env, "GET", ROOT + "/articles", who="agent-a", params={"limit": 2}).json()
    second = call(env, "GET", ROOT + "/articles", who="agent-a", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1 and second["next_cursor"] is None
    assert len({item["article_id"] for item in first["items"] + second["items"]}) == 3
    for who, limit in (("agent-b", 2), ("agent-a", 1), ("manager", 2)):
        assert call(env, "GET", ROOT + "/articles", who=who, params={"limit": limit, "cursor": first["next_cursor"]}).status_code == 422
    article = articles[0]
    history = call(env, "GET", f"{ROOT}/articles/{article['id']}/events", params={"limit": 1}).json()
    assert history["items"][0]["article_revision"] == 1
    next_page = call(env, "GET", f"{ROOT}/articles/{article['id']}/events", params={"limit": 1, "cursor": history["next_cursor"]}).json()
    assert next_page["items"][0]["article_revision"] == 2 and next_page["next_cursor"] is None
    assert call(env, "GET", f"{ROOT}/articles/{articles[1]['id']}/events", params={"limit": 1, "cursor": history["next_cursor"]}).status_code == 422
    assert call(env, "GET", f"{ROOT}/articles/{article['id']}/events", who="agent-a").status_code == 403
    assert call(env, "GET", f"{ROOT}/articles/{article['id']}/versions", who="agent-a").status_code == 403
    assert call(env, "GET", ROOT + "/articles", params={"cursor": "tampered"}).status_code == 422


def test_bundled_synthetic_import_is_draft_first_repeatable_and_does_not_unarchive(env):
    from supportops.seed_knowledge import seed_knowledge
    with Session(bind=env[1], join_transaction_mode="create_savepoint") as session:
        first = seed_knowledge(session)
        session.commit()
    assert len(first) == 4 and totals(env) == [4, 4, 4, 4]
    assert call(env, "GET", ROOT + "/articles", who="agent-a").json()["items"] == []
    with Session(bind=env[1], join_transaction_mode="create_savepoint") as session:
        published = seed_knowledge(session, publish=True)
        session.commit()
    assert len(call(env, "GET", ROOT + "/articles", who="agent-a").json()["items"]) == 3
    assert change(env, published[0], "archive").status_code == 200
    before = totals(env)
    with Session(bind=env[1], join_transaction_mode="create_savepoint") as session:
        seed_knowledge(session, publish=True)
        session.commit()
    assert totals(env) == before
    assert call(env, "GET", version_path(first[0]), who="agent-a").status_code == 404


def test_manager_version_history_is_paged_without_changing_snapshot_numbers(env):
    first = create(env)
    published = change(env, first).json()
    second = create(env, article_id=first["id"], expected_revision=2, body="Synthetic second draft")
    third = create(env, article_id=first["id"], expected_revision=3, body="Synthetic third draft")
    path = f"{ROOT}/articles/{first['id']}/versions"
    rows, cursor = [], None
    for _ in range(3):
        page = call(env, "GET", path, params={"limit": 1, **({"cursor": cursor} if cursor else {})}).json()
        rows.extend(page["items"])
        cursor = page["next_cursor"]
    assert cursor is None and {row["number"] for row in rows} == {1, 2, 3}
    assert {row["version_id"]: row["status"] for row in rows} == {
        first["version"]["id"]: "published", second["version"]["id"]: "draft", third["version"]["id"]: "draft"}
    current = call(env, "GET", ROOT + "/articles/" + first["id"]).json()
    assert current["revision"] == 4 and current["version"]["number"] == 3
    assert current["published_version_id"] == published["version"]["id"]
