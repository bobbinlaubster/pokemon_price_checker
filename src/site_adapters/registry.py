from src.site_adapters.base import BaseSiteAdapter
from src.site_adapters.dots import DotsAdapter
from src.site_adapters.flipside_gaming import FlipsideGamingAdapter
from src.site_adapters.generic_shopify import GenericShopifyCollectionAdapter
from src.site_adapters.grandads import GrandadsAdapter
from src.site_adapters.nova_break import NovaBreakAdapter
from src.site_adapters.pack_fresh import PackFreshAdapter
from src.site_adapters.pokemon_plug import PokemonPlugAdapter
from src.site_adapters.safari_zone import SafariZoneAdapter
from src.site_adapters.sakuras import SakurasAdapter
from src.site_adapters.tcg_stadium import TCGStadiumAdapter


REGISTERED_SITE_ADAPTERS: list[BaseSiteAdapter] = [
    SakurasAdapter(),
    DotsAdapter(),
    GrandadsAdapter(),
    SafariZoneAdapter(),
    TCGStadiumAdapter(),
    FlipsideGamingAdapter(),
    PokemonPlugAdapter(),
    PackFreshAdapter(),
    NovaBreakAdapter(),
    GenericShopifyCollectionAdapter(),
]


def get_site_adapter(site) -> BaseSiteAdapter:
    adapter_name = getattr(site, "adapter", getattr(site, "mode", "unknown"))
    for adapter in REGISTERED_SITE_ADAPTERS:
        if adapter.supports(site):
            return adapter
    raise ValueError(f"No site adapter registered for adapter: {adapter_name}")
