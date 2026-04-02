from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ScrapeContext:
    fetcher: object
    site: object
    max_products: int | None
    run_ts: str
    set_rules: list
    max_urls_per_site: int


@dataclass
class SiteScrapeResult:
    rows: List[dict]
    coverage: Dict[str, int]
    near_misses: List[Dict[str, str]]
