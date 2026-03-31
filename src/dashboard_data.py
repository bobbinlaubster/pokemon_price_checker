from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.output import build_best_rows
from src.sets import load_sets
from src.tcgplayer_api import TCGplayerClient


@lru_cache(maxsize=4)
def load_snapshot(snapshot_path: str) -> pd.DataFrame:
    path = Path(snapshot_path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_json(path)


@lru_cache(maxsize=4)
def load_market_prices(sets_path: str) -> pd.DataFrame:
    client = TCGplayerClient()
    if not client.available():
        return pd.DataFrame(columns=["set_name", "product_type", "market_price", "market_source"])

    rules = load_sets(sets_path)
    rows: List[Dict[str, object]] = []
    for rule in rules:
        for product_type in rule.allowed_product_types:
            query = f"{rule.name} {product_type}".strip()
            try:
                product_ids = client.search_product_ids(query, limit=3)
                market_price = client.get_best_market_price(product_ids)
            except Exception:
                market_price = None
            rows.append(
                {
                    "set_name": rule.name,
                    "product_type": product_type,
                    "market_price": market_price,
                    "market_source": "TCGplayer" if market_price is not None else None,
                }
            )
    return pd.DataFrame(rows)


def build_best_price_table(snapshot_path: str, sets_path: str) -> pd.DataFrame:
    snapshot_df = load_snapshot(snapshot_path)
    if snapshot_df.empty:
        return pd.DataFrame()

    best_df = pd.DataFrame(build_best_rows(snapshot_df.to_dict(orient="records")))
    if best_df.empty:
        return best_df

    market_df = load_market_prices(sets_path)
    merged = best_df.merge(market_df, how="left", on=["set_name", "product_type"])
    if "market_price" in merged.columns:
        merged["delta_vs_market"] = merged["best_price"] - merged["market_price"]
    return merged
