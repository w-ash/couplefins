"""Shared Pydantic type aliases for API schemas."""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

# Decimal precision on input (JSON number → Decimal via str intermediary),
# serialized as a JSON number on output (lossless for 2-decimal monetary values),
# and generates `type: number` in the OpenAPI schema so TypeScript gets `number`.
MoneyField = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema({"type": "number"}),
]
