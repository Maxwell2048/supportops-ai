from unittest.mock import Mock

from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from supportops.db import check_readiness


def test_readiness_hides_driver_connection_details():
    engine = Mock(spec=Engine)
    engine.connect.side_effect = OperationalError(
        "connect", {}, Exception("private-password@private-database-host")
    )
    result = check_readiness(engine)
    assert result == (False, "database_unavailable_or_unmigrated")
    assert "private-password" not in str(result)
    assert "private-database-host" not in str(result)
