from src.site_adapters.generic_shopify import BaseGenericShopifySiteAdapter


class PokemonPlugAdapter(BaseGenericShopifySiteAdapter):
    adapter_name = "pokemon_plug"
    default_title_exclude_keywords = (
        "premium collection",
        "collection box",
        "tin",
        "blister",
    )
