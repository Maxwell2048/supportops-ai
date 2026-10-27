import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from supportops.knowledge_schemas import KnowledgeCreate
from supportops.knowledge_service import create_draft
from supportops.models import IdempotencyRecord, KnowledgeArticle, KnowledgeEvent, KnowledgeVersion
from test_knowledge import CONTENT, ROOT
from test_ticket_concurrency import committed, headers

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("same_body", [True, False])
def test_independent_connections_deduplicate_knowledge_creation(committed, same_body):
    app, engine, users, _ = committed
    key = str(uuid4())
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[
                client.post(ROOT + "/articles", headers=headers(committed, "manager", key),
                    json={**CONTENT, "body": CONTENT["body"] if same_body else f"Synthetic content {number}"}) for number in range(2)
            ])
            assert sorted(response.status_code for response in responses) == ([201, 201] if same_body else [201, 409])
            if same_body:
                assert responses[0].json() == responses[1].json()
    asyncio.run(scenario())
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(KnowledgeArticle).where(KnowledgeArticle.created_by == users["manager"])) == 1
        assert session.scalar(select(func.count()).select_from(KnowledgeEvent).where(KnowledgeEvent.actor_id == users["manager"])) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.actor_id == users["manager"], IdempotencyRecord.operation == "knowledge_draft")) == 1


@pytest.mark.parametrize("operation", ["draft", "publish"])
def test_same_revision_allows_only_one_concurrent_draft_or_publication(committed, operation):
    app, engine, users, _ = committed
    with Session(engine) as session, session.begin():
        first = create_draft(session, users["manager"], KnowledgeCreate(**CONTENT), str(uuid4())).body
        second = create_draft(session, users["manager"], KnowledgeCreate(**CONTENT, article_id=UUID(first["id"]), expected_revision=1), str(uuid4())).body
    article_id = UUID(first["id"])
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            payloads = [{**CONTENT, "article_id": first["id"], "expected_revision": 2, "body": f"Concurrent synthetic draft {number}"} for number in range(2)] if operation == "draft" else [
                {"version_id": row["version"]["id"], "expected_revision": 2} for row in (first, second)]
            path = ROOT + "/articles" if operation == "draft" else f"{ROOT}/articles/{article_id}/publish"
            responses = await asyncio.gather(*[client.post(path, headers=headers(committed, "manager", str(uuid4())), json=payload) for payload in payloads])
            assert sorted(response.status_code for response in responses) == ([201, 409] if operation == "draft" else [200, 409])
            winner = next(response.json() for response in responses if response.status_code in (200, 201))
            with Session(engine) as session:
                article = session.get(KnowledgeArticle, article_id)
                assert article.revision == 3
                assert session.scalar(select(func.count()).select_from(KnowledgeEvent).where(KnowledgeEvent.article_id == article_id)) == 3
                if operation == "publish":
                    assert str(article.published_version_id) == winner["version"]["id"]
                    assert session.scalar(select(func.count()).select_from(KnowledgeVersion).where(KnowledgeVersion.article_id == article_id)) == 2
                else:
                    assert article.latest_version_number == 3 and article.published_version_id is None
    asyncio.run(scenario())
