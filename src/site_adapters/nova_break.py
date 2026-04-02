from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class NovaBreakAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "nova_break"
    default_title_exclude_keywords = (
        "premium collection",
        "ultra premium",
        "super premium",
        "collection box",
        "figure collection",
        "binder collection",
        "playmat collection",
        "starter deck",
        "battle deck",
        "theme deck",
        "deck",
        "tin",
        "mini tin",
        "accessory pouch",
        "surprise box",
    )
