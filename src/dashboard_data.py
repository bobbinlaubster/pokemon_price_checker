from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.output import build_best_rows
from src.sets import load_sets
from src.tcgplayer_api import TCGplayerClient


def load_snapshot(snapshot_path: str) -> pd.DataFrame:
    path = Path(snapshot_path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_json(path)


def load_market_prices(sets_path: str) -> pd.DataFrame:
    client = TCGplayerClient()
    if not client.available():
        return pd.DataFrame(columns=["franchise", "region", "set_name", "product_type", "market_price", "market_source"])

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
                    "franchise": rule.franchise,
                    "region": rule.region,
                    "set_name": rule.name,
                    "product_type": product_type,
                    "market_price": market_price,
                    "market_source": "TCGplayer" if market_price is not None else None,
                }
            )
    return pd.DataFrame(rows)


def build_best_price_table(snapshot_path: str, sets_path: str) -> pd.DataFrame:
    rules = load_sets(sets_path)
    set_meta_df = pd.DataFrame(
        [
            {
                "franchise": rule.franchise,
                "region": rule.region,
                "set_name": rule.name,
            }
            for rule in rules
        ]
    )

    snapshot_df = load_snapshot(snapshot_path)
    if snapshot_df.empty:
        return pd.DataFrame()

    best_df = pd.DataFrame(build_best_rows(snapshot_df.to_dict(orient="records")))
    if best_df.empty:
        return best_df

    if not set_meta_df.empty:
        best_df = best_df.merge(set_meta_df, how="left", on=["franchise", "set_name"])

    market_df = load_market_prices(sets_path)
    merged = best_df.merge(market_df, how="left", on=["franchise", "region", "set_name", "product_type"])
    if "market_price" in merged.columns:
        merged["delta_vs_market"] = merged["best_price"] - merged["market_price"]
    return merged


def build_tracked_sets_table(snapshot_path: str, sets_path: str) -> pd.DataFrame:
    rules = load_sets(sets_path)
    tracked_rows = [
        {
            "franchise": rule.franchise,
            "region": rule.region,
            "set_name": rule.name,
            "tracked_product_types": ", ".join(rule.allowed_product_types),
            "set_order": index,
        }
        for index, rule in enumerate(rules)
    ]
    tracked_df = pd.DataFrame(tracked_rows)
    if tracked_df.empty:
        return tracked_df

    best_df = build_best_price_table(snapshot_path, sets_path)
    if best_df.empty:
        tracked_df["best_product_type"] = None
        tracked_df["best_site"] = None
        tracked_df["best_price_per_pack"] = None
        tracked_df["market_price"] = None
        tracked_df["delta_vs_market"] = None
        tracked_df["best_url"] = None
        return tracked_df.drop(columns=["set_order"])

    best_by_set = (
        best_df.sort_values(
            by=["franchise", "set_name", "best_effective_price_per_pack"],
            na_position="last",
        )
        .groupby(["franchise", "set_name"], as_index=False)
        .first()
        .rename(columns={"product_type": "best_product_type"})
    )

    merged = tracked_df.merge(best_by_set, how="left", on=["franchise", "set_name"])
    merged = merged.sort_values(by=["franchise", "set_order"], kind="stable")
    return merged.drop(columns=["set_order"])
