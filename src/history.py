import sqlite3
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS price_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  site_name TEXT NOT NULL,
  product_name TEXT NOT NULL,
  set_name TEXT NOT NULL,
  product_type TEXT NOT NULL,
  sku_or_url TEXT NOT NULL,
  price REAL,
  currency TEXT,
  in_stock INTEGER,
  shipping_if_available REAL,
  condition TEXT,
  pack_count INTEGER,
  price_per_pack REAL,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_checks_lookup
ON price_checks (set_name, product_type, site_name, sku_or_url, timestamp);

CREATE INDEX IF NOT EXISTS idx_checks_ts
ON price_checks (timestamp);
"""


def _to_int_bool(v: Any) -> Optional[int]:
    if v is None:
        return None
    return 1 if bool(v) else 0


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def insert_rows(db_path: str, rows: List[Dict[str, Any]]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        sql = """
        INSERT INTO price_checks (
          timestamp, site_name, product_name, set_name, product_type, sku_or_url,
          price, currency, in_stock, shipping_if_available, condition, pack_count,
          price_per_pack, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        data = []
        for r in rows:
            data.append((
                r.get("timestamp"),
                r.get("site_name"),
                r.get("product_name") or "Unknown",
                r.get("set_name") or "Unknown",
                r.get("product_type") or "Unknown",
                r.get("sku_or_url") or "",
                r.get("price"),
                r.get("currency"),
                _to_int_bool(r.get("in_stock")),
                r.get("shipping_if_available"),
                r.get("condition"),
                r.get("pack_count"),
                r.get("price_per_pack"),
                r.get("notes") or "",
            ))
        conn.executemany(sql, data)
        conn.commit()
    finally:
        conn.close()


def _latest_two_points(
    conn: sqlite3.Connection,
    set_name: str,
    product_type: str,
    site_name: str,
    sku_or_url: str,
    only_in_stock: bool = True,
) -> List[Tuple]:
    where = "set_name=? AND product_type=? AND site_name=? AND sku_or_url=?"
    params = [set_name, product_type, site_name, sku_or_url]
    if only_in_stock:
        where += " AND in_stock=1"

    q = f"""
    SELECT timestamp, price, price_per_pack, in_stock
    FROM price_checks
    WHERE {where}
    ORDER BY timestamp DESC
    LIMIT 2
    """
    return conn.execute(q, params).fetchall()


def build_trend_report(
    db_path: str,
    latest_rows: List[Dict[str, Any]],
    only_in_stock: bool = True,
    min_abs_pct_change: float = 0.0,
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    try:
        out: List[Dict[str, Any]] = []
        seen = set()

        for r in latest_rows:
            set_name = r.get("set_name") or "Unknown"
            product_type = r.get("product_type") or "Unknown"
            site_name = r.get("site_name") or "Unknown"
            sku_or_url = r.get("sku_or_url") or ""

            key = (set_name, product_type, site_name, sku_or_url)
            if key in seen:
                continue
            seen.add(key)

            points = _latest_two_points(
                conn, set_name, product_type, site_name, sku_or_url, only_in_stock=only_in_stock
            )
            if len(points) < 2:
                continue

            (ts_now, price_now, ppp_now, _in_stock_now) = points[0]
            (ts_prev, price_prev, ppp_prev, _in_stock_prev) = points[1]

            delta = None
            pct = None
            if price_now is not None and price_prev is not None and price_prev != 0:
                delta = round(float(price_now) - float(price_prev), 2)
                pct = round((float(price_now) - float(price_prev)) / float(price_prev) * 100.0, 2)

            ppp_delta = None
            ppp_pct = None
            if ppp_now is not None and ppp_prev is not None and ppp_prev != 0:
                ppp_delta = round(float(ppp_now) - float(ppp_prev), 4)
                ppp_pct = round((float(ppp_now) - float(ppp_prev)) / float(ppp_prev) * 100.0, 2)

            if min_abs_pct_change > 0 and (pct is None or abs(pct) < min_abs_pct_change):
                continue

            direction = "Flat"
            if pct is not None:
                if pct > 0:
                    direction = "Rising"
                elif pct < 0:
                    direction = "Falling"

            out.append({
                "set_name": set_name,
                "product_type": product_type,
                "site_name": site_name,
                "sku_or_url": sku_or_url,
                "latest_timestamp": ts_now,
                "previous_timestamp": ts_prev,
                "latest_price": price_now,
                "previous_price": price_prev,
                "delta_price": delta,
                "pct_change_price": pct,
                "latest_price_per_pack": ppp_now,
                "previous_price_per_pack": ppp_prev,
                "delta_price_per_pack": ppp_delta,
                "pct_change_price_per_pack": ppp_pct,
                "direction": direction,
            })

        out.sort(key=lambda x: abs(x.get("pct_change_price") or 0.0), reverse=True)
        return out
    finally:
        conn.close()


def build_drop_watchlist(trends: List[Dict[str, Any]], drop_pct_threshold: float = 10.0) -> List[Dict[str, Any]]:
    out = []
    for t in trends:
        pct = t.get("pct_change_price")
        if pct is None:
            continue
        if pct <= -abs(drop_pct_threshold):
            out.append(t)
    out.sort(key=lambda x: x.get("pct_change_price") or 0.0)  # most negative first
    return out
