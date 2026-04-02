from src.site_adapters.base import BaseSiteAdapter
from src.site_adapters.generic_shopify import GenericShopifyCollectionAdapter
from src.site_adapters.sakuras import SakurasAdapter


REGISTERED_SITE_ADAPTERS: list[BaseSiteAdapter] = [
    SakurasAdapter(),
    GenericShopifyCollectionAdapter(),
]


def get_site_adapter(site) -> BaseSiteAdapter:
    adapter_name = getattr(site, "adapter", getattr(site, "mode", "unknown"))
    for adapter in REGISTERED_SITE_ADAPTERS:
        if adapter.supports(site):
            return adapter
    raise ValueError(f"No site adapter registered for adapter: {adapter_name}")
