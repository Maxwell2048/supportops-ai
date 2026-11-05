"""Materialize current synthetic-demo publications without publishing any drafts.

Run from backend: uv run --locked python ../scripts/index_knowledge.py --mode keyword
Vector mode requires the pinned local Ollama model. Derived writes use the active demo manager.
"""
import argparse
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'/'src'))

from sqlalchemy.orm import Session
from supportops.config import load_settings
from supportops.db import make_engine,check_readiness
from supportops.embeddings import OllamaEmbedding
from supportops.knowledge_service import active_versions,_manager
from supportops.retrieval import build_index
from supportops.retrieval_schemas import IndexCreate
from supportops.seed import synthetic_id


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['keyword','vector'],default='keyword')
    args=parser.parse_args()
    settings=load_settings()
    if not settings.database_url:raise SystemExit('Configure the database first')
    engine=make_engine(settings.database_url)
    try:
        if check_readiness(engine)!=(True,'database_ready'):raise SystemExit('Migrate the database before indexing')
        with Session(engine) as session,session.begin():
            actor=_manager(session,synthetic_id('manager'))
            rows=session.execute(active_versions(actor)).all()
            provider=OllamaEmbedding(settings.embedding_url)
            for article,version in rows:
                build_index(session,actor.id,article.id,IndexCreate(version_id=version.id,expected_revision=article.revision,mode=args.mode),str(uuid4()),provider)
        print(f'Processed {len(rows)} current publications in {args.mode} mode; no draft was published.')
    finally:engine.dispose()


if __name__=='__main__':main()
