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

    def test_strips_channel_binding(self) -> None:
        # asyncpg forwards unknown query params to connect() as kwargs and
        # raises TypeError on this one. Neon puts it in every new connection
        # string it hands out.
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@host.neon.tech/db?channel_binding=require"
        )
        assert config.async_url == "postgresql+asyncpg://user:pass@host.neon.tech/db"

    def test_strips_sslmode_and_channel_binding_together(self) -> None:
        # The exact shape Neon returns today.
        config = DatabaseConfig(
            url=(
                "postgresql+asyncpg://user:pass@host.neon.tech/neondb"
                "?sslmode=require&channel_binding=require"
            )
        )
        assert config.async_url == (
            "postgresql+asyncpg://user:pass@host.neon.tech/neondb"
        )
        assert config.async_connect_args == {"ssl": "require"}

    def test_sync_url_keeps_libpq_params(self) -> None:
        # psycopg understands both, and Alembic connects through sync_url.
        url = (
            "postgresql+asyncpg://user:pass@host.neon.tech/db"
            "?sslmode=require&channel_binding=require"
        )
        config = DatabaseConfig(url=url)
        assert "sslmode=require" in config.sync_url
        assert "channel_binding=require" in config.sync_url


class TestAsyncConnectArgs:
    def test_sslmode_translates_to_ssl(self) -> None:
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@host.neon.tech/db?sslmode=require"
        )
        assert config.async_connect_args == {"ssl": "require"}

    def test_no_sslmode_returns_empty(self) -> None:
        config = DatabaseConfig(url="postgresql+asyncpg://localhost:5432/couplefins")
        assert config.async_connect_args == {}
