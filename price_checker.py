import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from src.config import AppConfig, load_config
from src.fetcher import Fetcher
from src.history import init_db, insert_rows
from src.output import (
    build_best_rows,
    write_best_by_set_csv,
    write_best_by_set_xlsx,
    write_coverage_csv,
    write_csv,
    write_json,
    write_near_misses_csv,
)
from src.scraper import scrape_site
from src.sets import SetRule, load_sets
from src.utils import setup_logging


def parse_args():
    parser = argparse.ArgumentParser(description="Card price checker (Pokemon + One Piece).")
    parser.add_argument("--config", default="sites.yaml")
    parser.add_argument("--sets", default="sets.yaml")
    parser.add_argument("--out", default="results")
    parser.add_argument("--db", default=None, help="SQLite history database path. Defaults to <out>/history.sqlite")
    parser.add_argument("--max-products", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_fetcher(cfg: AppConfig) -> Fetcher:
    return Fetcher(
        timeout_seconds=cfg.global_settings.timeout_seconds,
        max_retries=cfg.global_settings.max_retries,
        user_agents=cfg.global_settings.user_agents,
        respect_robots_txt=cfg.global_settings.respect_robots_txt,
        cache_ttl_seconds=cfg.global_settings.cache_ttl_seconds,
    )


def collect_rows(
    cfg: AppConfig,
    set_rules: List[SetRule],
    fetcher: Fetcher,
    run_ts: str,
    max_products: int | None,
) -> Tuple[List[dict], List[Dict[str, int]], List[Dict[str, str]]]:
    all_rows: List[dict] = []
    coverage_rows: List[Dict[str, int]] = []
    near_misses: List[Dict[str, str]] = []

    for site in cfg.sites:
        rows, coverage, misses = scrape_site(
            fetcher=fetcher,
            site=site,
            max_products=max_products,
            run_ts=run_ts,
            set_rules=set_rules,
            max_urls_per_site=cfg.global_settings.max_urls_per_site,
        )
        all_rows.extend(rows)
        coverage_rows.append(coverage)
        near_misses.extend(misses)

    return all_rows, coverage_rows, near_misses


def persist_outputs(out_dir: Path, safe_ts: str, rows: List[dict], coverage_rows, near_misses) -> Dict[str, Path]:
    paths = {
        "raw_csv": out_dir / f"raw_results_{safe_ts}.csv",
        "raw_json": out_dir / f"raw_results_{safe_ts}.json",
        "best_csv": out_dir / f"best_by_set_{safe_ts}.csv",
        "best_xlsx": out_dir / f"best_by_set_{safe_ts}.xlsx",
        "coverage": out_dir / f"coverage_{safe_ts}.csv",
        "near_misses": out_dir / f"near_misses_{safe_ts}.csv",
        "latest_snapshot": out_dir / "latest_snapshot.json",
        "latest_best": out_dir / "latest_best_by_set.json",
    }

    write_coverage_csv(paths["coverage"], coverage_rows)
    write_near_misses_csv(paths["near_misses"], near_misses)
    write_csv(paths["raw_csv"], rows)
    write_json(paths["raw_json"], rows)
    write_best_by_set_csv(paths["best_csv"], rows)
    write_best_by_set_xlsx(paths["best_xlsx"], rows)
    write_json(paths["latest_snapshot"], rows)
    write_json(paths["latest_best"], build_best_rows(rows))
    return paths


def main():
    args = parse_args()
    setup_logging()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config(args.config)
    set_rules = load_sets(args.sets)
    fetcher = build_fetcher(cfg)

    run_ts = datetime.now(timezone.utc).isoformat()
    safe_ts = run_ts.replace(":", "-")

    rows, coverage_rows, near_misses = collect_rows(
        cfg=cfg,
        set_rules=set_rules,
        fetcher=fetcher,
        run_ts=run_ts,
        max_products=args.max_products,
    )

    if args.dry_run:
        print(f"Collected {len(rows)} rows.")
        for row in rows[:20]:
            print(row)
        return

    paths = persist_outputs(out_dir, safe_ts, rows, coverage_rows, near_misses)

    db_path = Path(args.db) if args.db else out_dir / "history.sqlite"
    init_db(str(db_path))
    insert_rows(str(db_path), rows)

    print("Done. Files created:")
    for label in ["raw_csv", "raw_json", "best_csv", "best_xlsx", "coverage", "near_misses", "latest_snapshot", "latest_best"]:
        print(f"- {paths[label]}")
    print(f"- {db_path}")


if __name__ == "__main__":
    main()
