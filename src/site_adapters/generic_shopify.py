import logging
import time
from typing import Dict, List

from bs4 import BeautifulSoup

from src.normalize import is_allowed_language, normalize_title
from src.sets import match_set
from src.site_adapters.base import BaseSiteAdapter
from src.site_adapters.models import ScrapeContext, SiteScrapeResult
from src.site_adapters.shopify_helpers import (
    build_standard_row,
    derive_variant_offer,
    discover_product_urls,
    fetch_shopify_js_variants,
    serialize_rows,
    title_excluded,
)
from src.utils import parse_price

logger = logging.getLogger(__name__)


class GenericShopifyCollectionAdapter(BaseSiteAdapter):
    adapter_name = "shopify_collection"

    def supports(self, site) -> bool:
        return getattr(site, "adapter", "").strip().lower() == self.adapter_name

    def scrape(self, context: ScrapeContext) -> SiteScrapeResult:
        site = context.site
        rows = []
        near_misses: List[Dict[str, str]] = []

        discovered_urls: List[str] = []
        processed_urls = 0
        matched_rows = 0
        keyword_hits_but_filtered = 0
        unknown_product_type = 0

        for collection_url in site.collection_pages:
            discovered_urls.extend(
                discover_product_urls(
                    fetcher=context.fetcher,
                    site=site,
                    collection_url=collection_url,
                    max_pages=site.max_collection_pages,
                    max_urls_per_site=context.max_urls_per_site,
                )
            )

        discovered_urls = list(dict.fromkeys(discovered_urls))
        if context.max_products:
            discovered_urls = discovered_urls[:context.max_products]

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
                        js = fetch_shopify_js_variants(context.fetcher, url)
                        title = str(js.get("title", "")).strip() or title
                        notes = "shopify_js"
                    except Exception as exc:
                        notes = f"shopify_js_failed:{exc}"
                        js = None

                if not title or js is None:
                    response = context.fetcher.get(url)
                    soup = BeautifulSoup(response.text, "lxml")
                    if not title:
                        heading = soup.select_one("h1")
                        title = heading.get_text(strip=True) if heading else url
                else:
                    soup = None

                if title_excluded(site, title):
                    keyword_hits_but_filtered += 1
                    near_misses.append({
                        "site_name": site.name,
                        "title": title,
                        "reason": "filtered_by_site_title_keyword",
                        "url": url,
                    })
                    continue

                if not is_allowed_language(title):
                    continue

                _, base_product_type = normalize_title(title)
                if base_product_type == "Unknown":
                    unknown_product_type += 1

                rule = match_set(title, context.set_rules)
                if not rule:
                    continue

                if js is not None:
                    price, in_stock = derive_variant_offer(js.get("variants") or [])

                if price is None or in_stock is None:
                    if soup is None:
                        response = context.fetcher.get(url)
                        soup = BeautifulSoup(response.text, "lxml")
                    if price is None:
                        price_node = soup.select_one(
                            "span.price-item--sale, span.price-item--regular, .price__regular .price-item, .price .money, [data-product-price]"
                        )
                        price = parse_price(price_node.get_text(" ", strip=True) if price_node else "")
                    if in_stock is None:
                        in_stock = "sold out" not in soup.get_text(" ", strip=True).lower()

                if rule.allowed_product_types and base_product_type not in rule.allowed_product_types:
                    keyword_hits_but_filtered += 1
                    near_misses.append({
                        "site_name": site.name,
                        "title": title,
                        "reason": "filtered_by_product_type",
                        "url": url,
                    })
                    continue

                rows.append(
                    build_standard_row(
                        site=site,
                        run_ts=context.run_ts,
                        title=title,
                        rule=rule,
                        product_url=url,
                        price=price,
                        in_stock=in_stock,
                        notes=notes,
                    )
                )
                matched_rows += 1
            except Exception as exc:
                logger.exception("Failed scraping %s (%s): %s", site.name, url, exc)
                near_misses.append({
                    "site_name": site.name,
                    "title": "",
                    "reason": f"error:{exc}",
                    "url": url,
                })

        return SiteScrapeResult(
            rows=serialize_rows(rows),
            coverage={
                "site_name": site.name,
                "discovered_urls": len(discovered_urls),
                "processed_urls": processed_urls,
                "matched_rows": matched_rows,
                "keyword_hits_but_filtered": keyword_hits_but_filtered,
                "unknown_product_type": unknown_product_type,
            },
            near_misses=near_misses,
        )
