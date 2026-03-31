import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def build_daily_summary(
    db_path: str,
    now_utc: Optional[datetime] = None,
    drop_pct_threshold: float = 10.0,
) -> Dict[str, Any]:
    """
    Summarize last 24 hours from SQLite history:
    - Biggest in-stock drops >= threshold
    - Best by set (cheapest in stock) based on latest seen price in window
    - Rising/falling counts + in-stock SKU count
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(hours=24)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        latest_rows = conn.execute(
            """
            WITH ranked AS (
              SELECT
                *,
                ROW_NUMBER() OVER (
                  PARTITION BY set_name, product_type, site_name, sku_or_url
                  ORDER BY timestamp DESC
                ) AS rn
              FROM price_checks
              WHERE timestamp >= ?
            )
            SELECT * FROM ranked WHERE rn = 1
            """,
            (start_utc.isoformat(),),
        ).fetchall()

        drops: List[Dict[str, Any]] = []
        movers: List[Dict[str, Any]] = []
        in_stock_count = 0

        for r in latest_rows:
            latest_ts = r["timestamp"]
            set_name = r["set_name"]
            product_type = r["product_type"]
            site_name = r["site_name"]
            sku_or_url = r["sku_or_url"]

            latest_price = r["price"]
            latest_ppp = r["price_per_pack"]
            latest_in_stock = (r["in_stock"] == 1)

            if latest_in_stock:
                in_stock_count += 1

            prev = conn.execute(
                """
                SELECT timestamp, price, price_per_pack
                FROM price_checks
                WHERE set_name=? AND product_type=? AND site_name=? AND sku_or_url=?
                  AND timestamp < ?
                  AND in_stock=1
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (set_name, product_type, site_name, sku_or_url, latest_ts),
            ).fetchone()

            if not prev:
                continue

            prev_price = prev["price"]
            prev_ppp = prev["price_per_pack"]

            if latest_price is None or prev_price is None or prev_price == 0:
                continue

            pct = ((latest_price - prev_price) / prev_price) * 100.0
            delta = latest_price - prev_price

            ppp_pct = None
            ppp_delta = None
            if latest_ppp is not None and prev_ppp is not None and prev_ppp != 0:
                ppp_pct = ((latest_ppp - prev_ppp) / prev_ppp) * 100.0
                ppp_delta = latest_ppp - prev_ppp

            direction = "Flat"
            if pct > 0:
                direction = "Rising"
            elif pct < 0:
                direction = "Falling"

            row = {
                "set_name": set_name,
                "product_type": product_type,
                "site_name": site_name,
                "sku_or_url": sku_or_url,
                "latest_timestamp": latest_ts,
                "previous_timestamp": prev["timestamp"],
                "latest_price": latest_price,
                "previous_price": prev_price,
                "delta_price": round(delta, 2),
                "pct_change_price": round(pct, 2),
                "latest_price_per_pack": latest_ppp,
                "previous_price_per_pack": prev_ppp,
                "delta_price_per_pack": (round(ppp_delta, 4) if ppp_delta is not None else None),
                "pct_change_price_per_pack": (round(ppp_pct, 2) if ppp_pct is not None else None),
                "direction": direction,
                "in_stock": latest_in_stock,
            }

            movers.append(row)
            if latest_in_stock and pct <= -abs(drop_pct_threshold):
                drops.append(row)

        best_by_set_rows = conn.execute(
            """
            WITH latest AS (
              SELECT
                set_name, product_type, site_name, sku_or_url, price, price_per_pack, timestamp, in_stock,
                ROW_NUMBER() OVER (
                  PARTITION BY set_name, product_type, site_name, sku_or_url
                  ORDER BY timestamp DESC
                ) AS rn
              FROM price_checks
              WHERE timestamp >= ?
            ),
            filtered AS (
              SELECT * FROM latest WHERE rn = 1 AND in_stock = 1 AND price IS NOT NULL
            ),
            ranked AS (
              SELECT *,
                ROW_NUMBER() OVER (
                  PARTITION BY set_name, product_type
                  ORDER BY price ASC
                ) AS pr
              FROM filtered
            )
            SELECT * FROM ranked WHERE pr = 1
            """,
            (start_utc.isoformat(),),
        ).fetchall()

        best_by_set = [{
            "set_name": b["set_name"],
            "product_type": b["product_type"],
            "best_site": b["site_name"],
            "best_price": b["price"],
            "best_price_per_pack": b["price_per_pack"],
            "best_url": b["sku_or_url"],
            "timestamp": b["timestamp"],
        } for b in best_by_set_rows]

        drops.sort(key=lambda x: x["pct_change_price"])  # most negative first
        movers.sort(key=lambda x: abs(x["pct_change_price"]), reverse=True)

        num_rising = sum(1 for m in movers if m["direction"] == "Rising" and m["in_stock"])
        num_falling = sum(1 for m in movers if m["direction"] == "Falling" and m["in_stock"])

        return {
            "date_local_label": now_utc.strftime("%Y-%m-%d"),
            "window_hours": 24,
            "drop_pct_threshold": drop_pct_threshold,
            "drops": drops[:25],
            "best_by_set": best_by_set[:25],
            "top_movers": movers[:25],
            "num_rising": num_rising,
            "num_falling": num_falling,
            "in_stock_count": in_stock_count,
        }
    finally:
        conn.close()
