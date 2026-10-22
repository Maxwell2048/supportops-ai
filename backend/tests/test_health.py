import asyncio

import httpx

from supportops.main import create_app
from supportops.config import Settings


def test_liveness_does_not_claim_dependency_readiness():
    async def check_endpoints():
        transport = httpx.ASGITransport(app=create_app(Settings()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok", "service": "supportops-api"}
            readiness = await client.get("/ready")
            assert readiness.status_code == 503
            assert readiness.json()["reason"] == "database_not_configured"

    asyncio.run(check_endpoints())
