"""Exercise a running local Compose stack using only synthetic accounts and data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from uuid import uuid4

from compose_backup import backup, database_container, restore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    password = os.getenv('DEMO_PASSWORD')
    if not password or not 12 <= len(password) <= 128:
        raise SystemExit('A synthetic DEMO_PASSWORD is required in the environment')
    db = database_container(args.project)
    result = subprocess.run(['docker', 'ps', '--filter', f'label=com.docker.compose.project={args.project}',
                             '--filter', 'label=com.docker.compose.service=api', '--format', '{{.ID}}'],
                            check=True, capture_output=True, text=True)
    api = result.stdout.splitlines()
    if len(api) != 1:
        raise SystemExit('Exactly one running API container is required')
    subprocess.run(['docker', 'exec', '-e', 'DEMO_PASSWORD', api[0], 'python', '-m', 'supportops.compose_demo'], check=True)
    base = f'http://127.0.0.1:{args.port}'

    def call(path, body=None, token=None, key=None):
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if key:
            headers['Idempotency-Key'] = key
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=10) as response:
            return json.load(response)

    if call('/ready')['status'] != 'ready':
        raise RuntimeError('Stack is not ready')
    requester = call('/api/auth/login', {'email': 'requester-a@example.invalid', 'password': password})['access_token']
    manager = call('/api/auth/login', {'email': 'manager@example.invalid', 'password': password})['access_token']
    ticket = call('/api/tickets', {'title': 'Isolated container request', 'body': 'Synthetic stack validation.'}, requester, str(uuid4()))
    job = call('/api/tickets/' + ticket['id'] + '/analysis-jobs', {'expected_version': ticket['version']}, manager, str(uuid4()))
    for _ in range(30):
        state = call('/api/analysis-jobs/' + job['job_id'], token=manager)
        if state['status'] in {'succeeded', 'failed'}:
            break
        time.sleep(1)
    if state['status'] != 'succeeded':
        raise RuntimeError('Mock worker did not complete the synthetic job')
    suggestion = call('/api/analysis-jobs/' + job['job_id'] + '/suggestion', token=manager)
    if suggestion['suggestion']['citations']:
        raise RuntimeError('Expected a no-evidence handoff in an empty synthetic stack')
    decision = call('/api/suggestions/' + job['job_id'] + '/review', {'expected_version': ticket['version'], 'decision': 'rejected'}, manager, str(uuid4()))
    if decision['message_id'] is not None:
        raise RuntimeError('Rejected handoff created a public reply')
    with urllib.request.urlopen(base + '/', timeout=10) as response:
        if '<div id="root">' not in response.read().decode():
            raise RuntimeError('Frontend shell unavailable')
    directory = Path(__file__).resolve().parents[1] / 'tmp'
    directory.mkdir(exist_ok=True)
    archive = directory / ('compose-check-' + uuid4().hex + '.dump')
    target = 'restore_' + uuid4().hex[:16]
    try:
        backup(db, archive)
        restore(db, archive, target)
        tables = ['users', 'tickets', 'ticket_messages', 'ticket_events', 'idempotency_records', 'audit_events',
                  'knowledge_articles', 'knowledge_versions', 'knowledge_events', 'knowledge_chunks', 'embedding_profiles',
                  'knowledge_embeddings', 'knowledge_indexes', 'analysis_jobs', 'mcp_tool_calls', 'alembic_version']
        for table in tables:
            sql = f"SELECT count(*)::text || ':' || md5(coalesce(string_agg(row_to_json(t)::text, '|' ORDER BY row_to_json(t)::text),'')) FROM public.{table} t"
            original = subprocess.check_output(['docker', 'exec', db, 'sh', '-c', 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$1"', 'sh', sql], text=True).strip()
            recovered = subprocess.check_output(['docker', 'exec', db, 'sh', '-c', 'exec psql -U "$POSTGRES_USER" -d "$1" -At -c "$2"', 'sh', target, sql], text=True).strip()
            if original != recovered:
                raise RuntimeError(f'Restored table differs: {table}')
        print(f'Synthetic stack and restore verified; {len(tables)} table fingerprints match.')
    finally:
        archive.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
