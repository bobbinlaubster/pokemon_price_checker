from pathlib import Path
from types import SimpleNamespace

from src.config import load_config
from src.site_adapters.generic_shopify import GenericShopifyCollectionAdapter
from src.site_adapters.registry import get_site_adapter
from src.site_adapters.sakuras import SakurasAdapter
from src.site_adapters.shopify_helpers import derive_variant_offer, discover_product_urls, title_excluded


class FakeResponse:
    def __init__(self, text="", json_data=None):
        self.text = text
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class FakeFetcher:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url):
        value = self.responses[url]
        if isinstance(value, FakeResponse):
            return value
        return FakeResponse(text=value)


def fixture_text(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def test_load_config_supports_explicit_adapter():
    cfg = load_config("sites.yaml")
    sakuras = next(site for site in cfg.sites if site.name == "Sakuras Card Shop")
    nova = next(site for site in cfg.sites if site.name == "Nova Break")

    assert sakuras.adapter == "sakuras"
    assert nova.adapter == "shopify_collection"


def test_registry_returns_expected_adapter_classes():
    sakuras_site = SimpleNamespace(adapter="sakuras", mode="shopify_collection")
    generic_site = SimpleNamespace(adapter="shopify_collection", mode="shopify_collection")

    assert isinstance(get_site_adapter(sakuras_site), SakurasAdapter)
    assert isinstance(get_site_adapter(generic_site), GenericShopifyCollectionAdapter)


def test_discover_product_urls_deduplicates_and_absolutizes():
    site = SimpleNamespace(throttle_seconds=0)
    fetcher = FakeFetcher({
        "https://example.com/collections/test?page=1": fixture_text("collection_page.html"),
    })

    urls = discover_product_urls(
        fetcher=fetcher,
        site=site,
        collection_url="https://example.com/collections/test",
        max_pages=1,
        max_urls_per_site=10,
    )

    assert urls == [
        "https://example.com/products/one",
        "https://example.com/products/two",
    ]


def test_derive_variant_offer_prefers_cheapest_available_non_case_variant():
    price, in_stock = derive_variant_offer(
        [
            {"title": "Booster Box", "price": 11999, "available": True},
            {"title": "Booster Box Case", "price": 59999, "available": True},
            {"title": "Booster Box", "price": 10999, "available": True},
        ]
    )

    assert price == 109.99
    assert in_stock is True


def test_title_excluded_uses_site_keywords_case_insensitively():
    site = SimpleNamespace(title_exclude_keywords=["premium collection", "starter deck"])
    assert title_excluded(site, "Charizard Premium Collection") is True
    assert title_excluded(site, "Journey Together Elite Trainer Box") is False
