from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class GlobalSettings:
    timeout_seconds: int
    max_retries: int
    user_agents: List[str]
    respect_robots_txt: bool
    cache_ttl_seconds: int
    max_urls_per_site: int


@dataclass
class ShippingRule:
    type: str = "unknown"
    flat_amount: Optional[float] = None
    free_over: Optional[float] = None


@dataclass
class SiteConfig:
    name: str
    mode: str
    throttle_seconds: float
    currency: str
    adapter: str
    shopify_js_fallback: bool
    collection_pages: List[str]
    max_collection_pages: int
    title_exclude_keywords: List[str]
    shipping: ShippingRule


@dataclass
class AppConfig:
    global_settings: GlobalSettings
    sites: List[SiteConfig]


def _get(d: Dict[str, Any], key: str, default):
    return d.get(key, default)


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    g = data.get("global", {}) or {}

    gs = GlobalSettings(
        timeout_seconds=int(_get(g, "timeout_seconds", 25)),
        max_retries=int(_get(g, "max_retries", 3)),
        user_agents=list(_get(g, "user_agents", [])) or ["Mozilla/5.0"],
        respect_robots_txt=bool(_get(g, "respect_robots_txt", True)),
        cache_ttl_seconds=int(_get(g, "cache_ttl_seconds", 900)),
        max_urls_per_site=int(_get(g, "max_urls_per_site", 250)),
    )

    sites: List[SiteConfig] = []
    for s in data.get("sites", []) or []:
        ship = s.get("shipping", {}) or {}
        mode = str(s["mode"]).lower().strip()
        sites.append(
            SiteConfig(
                name=str(s["name"]).strip(),
                mode=mode,
                throttle_seconds=float(_get(s, "throttle_seconds", 2.0)),
                currency=str(_get(s, "currency", "USD")).strip(),
                adapter=str(_get(s, "adapter", mode)).strip().lower(),
                shopify_js_fallback=bool(_get(s, "shopify_js_fallback", False)),
                collection_pages=list(_get(s, "collection_pages", [])),
                max_collection_pages=int(_get(s, "max_collection_pages", 3)),
                title_exclude_keywords=[
                    str(keyword).strip().lower()
                    for keyword in (_get(s, "title_exclude_keywords", []) or [])
                    if str(keyword).strip()
                ],
                shipping=ShippingRule(
                    type=str(_get(ship, "type", "unknown")),
                    flat_amount=ship.get("flat_amount"),
                    free_over=ship.get("free_over"),
                ),
            )
        )

    return AppConfig(global_settings=gs, sites=sites)
