from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class DotsAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "dots"
    default_title_exclude_keywords = (
        "premium collection",
        "figure collection",
        "collection box",
        "tin",
    )
