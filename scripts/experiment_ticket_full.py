"""Compare the real ticket-list query in an isolated synthetic migrated schema."""
import argparse
import json
import re
from statistics import median
import time

from sqlalchemy import select, text

from serve_frontend_check import browser_fixture
from supportops.models import Ticket
from supportops.seed import synthetic_id


def main():
    options = argparse.Namespace(read_delay_ms=0, extra_tickets=0, session_minutes=30,
                                 lose_first_write_response=False, write_delay_ms=0)
    with browser_fixture(options) as app:
        engine = app.state.engine
        with engine.begin() as connection:
            schema = connection.scalar(text('SELECT current_schema()'))
            if not re.fullmatch(r'test_s09_browser_[0-9a-f]{32}', schema):
                raise RuntimeError('Refusing to modify an unowned schema')
            connection.execute(text('''INSERT INTO tickets
                (id, requester_id, assignee_id, title, body, status, priority, version, archived, created_at, updated_at)
                SELECT md5('benchmark-' || n::text)::uuid, :requester,
                    CASE WHEN n % 20 = 7 THEN :agent ELSE NULL END,
                    'Synthetic ticket ' || n, 'Synthetic benchmark data',
                    CASE WHEN (n / 20) % 5 = 0 THEN 'open' ELSE 'closed' END,
                    'normal', 1, false, TIMESTAMPTZ '2025-01-01 00:00:00+00' + n * INTERVAL '1 second',
                    TIMESTAMPTZ '2025-01-01 00:00:00+00' + n * INTERVAL '1 second'
                FROM generate_series(1, 5000) n'''), {'requester': synthetic_id('requester-a'), 'agent': synthetic_id('agent-a')})
            connection.execute(text('ANALYZE tickets'))
            version = connection.scalar(text('SHOW server_version'))
            connection.execute(text(f'DROP INDEX "{schema}".ix_tickets_assignee_status'))
            statement = select(Ticket).where(Ticket.assignee_id == synthetic_id('agent-a'), Ticket.status == 'open').order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(21)
            sql = str(statement.compile(dialect=connection.dialect, compile_kwargs={'literal_binds': True}))
            def measure():
                plans = [connection.scalar(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql))[0] for _ in range(5)]
                rows = list(connection.execute(statement).scalars())
                return plans, rows
            def measure_writes():
                samples = []
                for _ in range(5):
                    savepoint = connection.begin_nested()
                    started = time.perf_counter()
                    connection.execute(text('''INSERT INTO tickets
                        (id, requester_id, assignee_id, title, body, status, priority, version, archived)
                        SELECT md5('write-' || n::text)::uuid, :requester, :agent,
                            'Synthetic write', 'Synthetic benchmark data', 'open', 'normal', 1, false
                        FROM generate_series(1, 1000) n'''),
                        {'requester': synthetic_id('requester-a'), 'agent': synthetic_id('agent-a')})
                    samples.append(round((time.perf_counter() - started) * 1000, 3))
                    savepoint.rollback()
                return samples
            before, before_ids = measure()
            before_writes = measure_writes()
            connection.execute(text(f'CREATE INDEX ix_tickets_assignee_status ON "{schema}".tickets (assignee_id, status, created_at, id)'))
            connection.execute(text('ANALYZE tickets'))
            after, after_ids = measure()
            after_writes = measure_writes()
            if before_ids != after_ids or len(before_ids) != 21:
                raise RuntimeError('Query pages differ')
            print(json.dumps({'postgresql': version, 'synthetic_inserted': 5000, 'query': sql,
                'page_rows': len(before_ids), 'runs_each': 5,
                'without_index_ms': [p['Execution Time'] for p in before],
                'with_index_ms': [p['Execution Time'] for p in after],
                'without_index_median_ms': median(p['Execution Time'] for p in before),
                'with_index_median_ms': median(p['Execution Time'] for p in after),
                'insert_1000_without_index_ms': before_writes,
                'insert_1000_with_index_ms': after_writes,
                'without_index_plan': before[-1]['Plan'], 'with_index_plan': after[-1]['Plan']}, indent=2))


if __name__ == '__main__':
    main()
