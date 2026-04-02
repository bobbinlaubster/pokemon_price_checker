from src.site_adapters.models import ScrapeContext
from src.site_adapters.registry import get_site_adapter


def scrape_site(fetcher, site, max_products, run_ts, set_rules, max_urls_per_site):
    context = ScrapeContext(
        fetcher=fetcher,
        site=site,
        max_products=max_products,
        run_ts=run_ts,
        set_rules=set_rules,
        max_urls_per_site=max_urls_per_site,
    )
    result = get_site_adapter(site).scrape(context)
    return result.rows, result.coverage, result.near_misses
