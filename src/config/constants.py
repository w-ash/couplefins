from typing import Final


class AppConfig:
    TITLE: Final = "Couplefins"
    API_V1_PREFIX: Final = "/api/v1"
    APP_VERSION: Final = "1.2.2"
    SCHEMA_VERSION: Final = "0005"  # must match current Alembic head
