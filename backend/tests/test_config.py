import pytest

from supportops.config import Settings


def test_config_does_not_expose_database_password_in_repr():
    settings = Settings(database_url="postgresql+psycopg://user:private-password@localhost/test")
    assert "private-password" not in repr(settings)


@pytest.mark.parametrize("url", ["sqlite:///test.db", "postgresql://user:password@localhost/test"])
def test_only_supported_postgres_driver_is_accepted(url):
    with pytest.raises(ValueError, match="postgresql\\+psycopg"):
        Settings(database_url=url)
