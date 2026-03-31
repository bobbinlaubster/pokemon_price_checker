import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from src.models import ResultRow
from src.normalize import (
    normalize_title,
    infer_pack_count,
    compute_price_per_pack,
    compute_landed_price,
    compute_landed_price_per_pack,
    is_allowed_language,
)
from src.sets import match_set, SetRule
from src.utils import parse_price, shopify_products_js_url, absolutize_url

logger = logging.getLogger(__name__)

CASE_KEYWORDS = ["case", "display case", "sealed case", "carton", "master case", "x6", "x10", "x12"]


def _is_case_variant(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in CASE_KEYWORDS)


def _apply_shipping(site, price: Optional[float]) -> Optional[float]:
    if price is None:
        return None

    rule = getattr(site, "shipping", None)
    if not rule:
        return None

    rtype = getattr(rule, "type", "unknown")
    if rtype == "flat" and getattr(rule, "flat_amount", None) is not None:
        try:
            return float(rule.flat_amount)
        except Exception:
            return None

    if rtype == "free_over" and getattr(rule, "free_over", None) is not None:
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
            resp = fetcher.get(url)
        except Exception as e:
            logger.warning("Skipping collection page (blocked/failed): %s (%s)", url, e)
            break

        soup = BeautifulSoup(resp.text, "lxml")

        new_on_page = 0
        for a in soup.select('a[href*="/products/"]'):
            href = a.get("href") or ""
            if not href:
                continue
            full = absolutize_url(url, href).split("#")[0]
            if full not in seen:
                seen.add(full)
                product_urls.append(full)
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
    js_resp = fetcher.get(js_url)
    return js_resp.json()


def _sakura_variant_rows(
    *,
    site,
    product_url: str,
    run_ts: str,
    title: str,
    rule: SetRule,
    variants: List[Dict[str, Any]],
) -> List[ResultRow]:
    out: List[ResultRow] = []

    packs_per_box = rule.default_booster_box_packs or (30 if rule.region == "JP" else 36)
    boxes_per_case = 6

    for v in variants:
        v_title = str(v.get("title") or "").strip()
        v_title_l = v_title.lower()
        available = bool(v.get("available"))
        if not available:
            continue

        v_price = v.get("price")
        if v_price is None:
            continue

        try:
            price = float(v_price) / 100.0
        except Exception:
            continue

        seal_status = "sealed"
        unit_type = "box"
        product_type = "Booster Box"
        pack_count = packs_per_box

        if "no shrink" in v_title_l or "no-shrink" in v_title_l:
            seal_status = "no_shrink"
            unit_type = "box"
            pack_count = packs_per_box
        elif "case" in v_title_l or _is_case_variant(v_title):
            seal_status = "sealed"
            unit_type = "case"
            pack_count = packs_per_box * boxes_per_case

        ship_cost = _apply_shipping(site, price)
        ppp = compute_price_per_pack(price, pack_count)

        out.append(ResultRow(
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
            shipping_if_available=ship_cost,
            condition="sealed",
            variant_name=v_title,
            seal_status=seal_status,
            unit_type=unit_type,
            boxes_per_case=(boxes_per_case if unit_type == "case" else None),
            pack_count=pack_count,
            price_per_pack=ppp,
            notes="shopify_js_variants",
        ))

    return out


def scrape_site(
    fetcher,
    site,
    max_products: Optional[int],
    run_ts: str,
    set_rules: List[SetRule],
    max_urls_per_site: int,
) -> Tuple[List[dict], Dict[str, int], List[Dict[str, str]]]:
    rows: List[ResultRow] = []
    near_misses: List[Dict[str, str]] = []

    discovered_urls: List[str] = []
    processed_urls = 0
    matched_rows = 0
    keyword_hits_but_filtered = 0
    unknown_product_type = 0

    for c in site.collection_pages:
        discovered_urls.extend(
            discover_product_urls(fetcher, site, c, site.max_collection_pages, max_urls_per_site)
        )

    discovered_urls = list(dict.fromkeys(discovered_urls))
    if max_products:
        discovered_urls = discovered_urls[:max_products]

    total = len(discovered_urls)

    for url in discovered_urls:
        processed_urls += 1
        print(f"[HB] [{site.name}] {processed_urls}/{total} {url}")

        time.sleep(site.throttle_seconds)
        try:
            title = ""
            price = None
            in_stock = None
            notes = ""

            js = None
            if site.shopify_js_fallback:
                try:
                    js = fetch_shopify_js_variants(fetcher, url)
                    title = str(js.get("title", "")).strip() or title
                    notes = "shopify_js"
                except Exception as e:
                    notes = f"shopify_js_failed:{e}"
                    js = None

            if not title or js is None:
                resp = fetcher.get(url)
                soup = BeautifulSoup(resp.text, "lxml")
                if not title:
                    h1 = soup.select_one("h1")
                    title = h1.get_text(strip=True) if h1 else url

            # Language filter
            if not is_allowed_language(title):
                continue

            _, base_product_type = normalize_title(title)
            if base_product_type == "Unknown":
                unknown_product_type += 1

            rule = match_set(title, set_rules)
            if not rule:
                continue

            if site.name.strip().lower().startswith("sakuras") and js is not None:
                variants = js.get("variants") or []
                variant_rows = _sakura_variant_rows(
                    site=site,
                    product_url=url,
                    run_ts=run_ts,
                    title=title,
                    rule=rule,
                    variants=variants,
                )

                final_variant_rows = []
                for vr in variant_rows:
                    if rule.allowed_product_types and vr.product_type not in rule.allowed_product_types:
                        keyword_hits_but_filtered += 1
                        near_misses.append({
                            "site_name": site.name,
                            "title": f"{title} [{vr.variant_name}]",
                            "reason": "filtered_by_product_type",
                            "url": url,
                        })
                        continue
                    final_variant_rows.append(vr)

                rows.extend(final_variant_rows)
                matched_rows += len(final_variant_rows)
                continue

            # Cheapest available non-case variant for other shops
            if js is not None:
                variants = js.get("variants") or []
                prices: List[Tuple[bool, float]] = []
                for v in variants:
                    v_title = str(v.get("title") or "")
                    if _is_case_variant(v_title):
                        continue
                    v_price = v.get("price")
                    if v_price is None:
                        continue
                    try:
                        p = float(v_price) / 100.0
                    except Exception:
                        continue
                    avail = bool(v.get("available"))
                    prices.append((avail, p))

                available_prices = [p for avail, p in prices if avail]
                price = min(available_prices) if available_prices else (min(p for _, p in prices) if prices else None)
                in_stock = any(avail for avail, _ in prices) if prices else None

            if price is None or in_stock is None:
                resp = fetcher.get(url)
                soup = BeautifulSoup(resp.text, "lxml")
                if price is None:
                    price_node = soup.select_one(
                        "span.price-item--sale, span.price-item--regular, .price__regular .price-item, .price .money, [data-product-price]"
                    )
                    price = parse_price(price_node.get_text(" ", strip=True) if price_node else "")
                if in_stock is None:
                    in_stock = ("sold out" not in soup.get_text(" ", strip=True).lower())

            if rule.allowed_product_types and base_product_type not in rule.allowed_product_types:
                keyword_hits_but_filtered += 1
                near_misses.append({
                    "site_name": site.name,
                    "title": title,
                    "reason": "filtered_by_product_type",
                    "url": url,
                })
                continue

            pack_count = infer_pack_count(
                title,
                base_product_type,
                region=rule.region,
                default_booster_box_packs=rule.default_booster_box_packs,
                default_bundle_packs=rule.default_bundle_packs,
            )
            ppp = compute_price_per_pack(price, pack_count)

            ship_cost = _apply_shipping(site, price)

            rows.append(ResultRow(
                timestamp=run_ts,
                franchise=rule.franchise,
                site_name=site.name,
                product_name=title or "Unknown",
                set_name=rule.name,
                product_type=base_product_type,
                sku_or_url=url,
                price=price,
                currency=site.currency,
                in_stock=in_stock,
                shipping_if_available=ship_cost,
                condition="sealed",
                variant_name=None,
                seal_status="sealed",
                unit_type="box",
                boxes_per_case=None,
                pack_count=pack_count,
                price_per_pack=ppp,
                notes=notes or "html",
            ))
            matched_rows += 1

        except Exception as e:
            logger.exception("Failed scraping %s (%s): %s", site.name, url, e)
            near_misses.append({
                "site_name": site.name,
                "title": "",
                "reason": f"error:{e}",
                "url": url,
            })

    out_rows: List[dict] = []
    for r in rows:
        d = r.to_dict()
        ship = d.get("shipping_if_available")
        d["landed_price"] = compute_landed_price(d.get("price"), ship)
        d["landed_price_per_pack"] = compute_landed_price_per_pack(d.get("price"), ship, d.get("pack_count"))
        out_rows.append(d)

    coverage = {
        "site_name": site.name,
        "discovered_urls": len(discovered_urls),
        "processed_urls": processed_urls,
        "matched_rows": matched_rows,
        "keyword_hits_but_filtered": keyword_hits_but_filtered,
        "unknown_product_type": unknown_product_type,
    }

    return out_rows, coverage, near_misses
