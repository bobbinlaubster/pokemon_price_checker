from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class SafariZoneAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "safari_zone"
    default_title_exclude_keywords = (
        "premium collection",
        "collection box",
        "tin",
        "build & battle",
    )
