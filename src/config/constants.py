from typing import Final


class AppConfig:
    TITLE: Final = "Couplefins"
    API_V1_PREFIX: Final = "/api/v1"
    APP_VERSION: Final = "1.3.3"
    SCHEMA_VERSION: Final = "0007"  # must match current Alembic head
