import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from src.models import ResultRow
from src.normalize import (
    compute_landed_price,
    compute_landed_price_per_pack,
    compute_price_per_pack,
    infer_pack_count,
    is_allowed_language,
    normalize_title,
)
from src.sets import SetRule, match_set
from src.utils import absolutize_url, parse_price, shopify_products_js_url

logger = logging.getLogger(__name__)

CASE_KEYWORDS = ["case", "display case", "sealed case", "carton", "master case", "x6", "x10", "x12"]


def title_excluded(site, title: str) -> bool:
    title_l = (title or "").lower()
    blocked = getattr(site, "title_exclude_keywords", []) or []
    return any(keyword in title_l for keyword in blocked)


def is_case_variant(name: str) -> bool:
    lowered = (name or "").lower()
    return any(keyword in lowered for keyword in CASE_KEYWORDS)


def apply_shipping(site, price: Optional[float]) -> Optional[float]:
    if price is None:
        return None

    rule = getattr(site, "shipping", None)
    if not rule:
        return None

    rule_type = getattr(rule, "type", "unknown")
    if rule_type == "flat" and getattr(rule, "flat_amount", None) is not None:
        try:
            return float(rule.flat_amount)
        except Exception:
            return None

    if rule_type == "free_over" and getattr(rule, "free_over", None) is not None:
        try:
            threshold = float(rule.free_over)
        except Exception:
            return None
        if price >= threshold:
            return 0.0
        return None

    return None


def discover_product_urls(fetcher, site, collection_url: str, max_pages: int, max_urls_per_site: int) -> List[str]:
    product_urls: List[str] = []
    seen = set()

    for page in range(1, max_pages + 1):
        url = f"{collection_url}{'&' if '?' in collection_url else '?'}page={page}"
        time.sleep(site.throttle_seconds)
        try:
            response = fetcher.get(url)
        except Exception as exc:
            logger.warning("Skipping collection page (blocked/failed): %s (%s)", url, exc)
            break

        soup = BeautifulSoup(response.text, "lxml")
        new_on_page = 0
        for anchor in soup.select('a[href*="/products/"]'):
            href = anchor.get("href") or ""
            if not href:
                continue
            full_url = absolutize_url(url, href).split("#")[0]
            if full_url in seen:
                continue
            seen.add(full_url)
            product_urls.append(full_url)
            new_on_page += 1
            if len(product_urls) >= max_urls_per_site:
                return product_urls

        if page > 1 and new_on_page == 0:
            break

    return product_urls


def fetch_shopify_js_variants(fetcher, product_url: str) -> Dict[str, Any]:
    js_url = shopify_products_js_url(product_url)
    if not js_url:
        raise ValueError("no_shopify_handle")
    return fetcher.get(js_url).json()


def derive_variant_offer(variants: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[bool]]:
    prices: List[Tuple[bool, float]] = []
    for variant in variants:
        variant_title = str(variant.get("title") or "")
        if is_case_variant(variant_title):
            continue
        raw_price = variant.get("price")
        if raw_price is None:
            continue
        try:
            price = float(raw_price) / 100.0
        except Exception:
            continue
        prices.append((bool(variant.get("available")), price))

    if not prices:
        return None, None

    available_prices = [price for available, price in prices if available]
    best_price = min(available_prices) if available_prices else min(price for _available, price in prices)
    return best_price, any(available for available, _price in prices)


def build_standard_row(*, site, run_ts: str, title: str, rule: SetRule, product_url: str, price, in_stock, notes: str) -> ResultRow:
    _, base_product_type = normalize_title(title)
    pack_count = infer_pack_count(
        title,
        base_product_type,
        region=rule.region,
        default_booster_box_packs=rule.default_booster_box_packs,
        default_bundle_packs=rule.default_bundle_packs,
    )
    shipping_cost = apply_shipping(site, price)
    return ResultRow(
        timestamp=run_ts,
        franchise=rule.franchise,
        site_name=site.name,
        product_name=title or "Unknown",
        set_name=rule.name,
        product_type=base_product_type,
        sku_or_url=product_url,
        price=price,
        currency=site.currency,
        in_stock=in_stock,
        shipping_if_available=shipping_cost,
        condition="sealed",
        variant_name=None,
        seal_status="sealed",
        unit_type="box",
        boxes_per_case=None,
        pack_count=pack_count,
        price_per_pack=compute_price_per_pack(price, pack_count),
        notes=notes or "html",
    )


def serialize_rows(rows: List[ResultRow]) -> List[dict]:
    output_rows: List[dict] = []
    for row in rows:
        item = row.to_dict()
        shipping_cost = item.get("shipping_if_available")
        item["landed_price"] = compute_landed_price(item.get("price"), shipping_cost)
        item["landed_price_per_pack"] = compute_landed_price_per_pack(item.get("price"), shipping_cost, item.get("pack_count"))
        output_rows.append(item)
    return output_rows


def sakura_variant_rows(*, site, product_url: str, run_ts: str, title: str, rule: SetRule, variants: List[Dict[str, Any]]) -> List[ResultRow]:
    rows: List[ResultRow] = []
    packs_per_box = rule.default_booster_box_packs or (30 if rule.region == "JP" else 36)
    boxes_per_case = 6

    for variant in variants:
        variant_title = str(variant.get("title") or "").strip()
        variant_title_l = variant_title.lower()
        if not bool(variant.get("available")):
            continue

        variant_price = variant.get("price")
        if variant_price is None:
            continue

        try:
            price = float(variant_price) / 100.0
        except Exception:
            continue

        seal_status = "sealed"
        unit_type = "box"
        product_type = "Booster Box"
        pack_count = packs_per_box

        if "no shrink" in variant_title_l or "no-shrink" in variant_title_l:
            seal_status = "no_shrink"
        elif "case" in variant_title_l or is_case_variant(variant_title):
            unit_type = "case"
            pack_count = packs_per_box * boxes_per_case

        shipping_cost = apply_shipping(site, price)
        rows.append(
            ResultRow(
                timestamp=run_ts,
                franchise=rule.franchise,
                site_name=site.name,
                product_name=title,
                set_name=rule.name,
                product_type=product_type,
                sku_or_url=product_url,
                price=price,
                currency=site.currency,
                in_stock=True,
                shipping_if_available=shipping_cost,
                condition="sealed",
                variant_name=variant_title,
                seal_status=seal_status,
                unit_type=unit_type,
                boxes_per_case=(boxes_per_case if unit_type == "case" else None),
                pack_count=pack_count,
                price_per_pack=compute_price_per_pack(price, pack_count),
                notes="shopify_js_variants",
            )
        )

    return rows
