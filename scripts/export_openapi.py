"""Export the OpenAPI spec from FastAPI to web/openapi.json.

Run from the project root: uv run python -m scripts.export_openapi
"""

import json
from pathlib import Path
import sys

# Ensure project root is on sys.path when invoked directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.interface.api.app import create_app  # noqa: E402

app = create_app()
spec = app.openapi()

# Strip SSE endpoint — Orval can't validate text/event-stream responses
paths = spec.get("paths", {})
paths.pop("/api/v1/events", None)

output = project_root / "web" / "openapi.json"
output.write_text(json.dumps(spec, indent=2) + "\n")
print(f"Wrote {output}")
