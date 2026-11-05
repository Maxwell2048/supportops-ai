"""Exercise real local embeddings and persistent pgvector in an owned disposable schema.

Run from backend: uv run --locked python ../scripts/check_retrieval.py
Requires the official pinned all-minilm:22m model in local Ollama. Does not publish development drafts.
"""
import argparse
import json
import logging
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from serve_frontend_check import browser_fixture
from supportops.embeddings import OllamaEmbedding
from supportops.knowledge_schemas import KnowledgeChange
from supportops.knowledge_service import change_publication
from supportops.models import KnowledgeChunk, KnowledgeEmbedding, User
from supportops.retrieval import build_index, search
from supportops.retrieval_schemas import IndexCreate, SearchQuery
from supportops.seed import synthetic_id
from supportops.seed_knowledge import seed_knowledge


def main():
    options=argparse.Namespace(read_delay_ms=0,extra_tickets=0,session_minutes=1,lose_first_write_response=False,write_delay_ms=0)
    with browser_fixture(options) as app:
        provider=OllamaEmbedding(app.state.settings.embedding_url)
        engine=app.state.engine
        with Session(engine) as session,session.begin():
            articles=seed_knowledge(session,publish=True)
            for article in articles:
                payload=IndexCreate(version_id=article['version']['id'],expected_revision=article['revision'],mode='vector')
                first=build_index(session,synthetic_id('manager'),UUID(article['id']),payload,str(uuid4()),provider)
                second=build_index(session,synthetic_id('manager'),UUID(article['id']),payload,str(uuid4()),provider)
                assert first.body==second.body
        # Close pooled connections before proving records are read back from PostgreSQL.
        engine.dispose()
        with Session(engine) as session:
            actor=session.get(User,synthetic_id('agent-a'))
            samples=[]
            for query in ('account access','collect diagnostic context','verify a resolution'):
                for mode in ('keyword','vector'):
                    result=search(session,actor,SearchQuery(q=query,mode=mode,limit=3),provider)
                    assert result.available_versions==result.indexed_versions==3
                    assert all(hit.version_id in {UUID(row['version']['id']) for row in articles if row['version']['scope']=='support'} for hit in result.items)
                    samples.append({'query':query,'mode':mode,'top_titles':[item.title for item in result.items]})
            assert session.scalar(select(func.count()).select_from(KnowledgeEmbedding))>0
            vector_count=session.scalar(select(func.count()).select_from(KnowledgeEmbedding))
            chunk_count=session.scalar(select(func.count()).select_from(KnowledgeChunk))
            extension=session.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        with Session(engine) as session,session.begin():
            last=articles[0]
            change_publication(session,synthetic_id('manager'),UUID(last['id']),KnowledgeChange(version_id=last['version']['id'],expected_revision=last['revision']),str(uuid4()),archive=True)
        with Session(engine) as session:
            actor=session.get(User,synthetic_id('agent-a'))
            result=search(session,actor,SearchQuery(q='account access',mode='vector',limit=20),provider)
            assert result.available_versions==result.indexed_versions==2
            assert all(str(hit.version_id)!=articles[0]['version']['id'] for hit in result.items)
        print(json.dumps({'provider':provider.spec.provider,'model':provider.spec.model,'digest':provider.spec.model_digest,
            'profile_id':str(provider.spec.id),'dimensions':provider.spec.dimensions,'pgvector':extension,'persisted_chunks':chunk_count,
            'persisted_vectors':vector_count,'connection_reopen':'passed','archive_exclusion':'passed','examples':samples}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
