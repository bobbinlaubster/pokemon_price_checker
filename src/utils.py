import logging
import re
from typing import Any, Dict
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def parse_price(text: str):
    """
    Extract a float from messy price strings like:
      "Regular price $120.00 USD Sale price $79.00 USD"
    We prefer the *last* number (usually the sale price).
    """
    if not text:
        return None

    cleaned = text.replace(",", "")
    matches = re.findall(r"(\d+(\.\d{1,2})?)", cleaned)
    if not matches:
        return None

    try:
        return float(matches[-1][0])
    except ValueError:
        return None


def get_json_path(data: Dict[str, Any], path: str):
    """
    Simple dot-path getter: "product.price" -> data["product"]["price"].
    Returns None if missing.
    """
    if not path:
        return None
    cur: Any = data
    for part in path.split("."):
        part = part.strip()
        if not part:
            continue
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def shopify_handle_from_product_url(url: str):
    """
    Extract Shopify product handle from URLs like:
      https://domain.com/products/handle
      https://domain.com/collections/all/products/handle?variant=...
    """
    try:
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        if "products" in parts:
            idx = parts.index("products")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        return None
    return None


def shopify_products_js_url(product_url: str):
    """
    Convert product page URL to Shopify JSON:
      https://domain.com/products/handle -> https://domain.com/products/handle.js
    """
    handle = shopify_handle_from_product_url(product_url)
    if not handle:
        return None
    parsed = urlparse(product_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/products/{handle}.js"


def absolutize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)
