"""Serve the real API with disposable synthetic PostgreSQL fixtures for manual UI checks.

Run from backend: uv run --locked python ../scripts/serve_frontend_check.py
Only localhost PostgreSQL and a dedicated *_test database are accepted. The
public synthetic password below is test data, never a development/user secret.
Ctrl+C stops the API and removes only the random schema owned by this process.
"""

from pathlib import Path
from contextlib import contextmanager
import argparse
import asyncio
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
import uvicorn
from fastapi.responses import JSONResponse

from supportops.config import Settings, load_settings
from supportops.main import create_app
from supportops.models import Ticket, User
from supportops.schemas import MessageCreate, TicketCreate, TicketPatch
from supportops.security import hash_password
from supportops.seed import seed, synthetic_id
from supportops.ticket_service import add_message, create_ticket, patch_ticket


PASSWORD = 'S09-local-synthetic-only!'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-delay-ms', type=int, default=0, choices=range(0, 2001), metavar='0..2000')
    parser.add_argument('--extra-tickets', type=int, default=0, choices=range(0, 101), metavar='0..100')
    parser.add_argument('--session-minutes', type=int, default=1, choices=range(1, 31), metavar='1..30')
    parser.add_argument('--lose-first-write-response', action='store_true', help='Return a test-only 503 after the first successful ticket write commits')
    parser.add_argument('--write-delay-ms', type=int, default=0, choices=range(0, 2001), metavar='0..2000')
    args = parser.parse_args()
    with browser_fixture(args) as app:
        uvicorn.run(app, host='127.0.0.1', port=8765, proxy_headers=False, access_log=False)


@contextmanager
def browser_fixture(args):
    """Own one disposable schema for a manual server or automated test runner."""
    configured = load_settings().database_url
    if not configured:
        raise SystemExit('Configure the local database first')
    url = make_url(configured)
    if url.drivername != 'postgresql+psycopg' or url.host not in {'127.0.0.1', 'localhost', '::1'} or not url.database:
        raise SystemExit('This fixture server accepts localhost PostgreSQL only')
    test_url = url if url.database.endswith('_test') else url.set(database=url.database + '_test')
    schema = 'test_s09_browser_' + uuid4().hex
    admin = create_engine(test_url, hide_parameters=True, connect_args={'connect_timeout': 3})
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(test_url, hide_parameters=True, connect_args={'connect_timeout': 3, 'options': f'-csearch_path={schema}'})
        with engine.begin() as connection:
            config = Config(str(ROOT / 'backend' / 'alembic.ini'))
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
        with Session(engine) as session, session.begin():
            seed(session)
            for user in session.scalars(select(User)):
                user.active = True
                user.password_hash = hash_password(PASSWORD)
            session.flush()
            ticket = session.get(Ticket, synthetic_id('ticket-1'))
            ticket.title = '[S09 browser] Unable to access the sample dashboard'
            ticket.body = 'Synthetic request: the sample dashboard reports an access error.\nLiteral markup must remain text: <img src=x onerror=alert(1)>'
            session.flush()
            patch_ticket(session, synthetic_id('manager'), ticket.id, TicketPatch(expected_version=1, assignee_id=synthetic_id('agent-a')), 'fixture-assign')
            add_message(session, synthetic_id('agent-a'), ticket.id, MessageCreate(expected_version=2, visibility='internal', body='Internal-only S09 diagnostic note: check the synthetic account flag.'), 'fixture-internal')
            add_message(session, synthetic_id('agent-a'), ticket.id, MessageCreate(expected_version=3, visibility='public', body='Public update: we are reviewing the sample access issue.'), 'fixture-public')
            create_ticket(session, synthetic_id('requester-b'), TicketCreate(title='[S09 browser] A separate private request', body='Only requester-b and the manager may view this synthetic request.'), 'fixture-private')
            for index in range(args.extra_tickets):
                created_ticket = create_ticket(session, synthetic_id('requester-a'), TicketCreate(title=f'[S10 browser] Pagination sample {index:02d}', body='Synthetic pagination and filtering fixture.'), f'fixture-page-{index}')
                if index % 2:
                    patch_ticket(session, synthetic_id('manager'), created_ticket.body['id'], TicketPatch(expected_version=1, priority='high'), f'fixture-priority-{index}')
        print('Created an isolated synthetic browser fixture schema.', flush=True)
        print('Synthetic accounts: requester-a, requester-b, agent-a, agent-b, manager @example.invalid', flush=True)
        print('Use the public test-only password documented in this script; no local credentials are printed.', flush=True)
        app = create_app(Settings(jwt_secret='S09-test-only-signing-secret-' * 3, access_token_minutes=args.session_minutes), engine=engine)
        if args.lose_first_write_response or args.write_delay_ms:
            lost_response = False

            @app.middleware('http')
            async def write_transport_check(request, call_next):
                nonlocal lost_response
                is_write = request.method in {'POST', 'PATCH'} and request.url.path.startswith('/api/tickets')
                if is_write and args.write_delay_ms:
                    await asyncio.sleep(args.write_delay_ms / 1000)
                response = await call_next(request)
                if is_write and args.lose_first_write_response and not lost_response and 200 <= response.status_code < 300:
                    lost_response = True
                    print('Test transport replaced one committed write response with 503.', flush=True)
                    return JSONResponse(status_code=503, content={'error': {'code': 'test_response_lost'}}, headers={'Cache-Control': 'no-store'})
                return response
        if args.read_delay_ms:
            @app.middleware('http')
            async def delayed_reads(request, call_next):
                response = await call_next(request)
                if request.method == 'GET' and request.url.path.startswith('/api/tickets'):
                    await asyncio.sleep(args.read_delay_ms / 1000)
                return response
        print(f'Fixture sessions last {args.session_minutes} minute(s); normal application configuration is unchanged.', flush=True)
        yield app
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            print('Removed the owned S09 browser-check schema.', flush=True)
        admin.dispose()


if __name__ == '__main__':
    main()
