import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session

from supportops.models import AuditEvent, Ticket, TicketMessage, User
from supportops.seed import synthetic_id
from test_tickets import env, call, PATH, TICKET_ID, state


pytestmark = pytest.mark.integration


def audit_rows(env):
    return env[1].execute(select(AuditEvent.__table__).order_by(AuditEvent.ticket_version)).mappings().all()


def test_assignment_audit_is_atomic_redacted_and_replay_is_not_new_change(env, caplog):
    payload = {'expected_version': 1, 'assignee_id': str(synthetic_id('agent-a'))}
    first = call(env, 'PATCH', payload=payload, key='audit-assignment')
    replay = call(env, 'PATCH', payload=payload, key='audit-assignment')
    assert first.status_code == replay.status_code == 200
    rows = audit_rows(env)
    assert len(rows) == 1
    row = rows[0]
    assert row['actor_id'] == synthetic_id('manager') and row['actor_role'] == 'manager'
    assert row['resource_id'] == TICKET_ID and row['resource_type'] == 'ticket'
    assert row['request_id'] == UUID(first.headers['x-request-id'])
    assert row['request_id'] != UUID(replay.headers['x-request-id'])
    assert row['action'] == 'ticket.assigned' and row['result'] == 'success' and row['ticket_version'] == 2
    assert row['changes'] == {'assignee_id': {'from': None, 'to': str(synthetic_id('agent-a'))}}
    records = [json.loads(record.message) for record in caplog.records if record.name == 'supportops.requests']
    assert records[-2]['request_id'] == str(row['request_id']) and records[-2]['status'] == 200
    assert records[-2]['route'] == '/api/tickets/{ticket_id}'


@pytest.mark.parametrize('operation', ['create', 'patch', 'message'])
def test_audit_database_failure_rolls_back_entire_write_and_key_can_retry(env, operation):
    before = state(env)
    ticket_count = env[1].scalar(select(func.count()).select_from(Ticket))
    def fail_audit(session, flush_context, instances):
        for obj in session.new:
            if isinstance(obj, AuditEvent):
                # Violate the real database constraint, rather than mock commit.
                obj.result = 'invalid-result'
    args = {
        'create': ('POST', '/api/tickets', 'requester-a', {'title': 'Synthetic audit failure ticket', 'body': 'Must not be committed'}),
        'patch': ('PATCH', PATH, 'manager', {'expected_version': 1, 'assignee_id': str(synthetic_id('agent-a'))}),
        'message': ('POST', PATH + '/messages', 'requester-a', {'expected_version': 1, 'visibility': 'public', 'body': 'Must not be committed'}),
    }[operation]
    method, path, who, payload = args
    event.listen(Session, 'before_flush', fail_audit)
    try:
        failed = call(env, method, path, who=who, payload=payload, key='rollback-audit')
        assert failed.status_code == 503
        assert failed.json()['error']['request_id'] == failed.headers['x-request-id']
    finally:
        event.remove(Session, 'before_flush', fail_audit)
    assert state(env) == before and audit_rows(env) == []
    assert env[1].scalar(select(func.count()).select_from(Ticket)) == ticket_count
    retry = call(env, method, path, who=who, payload=payload, key='rollback-audit')
    assert retry.status_code == (200 if operation == 'patch' else 201)
    assert len(audit_rows(env)) == 1


def test_denied_and_conflicting_requests_have_no_success_audit(env, caplog):
    assert call(env, 'PATCH', who='requester-a', payload={'expected_version': 1, 'priority': 'high'}).status_code == 403
    assert call(env, 'PATCH', payload={'expected_version': 9, 'priority': 'high'}).status_code == 409
    assert call(env, 'GET', who='requester-b').status_code == 404
    assert not audit_rows(env)
    records = [json.loads(r.message) for r in caplog.records if r.name == 'supportops.requests']
    assert [r['status'] for r in records] == [403, 409, 404]
    assert [r['error_code'] for r in records] == ['forbidden', 'version_conflict', 'not_found']


def test_unexpected_failure_rolls_back_and_is_safe_to_retry(env, caplog):
    before = state(env)
    def fail(session, context, instances):
        if any(isinstance(obj, AuditEvent) for obj in session.new):
            raise RuntimeError('PRIVATE-DIAGNOSTIC-TEXT')
    event.listen(Session, 'before_flush', fail)
    payload = {'expected_version': 1, 'priority': 'high'}
    try:
        response = call(env, 'PATCH', payload=payload, key='unexpected-failure')
    finally:
        event.remove(Session, 'before_flush', fail)
    assert response.status_code == 500 and state(env) == before and audit_rows(env) == []
    assert 'PRIVATE-DIAGNOSTIC-TEXT' not in response.text
    assert 'PRIVATE-DIAGNOSTIC-TEXT' not in '\n'.join(r.message for r in caplog.records if r.name == 'supportops.requests')
    assert call(env, 'PATCH', payload=payload, key='unexpected-failure').status_code == 200


def test_audit_requires_valid_active_identity(env):
    assert call(env, 'GET', '/api/audit-events', token='invalid-token').status_code == 401
    env[1].execute(update(User).where(User.id == synthetic_id('manager')).values(active=False))
    assert call(env, 'GET', '/api/audit-events').status_code == 401


def test_public_private_messages_and_reopen_reasons_are_not_in_audit(env):
    private_text = 'THIS-IS-PRIVATE-FREE-TEXT'
    assert call(env, 'POST', PATH + '/messages', payload={'expected_version': 1, 'visibility': 'internal', 'body': private_text}).status_code == 201
    env[1].execute(update(Ticket).where(Ticket.id == TICKET_ID).values(status='resolved', assignee_id=synthetic_id('agent-a')))
    assert call(env, 'PATCH', who='requester-a', payload={'expected_version': 2, 'status': 'in_progress', 'reason': private_text}).status_code == 200
    rows = audit_rows(env)
    assert len(rows) == 2 and private_text not in str(rows)
    assert rows[0]['changes']['visibility'] == 'internal'
    assert 'message_id' in rows[1]['changes'] and 'reason' not in rows[1]['changes']
    assert private_text in str(env[1].execute(select(TicketMessage.body)).all())


@pytest.mark.parametrize('who', ['requester-a', 'agent-a'])
def test_only_managers_can_read_audit(env, who):
    assert call(env, 'GET', '/api/audit-events', who=who).status_code == 403


def test_manager_query_filters_pagination_and_cursor_isolation(env):
    for version in range(1, 5):
        assert call(env, 'POST', PATH + '/messages', who='requester-a', payload={'expected_version': version, 'visibility': 'public', 'body': 'Synthetic content'}).status_code == 201
    # Equal timestamps exercise the UUID tiebreaker.
    env[1].execute(update(AuditEvent).values(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    params = {'resource_id': str(TICKET_ID), 'limit': 2}
    first = call(env, 'GET', '/api/audit-events', params=params).json()
    assert len(first['items']) == 2 and first['next_cursor']
    second = call(env, 'GET', '/api/audit-events', params={**params, 'cursor': first['next_cursor']}).json()
    assert len(second['items']) == 2 and second['next_cursor'] is None
    assert len({row['id'] for row in first['items'] + second['items']}) == 4
    assert call(env, 'GET', '/api/audit-events', params={**params, 'cursor': first['next_cursor'], 'limit': 3}).status_code == 422
    assert call(env, 'GET', '/api/audit-events', params={**params, 'cursor': first['next_cursor'] + 'tamper'}).status_code == 422
    assert call(env, 'GET', '/api/tickets', params={'limit': 2, 'cursor': first['next_cursor']}).status_code == 422
    assert call(env, 'GET', '/api/me', token=first['next_cursor']).status_code == 401
    env[1].execute(update(User).where(User.id == synthetic_id('agent-b')).values(role='manager'))
    assert call(env, 'GET', '/api/audit-events', who='agent-b', params={**params, 'cursor': first['next_cursor']}).status_code == 422
    row = first['items'][0]
    filtered = call(env, 'GET', '/api/audit-events', params={'request_id': row['request_id']}).json()
    assert len(filtered['items']) == 1 and filtered['items'][0]['id'] == row['id']
    assert call(env, 'GET', '/api/audit-events', params={'actor_id': str(synthetic_id('manager'))}).json()['items'] == []
    assert call(env, 'GET', '/api/audit-events', params={'action': 'ticket.assigned'}).json()['items'] == []
    assert call(env, 'GET', '/api/audit-events', params={'resource_id': str(uuid4())}).json()['items'] == []
    env[1].execute(update(User).where(User.id == synthetic_id('manager')).values(role='agent'))
    assert call(env, 'GET', '/api/audit-events', params={**params, 'cursor': first['next_cursor']}).status_code == 403


@pytest.mark.parametrize('params', [{'limit': 101}, {'resource_id': 'bad'}, {'resource_type': 'user'}, {'action': 'delete'}, {'unknown': 'x'}])
def test_audit_query_validation(env, params):
    assert call(env, 'GET', '/api/audit-events', params=params).status_code == 422
