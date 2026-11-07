import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from supportops import knowledge_service, retrieval
from supportops.generation import GenerationError, GenerationFailure, MockGeneration, Suggestion
from supportops.jobs import claim_job, execute_job
from supportops.knowledge_schemas import KnowledgeChange, KnowledgeCreate
from supportops.models import AnalysisJob, KnowledgeArticle
from supportops.retrieval_schemas import IndexCreate
from supportops.seed import synthetic_id
from test_jobs import prepared

pytestmark = pytest.mark.integration


def setup_source(engine, *, publish=True, index=True, scope="support", body="Synthetic source: check the account status."):
    manager = synthetic_id("manager")
    with Session(engine) as session, session.begin():
        receipt = knowledge_service.create_draft(session, manager, KnowledgeCreate(
            title="Cannot sign in to the sample product", body=body,
            scope=scope, source_kind="synthetic", source_reference="synthetic", license_note="synthetic"), str(uuid4()))
        article_id = UUID(receipt.body["id"])
        version_id = UUID(receipt.body["version"]["id"])
        if index:
            retrieval.build_index(session, manager, article_id, IndexCreate(version_id=version_id, expected_revision=1), str(uuid4()), None)
        if publish:
            knowledge_service.change_publication(session, manager, article_id, KnowledgeChange(version_id=version_id, expected_revision=1), str(uuid4()))
    return article_id


def enqueue(engine):
    with Session(engine) as session, session.begin():
        job = AnalysisJob(id=uuid4(), ticket_id=synthetic_id("ticket-1"), requester_id=synthetic_id("agent-a"), ticket_version=1)
        session.add(job)
        job_id = job.id
    with Session(engine) as session, session.begin():
        claim = claim_job(session)
    assert claim[0] == job_id
    return claim


def result(engine, job_id):
    with Session(engine) as session:
        job = session.get(AnalysisJob, job_id)
        return job.status, job.error_code, job.result


def test_no_evidence_handoff_does_not_call_model(prepared):
    class Never:
        def generate(self, ticket, evidence):
            raise AssertionError("No model call expected")
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Never())
    status, error, body = result(prepared, claim[0])
    assert status == "succeeded" and error is None and body["citations"] == []
    assert "No relevant" in body["human_verification"][0]


def test_valid_real_chunk_and_contiguous_quote(prepared):
    setup_source(prepared)
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, MockGeneration())
    status, error, body = result(prepared, claim[0])
    assert status == "succeeded" and error is None
    assert body["citations"][0]["quote"] == "Synthetic source: check the account status."


@pytest.mark.parametrize("bad", ["empty", "wrong_quote", "wrong_chunk", "wrong_version"])
def test_invalid_citations_fail_job(prepared, bad):
    setup_source(prepared)
    class Invalid:
        def generate(self, ticket, evidence):
            source = json.loads(evidence[0])
            citation = {"chunk_id": source["chunk_id"], "version_id": source["version_id"], "quote": source["text"]}
            if bad == "wrong_quote": citation["quote"] = "invented text"
            if bad == "wrong_chunk": citation["chunk_id"] = str(uuid4())
            if bad == "wrong_version": citation["version_id"] = str(uuid4())
            return Suggestion(category="other", suggested_priority="normal", reply_draft="Draft", citations=[] if bad == "empty" else [citation], human_verification=[])
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Invalid())
    assert result(prepared, claim[0]) == ("failed", "invalid_citation", None)


def test_unindexed_publication_is_failure_not_no_evidence(prepared):
    setup_source(prepared, index=False)
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, MockGeneration())
    assert result(prepared, claim[0]) == ("failed", "retrieval_or_access_unavailable", None)


def test_archive_during_generation_rejects_result(prepared):
    article_id = setup_source(prepared)
    class Archive(MockGeneration):
        def generate(self, ticket, evidence):
            response = super().generate(ticket, evidence)
            with Session(prepared) as session, session.begin():
                article = session.get(KnowledgeArticle, article_id)
                knowledge_service.change_publication(session, synthetic_id("manager"), article_id,
                    KnowledgeChange(version_id=article.published_version_id, expected_revision=article.revision), str(uuid4()), archive=True)
            return response
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Archive())
    assert result(prepared, claim[0]) == ("failed", "access_or_ticket_changed", None)


def test_provider_failure_is_not_no_evidence(prepared):
    setup_source(prepared)
    class Unavailable:
        def generate(self, ticket, evidence):
            raise GenerationError(GenerationFailure.INVALID_OUTPUT)
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Unavailable())
    assert result(prepared, claim[0]) == ("failed", "invalid_output", None)


def test_management_source_is_not_given_to_agent(prepared):
    setup_source(prepared, scope="management")
    class Never:
        def generate(self, ticket, evidence):
            raise AssertionError("Restricted source reached provider")
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Never())
    status, _, body = result(prepared, claim[0])
    assert status == "succeeded" and body["citations"] == []


def test_malformed_provider_output_fails_safely(prepared):
    setup_source(prepared)
    class Malformed:
        def generate(self, ticket, evidence):
            return {"unexpected": "content"}
    claim = enqueue(prepared)
    assert execute_job(prepared, *claim, Malformed())
    assert result(prepared, claim[0]) == ("failed", "invalid_output", None)
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, update
from supportops.models import Ticket, User
from supportops.seed import seed

@pytest.fixture
def prepared(pg_engine):
    schema = "test_citation_" + uuid4().hex
    with pg_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(pg_engine.url, hide_parameters=True, connect_args={"connect_timeout": 3, "options": f"-csearch_path={schema},public"})
    try:
        with engine.begin() as connection:
            config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(engine) as session, session.begin():
            seed(session)
            session.execute(update(User).values(active=True))
            session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(assignee_id=synthetic_id("agent-a")))
        yield engine
    finally:
        engine.dispose()
        with pg_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
