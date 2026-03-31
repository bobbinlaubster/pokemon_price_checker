import csv
from typing import Any, Dict, List


WATCHLIST_HEADERS = [
    "set_name",
    "product_type",
    "site_name",
    "sku_or_url",
    "latest_timestamp",
    "previous_timestamp",
    "latest_price",
    "previous_price",
    "delta_price",
    "pct_change_price",
    "latest_price_per_pack",
    "previous_price_per_pack",
    "delta_price_per_pack",
    "pct_change_price_per_pack",
    "direction",
]


def write_watchlist_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=WATCHLIST_HEADERS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in WATCHLIST_HEADERS})
