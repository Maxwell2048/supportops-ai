import asyncio
import json
from uuid import UUID

import httpx

from supportops.config import Settings
from supportops.main import create_app
from supportops.schemas import LoginInput


def test_logs_and_unhandled_errors_are_redacted_and_request_ids_are_server_generated(caplog):
    app = create_app(Settings())
    @app.get('/_test_failure/{item}')
    def fail(item: str):
        raise RuntimeError('TOP-SECRET exception payload')

    @app.post('/_test_validation')
    def validate(payload: LoginInput):
        return {'ok': True}

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            failed = await client.get('/_test_failure/TOP-SECRET?token=TOP-SECRET', headers={
                'X-Request-ID': 'attacker-controlled', 'Authorization': 'Bearer TOP-SECRET'})
            assert failed.status_code == 500 and 'TOP-SECRET' not in failed.text
            assert failed.json()['error']['request_id'] == failed.headers['x-request-id']
            UUID(failed.headers['x-request-id'])
            assert failed.headers['x-request-id'] != 'attacker-controlled'
            missing = await client.get('/TOP-SECRET?password=TOP-SECRET')
            assert missing.status_code == 404
            invalid = await client.post('/_test_validation', json={'email': 'bad', 'password': 'TOP-SECRET'})
            assert invalid.status_code == 422
            return failed.headers['x-request-id']
    request_id = asyncio.run(scenario())
    logs = [json.loads(r.message) for r in caplog.records if r.name == 'supportops.requests']
    assert len(logs) == 3 and 'TOP-SECRET' not in json.dumps(logs)
    assert logs[0]['route'] == '/_test_failure/{item}' and logs[0]['request_id'] == request_id
    assert logs[0]['error_code'] == 'internal_error' and logs[1]['route'] == 'unmatched'
    assert logs[2]['error_code'] == 'validation_error'
    assert all(log['duration_ms'] >= 0 for log in logs)
