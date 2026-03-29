from src.config.settings import DatabaseConfig


class TestIsPooledEndpoint:
    def test_pooled_neon_url(self) -> None:
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@ep-abc-pooler.us-west-2.aws.neon.tech/db"
        )
        assert config.is_pooled_endpoint is True

    def test_direct_neon_url(self) -> None:
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@ep-abc.us-west-2.aws.neon.tech/db"
        )
        assert config.is_pooled_endpoint is False

    def test_local_url(self) -> None:
        config = DatabaseConfig(url="postgresql+asyncpg://localhost:5432/couplefins")
        assert config.is_pooled_endpoint is False


class TestAsyncUrl:
    def test_strips_sslmode_from_neon_url(self) -> None:
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@host.neon.tech/db?sslmode=require"
        )
        assert "sslmode" not in config.async_url
        assert config.async_url == "postgresql+asyncpg://user:pass@host.neon.tech/db"

    def test_preserves_other_query_params(self) -> None:
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@host/db?sslmode=require&options=-c%20timezone%3Dutc"
        )
        assert "sslmode" not in config.async_url
        assert "options=" in config.async_url

    def test_no_sslmode_returns_unchanged(self) -> None:
        url = "postgresql+asyncpg://localhost:5432/couplefins"
        config = DatabaseConfig(url=url)
        assert config.async_url == url


class TestAsyncConnectArgs:
    def test_sslmode_translates_to_ssl(self) -> None:
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@host.neon.tech/db?sslmode=require"
        )
        assert config.async_connect_args == {"ssl": "require"}

    def test_no_sslmode_returns_empty(self) -> None:
        config = DatabaseConfig(url="postgresql+asyncpg://localhost:5432/couplefins")
        assert config.async_connect_args == {}
