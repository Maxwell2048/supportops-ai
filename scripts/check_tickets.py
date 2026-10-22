"""Local HTTP ticket workflow; creates a labelled synthetic closed/archived ticket."""

import argparse
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from supportops.config import load_settings
from supportops.seed import synthetic_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    parsed = urlparse(arguments.base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("This smoke check sends demo credentials to a local API only")
    load_settings()
    password = os.getenv("DEMO_PASSWORD")
    if not password:
        raise SystemExit("Configure and activate local demo accounts first")
    run_id = str(uuid4())
    tokens = {}
    with httpx.Client(base_url=arguments.base_url, timeout=10, follow_redirects=False) as client:
        for label in ("requester-a", "requester-b", "agent-a", "agent-b", "manager"):
            response = client.post("/api/auth/login", json={"email": f"{label}@example.invalid", "password": password})
            assert response.status_code == 200, f"Demo login failed: {label} HTTP {response.status_code}"
            tokens[label] = response.json()["access_token"]

        def read(path, who, **kwargs):
            return client.get(path, headers={"Authorization": "Bearer " + tokens[who]}, **kwargs)

        def write(method, path, who, body, key=None):
            return client.request(method, path, json=body, headers={"Authorization": "Bearer " + tokens[who],
                "Idempotency-Key": key or str(uuid4())})

        payload = {"title": f"[S08 smoke] {run_id}", "body": "Synthetic HTTP acceptance ticket retained as development evidence."}
        created = write("POST", "/api/tickets", "requester-a", payload, run_id)
        assert created.status_code == 201
        assert write("POST", "/api/tickets", "requester-a", payload, run_id).json() == created.json()
        path = "/api/tickets/" + created.json()["id"]
        assert read(path, "requester-b").status_code == 404
        assert write("PATCH", path, "requester-a", {"expected_version": 1, "assignee_id": str(synthetic_id("agent-a"))}).status_code == 403

        version = 1
        def patch(who, **fields):
            nonlocal version
            response = write("PATCH", path, who, {"expected_version": version, **fields})
            assert response.status_code == 200, f"Patch failed: HTTP {response.status_code}"
            version = response.json()["version"]
            return response

        patch("manager", assignee_id=str(synthetic_id("agent-a")))
        patch("agent-a", status="in_progress")
        body = {"expected_version": version, "visibility": "internal", "body": "Synthetic internal note: customers must not see this content."}
        message_key = str(uuid4())
        message = write("POST", path + "/messages", "agent-a", body, message_key)
        assert message.status_code == 201
        assert write("POST", path + "/messages", "agent-a", body, message_key).json() == message.json()
        version = message.json()["ticket_version"]
        requester_detail = read(path, "requester-a").json()
        assert requester_detail["messages"] == [] and "events" not in requester_detail
        stale = write("PATCH", path, "manager", {"expected_version": 1, "priority": "high"})
        assert stale.status_code == 409
        patch("agent-a", status="waiting_customer", public_reply="Please provide the synthetic error code.")
        reply = write("POST", path + "/messages", "requester-a", {"expected_version": version, "visibility": "public", "body": "Sample error code E001."})
        assert reply.status_code == 201
        version = reply.json()["ticket_version"]
        patch("agent-a", status="in_progress")
        patch("manager", assignee_id=str(synthetic_id("agent-b")))
        assert read(path, "agent-a").status_code == 404
        assert write("POST", path + "/messages", "agent-a", body, message_key).status_code == 404
        patch("agent-b", status="resolved", public_reply="Resolved using the synthetic repair procedure.")
        patch("requester-a", status="in_progress", reason="Synthetic reproduction: the issue has returned.")
        patch("agent-b", status="resolved", public_reply="Synthetic follow-up repair completed.")
        patch("manager", status="closed")
        patch("manager", archived=True)
        assert write("POST", path + "/messages", "requester-a", {"expected_version": version, "visibility": "public", "body": "Must not be written"}).status_code == 409
        page = read("/api/tickets", "requester-a", params={"q": run_id, "status": "closed", "limit": 1})
        assert page.status_code == 200 and [row["id"] for row in page.json()["items"]] == [created.json()["id"]]
        events = read(path + "/events", "manager")
        assert events.status_code == 200
        assert [row["ticket_version"] for row in events.json()] == list(range(1, version + 1))
        for who in ('requester-a', 'agent-b'):
            assert read('/api/audit-events', who).status_code == 403
        audit = read('/api/audit-events', 'manager', params={'resource_id': created.json()['id'], 'limit': 100})
        assert audit.status_code == 200 and audit.json()['next_cursor'] is None
        rows = audit.json()['items']
        assert len(rows) == version and sorted(row['ticket_version'] for row in rows) == list(range(1, version + 1))
        assert all(row['result'] == 'success' for row in rows)
        creation_audit = next(row for row in rows if row['ticket_version'] == 1)
        assert creation_audit['request_id'] == created.headers['x-request-id']
        by_request = read('/api/audit-events', 'manager', params={'request_id': created.headers['x-request-id']})
        assert [row['id'] for row in by_request.json()['items']] == [creation_audit['id']]
        assert 'Synthetic reproduction' not in audit.text and 'customers must not see this content' not in audit.text
        assert stale.json()['error']['request_id'] == stale.headers['x-request-id']
        print(f"Audit trace passed: records={len(rows)} create_request_id={created.headers['x-request-id']} conflict_request_id={stale.headers['x-request-id']}; manager-only query and no duplicate success audit verified.")
        print(f"HTTP ticket workflow passed: ticket={created.json()['id']} final_version={version}; closed and archived. Creation/message retries, 403/404/409, internal isolation, reassignment, reopen and filtered list verified. Credentials not displayed.")


if __name__ == "__main__":
    main()
