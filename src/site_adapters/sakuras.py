import logging
from typing import Dict, List

from src.normalize import is_allowed_language, normalize_title
from src.sets import match_set
from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter
from src.site_adapters.models import ScrapeContext, SiteScrapeResult
from src.site_adapters.shopify_helpers import (
    build_standard_row,
    discover_product_urls,
    sakura_variant_rows,
    serialize_rows,
)

logger = logging.getLogger(__name__)


class SakurasAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "sakuras"

    def scrape(self, context: ScrapeContext) -> SiteScrapeResult:
        site = context.site
        rows = []
        near_misses: List[Dict[str, str]] = []

        discovered_urls: List[str] = []
        for collection_url in self.collection_pages(site):
            discovered_urls.extend(
                discover_product_urls(
                    fetcher=context.fetcher,
                    site=site,
                    collection_url=collection_url,
                    max_pages=self.max_collection_pages(site),
                    max_urls_per_site=context.max_urls_per_site,
                )
            )

        discovered_urls = self.postprocess_discovered_urls(list(dict.fromkeys(discovered_urls)))
        if context.max_products:
            discovered_urls = discovered_urls[:context.max_products]

        processed_urls = 0
        matched_rows = 0
        keyword_hits_but_filtered = 0
        unknown_product_type = 0
        total = len(discovered_urls)

        for url in discovered_urls:
            processed_urls += 1
            print(f"[HB] [{site.name}] {processed_urls}/{total} {url}")
            try:
                title, price, in_stock, notes, js, _soup = self.resolve_title_and_offer(context, url)

                if self.should_skip_title(site, title):
                    keyword_hits_but_filtered += 1
                    near_misses.append({"site_name": site.name, "title": title, "reason": "filtered_by_site_title_keyword", "url": url})
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
                    variant_rows = sakura_variant_rows(
                        site=site,
                        product_url=url,
                        run_ts=context.run_ts,
                        title=title,
                        rule=rule,
                        variants=js.get("variants") or [],
                    )
                    final_variant_rows = []
                    for variant_row in variant_rows:
                        if rule.allowed_product_types and variant_row.product_type not in rule.allowed_product_types:
                            keyword_hits_but_filtered += 1
                            near_misses.append({
                                "site_name": site.name,
                                "title": f"{title} [{variant_row.variant_name}]",
                                "reason": "filtered_by_product_type",
                                "url": url,
                            })
                            continue
                        final_variant_rows.append(variant_row)
                    rows.extend(final_variant_rows)
                    matched_rows += len(final_variant_rows)
                    continue

                if rule.allowed_product_types and base_product_type not in rule.allowed_product_types:
                    keyword_hits_but_filtered += 1
                    near_misses.append({"site_name": site.name, "title": title, "reason": "filtered_by_product_type", "url": url})
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
                near_misses.append({"site_name": site.name, "title": "", "reason": f"error:{exc}", "url": url})

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
