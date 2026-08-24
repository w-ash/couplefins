from typing import Final


class AppConfig:
    TITLE: Final = "Couplefins"
    API_V1_PREFIX: Final = "/api/v1"
    APP_VERSION: Final = "1.11.0"
    SCHEMA_VERSION: Final = "0012"  # must match current Alembic head
