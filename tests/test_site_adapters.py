from pathlib import Path
from types import SimpleNamespace

from src.config import load_config
from src.site_adapters.dots import DotsAdapter
from src.site_adapters.flipside_gaming import FlipsideGamingAdapter
from src.site_adapters.generic_shopify import GenericShopifyCollectionAdapter
from src.site_adapters.grandads import GrandadsAdapter
from src.site_adapters.nova_break import NovaBreakAdapter
from src.site_adapters.pack_fresh import PackFreshAdapter
from src.site_adapters.pokemon_plug import PokemonPlugAdapter
from src.site_adapters.registry import get_site_adapter
from src.site_adapters.safari_zone import SafariZoneAdapter
from src.site_adapters.sakuras import SakurasAdapter
from src.site_adapters.shopify_helpers import derive_variant_offer, discover_product_urls, title_excluded
from src.site_adapters.tcg_stadium import TCGStadiumAdapter


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
    assert nova.adapter == "nova_break"


def test_registry_returns_expected_adapter_classes_for_sample_sites():
    sakuras_site = SimpleNamespace(adapter="sakuras", mode="shopify_collection")
    dots_site = SimpleNamespace(adapter="dots", mode="shopify_collection")
    pack_fresh_site = SimpleNamespace(adapter="pack_fresh", mode="shopify_collection")
    generic_site = SimpleNamespace(adapter="shopify_collection", mode="shopify_collection")

    assert isinstance(get_site_adapter(sakuras_site), SakurasAdapter)
    assert isinstance(get_site_adapter(dots_site), DotsAdapter)
    assert isinstance(get_site_adapter(pack_fresh_site), PackFreshAdapter)
    assert isinstance(get_site_adapter(generic_site), GenericShopifyCollectionAdapter)


def test_all_configured_sites_have_site_specific_adapters():
    cfg = load_config("sites.yaml")
    expected_classes = {
        "Sakuras Card Shop": SakurasAdapter,
        "Dots Card Shop": DotsAdapter,
        "Grandads Cards": GrandadsAdapter,
        "Safari Zone": SafariZoneAdapter,
        "TCG Stadium": TCGStadiumAdapter,
        "Flipside Gaming": FlipsideGamingAdapter,
        "PokemonPlug": PokemonPlugAdapter,
        "Pack Fresh": PackFreshAdapter,
        "Nova Break": NovaBreakAdapter,
    }

    for site in cfg.sites:
        adapter = get_site_adapter(site)
        assert isinstance(adapter, expected_classes[site.name])


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
