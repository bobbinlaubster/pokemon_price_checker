from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class GrandadsAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "grandads"
    default_title_exclude_keywords = (
        "premium collection",
        "collection box",
        "tin",
        "blister",
    )
