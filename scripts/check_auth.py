"""Local HTTP smoke check; tokens and demo password are never printed."""

import argparse
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from supportops.config import load_settings
from supportops.demo_accounts import DEMO_ROLES
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
    headers = {}
    with httpx.Client(base_url=arguments.base_url, timeout=10, follow_redirects=False) as client:
        for label, role in DEMO_ROLES.items():
            login = client.post("/api/auth/login", json={"email": f"{label}@example.invalid", "password": password})
            if login.status_code != 200:
                raise SystemExit(f"Login failed for synthetic {label}: HTTP {login.status_code}")
            headers[label] = {"Authorization": "Bearer " + login.json()["access_token"]}
            me = client.get("/api/me", headers=headers[label])
            assert me.status_code == 200 and me.json()["role"] == role
            assert set(me.json()) == {"id", "email", "role"}
        path = f"/api/tickets/{synthetic_id('ticket-1')}"
        own = client.get(path, headers=headers["requester-a"])
        assert own.status_code == 200 and "events" not in own.json()
        assert all(message["visibility"] == "public" for message in own.json()["messages"])
        assert client.get(path, headers=headers["requester-b"]).status_code == 404
        assert client.get(path + "/events", headers=headers["requester-a"]).status_code == 403
        assert client.get(path + "/events", headers=headers["manager"]).status_code == 200
        assert client.get("/api/me").status_code == 401
        assert client.get("/ready").status_code == 200
    print("HTTP smoke passed: 5 role logins + me; own-ticket 200; cross-user 404; requester events 403; manager events 200; missing session 401; readiness 200. Secrets not displayed.")


if __name__ == "__main__":
    main()
