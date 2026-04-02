from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class TCGStadiumAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "tcg_stadium"
    default_title_exclude_keywords = (
        "premium collection",
        "collection box",
        "tin",
        "blister",
    )
