"""Verify a pinned local model with a disposable synthetic worker and database.

Run from backend with the local Ollama server active:
uv run --locked python ../scripts/check_local_worker.py --model NAME --digest FULL_SHA256
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from serve_frontend_check import browser_fixture
from supportops import knowledge_service, retrieval
from supportops.jobs import JobCreate, create_job
from supportops.knowledge_schemas import KnowledgeChange, KnowledgeCreate
from supportops.models import AnalysisJob, Ticket
from supportops.retrieval_schemas import IndexCreate
from supportops.seed import synthetic_id

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--digest', required=True)
    args = parser.parse_args()
    options = argparse.Namespace(read_delay_ms=0, extra_tickets=0, session_minutes=30,
                                 lose_first_write_response=False, write_delay_ms=0)
    with browser_fixture(options) as app:
        engine = app.state.engine
        with Session(engine) as session, session.begin():
            schema = session.scalar(text('SELECT current_schema()'))
            ticket = session.get(Ticket, synthetic_id('ticket-1'))
            manager = synthetic_id('manager')
            article = knowledge_service.create_draft(session, manager, KnowledgeCreate(
                title=ticket.title, body='Synthetic guidance: verify the sample account before changing access.',
                scope='support', source_kind='synthetic', source_reference='synthetic/local-worker',
                license_note='Original synthetic data'), str(uuid4()))
            article_id, version_id = UUID(article.body['id']), UUID(article.body['version']['id'])
            retrieval.build_index(session, manager, article_id, IndexCreate(version_id=version_id, expected_revision=1), str(uuid4()), None)
            knowledge_service.change_publication(session, manager, article_id, KnowledgeChange(version_id=version_id, expected_revision=1), str(uuid4()))
            job = create_job(session, manager, ticket.id, JobCreate(expected_version=ticket.version), str(uuid4()))
            job_id = UUID(job.body['job_id'])
        environment = os.environ.copy()
        environment['DATABASE_URL'] = engine.url.render_as_string(hide_password=False)
        environment['PYTHONPATH'] = str(ROOT / 'backend' / 'src')
        environment['SUPPORTOPS_TEST_SCHEMA'] = schema
        code = ("import os, sqlalchemy; import supportops.job_worker as worker; "
                "worker.make_engine = lambda url: sqlalchemy.create_engine(url, hide_parameters=True, "
                "connect_args={'options': '-csearch_path=' + os.environ['SUPPORTOPS_TEST_SCHEMA'] + ',public'}); worker.main()")
        run = subprocess.run([sys.executable, '-c', code, '--once', '--model', args.model, '--digest', args.digest],
                             env=environment, capture_output=True, text=True, timeout=600)
        if run.returncode:
            raise SystemExit('Worker process failed; inspect local configuration')
        with Session(engine) as session:
            job = session.get(AnalysisJob, job_id)
            print('Job status:', job.status, 'error:', job.error_code)
            for call in job.tool_trace or []:
                print('Tool call: round', call['round'], call['planner'], call['tool'], call['status'],
                      'results', call['result_count'], call.get('reason') or '', call.get('errors') or '',
                      call.get('arguments') or '')
            if (job.generation_provider, job.generation_model, job.generation_digest) != ('ollama', args.model, args.digest):
                raise SystemExit('Pinned model provenance was not recorded')
            print('Pinned model provenance recorded')
            if job.status != 'succeeded' or not job.result or not job.result.get('citations'):
                raise SystemExit('No validated cited result was produced')
            print('Validated citations:', len(job.result['citations']))
            print('Category:', job.result['category'], 'priority:', job.result['suggested_priority'])
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
