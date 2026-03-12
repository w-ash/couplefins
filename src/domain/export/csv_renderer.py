import csv
import io

from src.domain.export.adjustments import Adjustment

ADJUSTMENT_TAG = "couplefins-adjustment"
_COLUMNS = ("Date", "Amount", "Merchant", "Category", "Account", "Tags", "Notes")


def render_adjustment_csv(adjustments: list[Adjustment]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS)
    for adj in adjustments:
        writer.writerow([
            adj.date.isoformat(),
            str(adj.amount),
            adj.merchant,
            adj.category,
            adj.account,
            ADJUSTMENT_TAG,
            f"[cf:{adj.dedup_id}]",
        ])
    return buf.getvalue()
