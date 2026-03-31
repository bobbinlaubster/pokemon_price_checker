import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ---- TCGplayer endpoints (per official docs) ----
TOKEN_URL = "https://api.tcgplayer.com/token"
CATALOG_PRODUCTS_URL = "https://api.tcgplayer.com/catalog/products"
PRICING_PRODUCTS_URL = "https://api.tcgplayer.com/pricing/product/{}"  # CSV list of productIds

# Pokémon categoryId on TCGplayer is typically 3 (as used commonly in integrations),
# but if you ever find it differs for your account/environment, you can override via env var.
DEFAULT_POKEMON_CATEGORY_ID = int(os.environ.get("TCGPLAYER_POKEMON_CATEGORY_ID", "3"))

# ProductTypes are not strictly required, but can help narrow search.
DEFAULT_PRODUCT_TYPES = os.environ.get("TCGPLAYER_PRODUCT_TYPES", "Sealed Products")


class TCGplayerError(Exception):
    pass


@dataclass
class TCGplayerAuth:
    access_token: str
    expires_at_epoch: float


class TCGplayerClient:
    """
    Minimal TCGplayer API client for:
      - OAuth token (client credentials)
      - Product search (catalog)
      - Pricing lookup (market baseline)

    Required env vars:
      - TCGPLAYER_PUBLIC_KEY
      - TCGPLAYER_PRIVATE_KEY

    Optional env vars:
      - TCGPLAYER_POKEMON_CATEGORY_ID (default 3)
      - TCGPLAYER_PRODUCT_TYPES (default "Sealed Products")
      - TCGPLAYER_TIMEOUT_SECONDS (default 20)
    """

    def __init__(self):
        self.public_key = os.environ.get("TCGPLAYER_PUBLIC_KEY")
        self.private_key = os.environ.get("TCGPLAYER_PRIVATE_KEY")

        self.timeout_seconds = int(os.environ.get("TCGPLAYER_TIMEOUT_SECONDS", "20"))

        self.category_id = DEFAULT_POKEMON_CATEGORY_ID
        self.product_types = DEFAULT_PRODUCT_TYPES

        self._auth: Optional[TCGplayerAuth] = None

    def available(self) -> bool:
        return bool(self.public_key and self.private_key)

    # -------------------------
    # Auth / Token
    # -------------------------
    def _get_token(self) -> str:
        if not self.available():
            raise TCGplayerError("Missing TCGPLAYER_PUBLIC_KEY/TCGPLAYER_PRIVATE_KEY env vars.")

        now = time.time()
        if self._auth and now < (self._auth.expires_at_epoch - 60):
            return self._auth.access_token

        data = {
            "grant_type": "client_credentials",
            "client_id": self.public_key,
            "client_secret": self.private_key,
        }

        resp = self._request("POST", TOKEN_URL, data=data, is_token_call=True)
        js = resp.json()

        token = js.get("access_token")
        expires_in = js.get("expires_in", 3600)

        if not token:
            raise TCGplayerError(f"Token response missing access_token: {js}")

        self._auth = TCGplayerAuth(
            access_token=token,
            expires_at_epoch=now + int(expires_in),
        )
        return token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"bearer {self._get_token()}",
            "Accept": "application/json",
        }

    # -------------------------
    # HTTP helper with retries
    # -------------------------
    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        is_token_call: bool = False,
        max_attempts: int = 4,
    ) -> requests.Response:
        """
        Very small retry loop:
          - honors Retry-After on 429
          - backs off on 5xx
        """
        headers = {"Accept": "application/json"} if is_token_call else self._headers()

        backoff = 1
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )

                # Rate limit
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_s = int(retry_after) if (retry_after and str(retry_after).strip().isdigit()) else 10
                    logger.warning("TCGplayer 429 rate limit. Sleeping %ss then retrying (%s/%s).", sleep_s, attempt, max_attempts)
                    time.sleep(sleep_s)
                    continue

                # Server errors
                if 500 <= resp.status_code <= 599:
                    logger.warning("TCGplayer %s server error. Backing off %ss (%s/%s).", resp.status_code, backoff, attempt, max_attempts)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 16)
                    continue

                # Client errors (except token call; token call can be 400 if keys wrong)
                if resp.status_code >= 400:
                    # Provide more detail for debugging
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text[:500]
                    raise TCGplayerError(f"HTTP {resp.status_code} for {url} | {body}")

                return resp

            except Exception as e:
                last_exc = e
                if attempt < max_attempts:
                    logger.warning("TCGplayer request failed (%s/%s): %s", attempt, max_attempts, e)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 16)
                    continue
                break

        raise TCGplayerError(f"TCGplayer request failed after retries: {last_exc}")

    # -------------------------
    # Catalog search
    # -------------------------
    def search_product_ids(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        product_types: Optional[str] = None,
    ) -> List[int]:
        """
        Search for Pokémon sealed products matching query.
        Returns productIds.
        """
        if not query or not query.strip():
            return []

        params = {
            "categoryId": self.category_id,
            "limit": int(limit),
            "offset": int(offset),
            "q": query.strip(),
        }

        # Narrow by productTypes if configured
        pt = product_types if product_types is not None else self.product_types
        if pt:
            params["productTypes"] = pt

        resp = self._request("GET", CATALOG_PRODUCTS_URL, params=params)
        js = resp.json()

        results = js.get("results") or []
        out: List[int] = []
        for r in results:
            pid = r.get("productId")
            if pid is None:
                continue
            try:
                out.append(int(pid))
            except Exception:
                continue
        return out

    def search_products(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        product_types: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return the full product objects from catalog search.
        """
        params = {
            "categoryId": self.category_id,
            "limit": int(limit),
            "offset": int(offset),
            "q": query.strip(),
        }
        pt = product_types if product_types is not None else self.product_types
        if pt:
            params["productTypes"] = pt

        resp = self._request("GET", CATALOG_PRODUCTS_URL, params=params)
        js = resp.json()
        return js.get("results") or []

    # -------------------------
    # Pricing
    # -------------------------
    def get_prices_for_product_ids(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Returns pricing rows for each productId.
        Each row can include:
          - productId
          - lowPrice / midPrice / highPrice / marketPrice
          - directLowPrice
          - subTypeName (e.g., 'Normal', 'Foil') depending on product category
        """
        if not product_ids:
            return []

        # TCGplayer pricing endpoint accepts comma-separated ids.
        ids_csv = ",".join(str(int(x)) for x in product_ids)
        url = PRICING_PRODUCTS_URL.format(ids_csv)

        resp = self._request("GET", url)
        js = resp.json()
        return js.get("results") or []

    def get_best_market_price(self, product_ids: List[int]) -> Optional[float]:
        """
        Convenience: returns the lowest non-null marketPrice among results.
        """
        rows = self.get_prices_for_product_ids(product_ids)
        market_prices = []
        for r in rows:
            mp = r.get("marketPrice")
            if mp is None:
                continue
            try:
                market_prices.append(float(mp))
            except Exception:
                continue
        return min(market_prices) if market_prices else None

    # -------------------------
    # Baseline helpers for your script
    # -------------------------
    def build_market_baseline_rows_for_sets(
        self,
        set_rules: List[Any],
        *,
        per_set_limit: int = 3,
        price_field: str = "marketPrice",
    ) -> List[Dict[str, Any]]:
        """
        Helper to produce "baseline rows" aligned to your existing output schema.

        set_rules: list of SetRule from src/sets.py
        per_set_limit: how many catalog products to consider per set query
        price_field: marketPrice | lowPrice | midPrice | highPrice
        """
        out: List[Dict[str, Any]] = []
        if not self.available():
            return out

        for rule in set_rules:
            # Build a query that tends to hit sealed products.
            # Example: "Prismatic Evolutions Booster Box"
            hint = rule.allowed_product_types[0] if getattr(rule, "allowed_product_types", []) else ""
            query = f"{rule.name} {hint}".strip()

            try:
                product_ids = self.search_product_ids(query, limit=per_set_limit)
                if not product_ids:
                    continue

                price_rows = self.get_prices_for_product_ids(product_ids)

                # Create baseline rows (one per pricing row) so you can compare.
                for pr in price_rows:
                    pid = pr.get("productId")
                    val = pr.get(price_field)

                    try:
                        price_val = float(val) if val is not None else None
                    except Exception:
                        price_val = None

                    out.append({
                        "timestamp": datetime_utc_iso(),
                        "site_name": "TCGplayer Market Baseline",
                        "product_name": f"TCGplayer {price_field} (productId={pid})",
                        "set_name": rule.name,
                        "product_type": "Market Baseline",
                        "sku_or_url": f"tcgplayer://product/{pid}",
                        "price": price_val,
                        "currency": "USD",
                        "in_stock": True,
                        "shipping_if_available": None,
                        "condition": "sealed",
                        "pack_count": None,
                        "price_per_pack": None,
                        "landed_price": price_val,
                        "landed_price_per_pack": None,
                        "notes": "tcgplayer_api",
                    })
            except Exception as e:
                logger.warning("TCGplayer baseline failed for %s: %s", getattr(rule, "name", "unknown"), e)

        return out


def datetime_utc_iso() -> str:
    # Small helper to avoid importing datetime everywhere in this module
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

