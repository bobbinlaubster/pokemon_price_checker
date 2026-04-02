from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class PackFreshAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "pack_fresh"
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
        "tin",
        "mini tin",
        "accessory pouch",
        "surprise box",
    )
