"""Evaluate synthetic retrieval cases in a disposable local database schema."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from serve_frontend_check import browser_fixture
from supportops import knowledge_service, retrieval
from supportops.embeddings import OllamaEmbedding
from supportops.knowledge_schemas import KnowledgeChange
from supportops.models import User
from supportops.retrieval_schemas import IndexCreate, SearchQuery
from supportops.seed import synthetic_id
from supportops.seed_knowledge import seed_knowledge

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'evals' / 'retrieval-cases-v1.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['dev', 'holdout'], required=True)
    parser.add_argument('--mode', choices=['keyword', 'vector'], required=True)
    args = parser.parse_args()
    raw = CASES.read_bytes()
    data = json.loads(raw)
    cases = [row for row in data['cases'] if row['split'] == args.split]
    if len(cases) != (20 if args.split == 'dev' else 10):
        raise SystemExit('Unexpected case count')
    options = argparse.Namespace(read_delay_ms=0, extra_tickets=0, session_minutes=30,
                                 lose_first_write_response=False, write_delay_ms=0)
    with browser_fixture(options) as app:
        provider = OllamaEmbedding()
        with Session(app.state.engine) as session, session.begin():
            drafts = seed_knowledge(session)
            manager = synthetic_id('manager')
            references = {}
            for article in drafts:
                article_id = UUID(article['id'])
                version_id = UUID(article['version']['id'])
                retrieval.build_index(session, manager, article_id,
                    IndexCreate(version_id=version_id, expected_revision=1, mode=args.mode), str(uuid4()), provider)
                knowledge_service.change_publication(session, manager, article_id,
                    KnowledgeChange(version_id=version_id, expected_revision=1), str(uuid4()))
                reference = article['version']['source_reference']
                references[reference.split('/')[-2]] = reference
            server_version = session.scalar(text('SHOW server_version'))
        results = []
        with Session(app.state.engine) as session:
            actor = session.get(User, synthetic_id('manager'))
            for case in cases:
                start = time.perf_counter()
                found = retrieval.search(session, actor, SearchQuery(q=case['query'], mode=args.mode, limit=5), provider)
                elapsed = (time.perf_counter() - start) * 1000
                expected = references[case['key']]
                results.append({'id': case['id'], 'hit': any(item.source_reference == expected for item in found.items),
                                'result_count': len(found.items), 'elapsed_ms': round(elapsed, 3)})
        durations = sorted(row['elapsed_ms'] for row in results)
        print(json.dumps({'dataset': data['version'], 'label_status': data['label_status'],
            'dataset_sha256': hashlib.sha256(raw).hexdigest(), 'split': args.split, 'mode': args.mode,
            'postgresql': server_version, 'model': provider.spec.model if args.mode == 'vector' else None,
            'model_digest': provider.spec.model_digest if args.mode == 'vector' else None,
            'cases': len(results), 'hits': sum(row['hit'] for row in results),
            'mean_ms': round(sum(durations) / len(durations), 3), 'results': results}, indent=2))


if __name__ == '__main__':
    main()
