from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class FlipsideGamingAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "flipside_gaming"
    force_shopify_js_fallback = False
    default_title_exclude_keywords = (
        "premium collection",
        "collection box",
        "tin",
        "blister",
        "sleeved booster",
    )
