from abc import ABC, abstractmethod

from src.site_adapters.models import ScrapeContext, SiteScrapeResult


class BaseSiteAdapter(ABC):
    @abstractmethod
    def supports(self, site) -> bool:
        raise NotImplementedError

    @abstractmethod
    def scrape(self, context: ScrapeContext) -> SiteScrapeResult:
        raise NotImplementedError
