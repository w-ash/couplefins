from typing import Final


class AppConfig:
    TITLE: Final = "Couplefins"
    API_V1_PREFIX: Final = "/api/v1"
    APP_VERSION: Final = "1.5.1"
    SCHEMA_VERSION: Final = "0008"  # must match current Alembic head
