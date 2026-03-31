import re
from typing import Optional, Tuple


# ----------------------------
# Language Detection
# ----------------------------

EXCLUDED_LANG_KEYWORDS = [
    "korean",
    "german",
    "french",
    "italian",
    "spanish",
    "portuguese",
    "thai",
    "indonesian",
    "simplified chinese",
    "traditional chinese",
]

# Chinese sets you explicitly allow
ALLOWED_CHINESE_KEYWORDS = [
    "151",
    "gem",
    "9 colors",
    "9 colours",
    "9 color gathering",
    "9 colours gathering",
]


def is_allowed_language(title: str) -> bool:
    """
    Allow:
      - English (default)
      - Japanese
      - Chinese ONLY for certain sets (151 / gem / 9 colors gathering)
    """
    if not title:
        return False

    t = title.lower()

    # Japanese always allowed
    if "japanese" in t or "jp " in t or "(jp)" in t:
        return True

    # Explicit Chinese sets allowed
    if "chinese" in t:
        if any(k in t for k in ALLOWED_CHINESE_KEYWORDS):
            return True
        return False

    # Block other languages explicitly
    if any(lang in t for lang in EXCLUDED_LANG_KEYWORDS):
        return False

    # Default assume English if no language specified
    return True


# ----------------------------
# Product Type Detection
# ----------------------------

PRODUCT_TYPE_RULES = [
    ("ETB", r"\b(etb|elite trainer box)\b"),
    ("Booster Box", r"\b(booster box|booster display|display box)\b"),
    ("Booster Bundle", r"\b(booster bundle)\b"),
    ("Booster Pack", r"\b(booster pack|single pack|single booster|booster)\b"),
    ("Blister", r"\b(blister)\b"),
    ("Tin", r"\b(tin)\b"),
    ("Collection Box", r"\b(collection|premium collection)\b"),
]


def normalize_title(title: str) -> Tuple[str, str]:
    t = " ".join((title or "").split())
    t_lower = t.lower()

    product_type = "Unknown"
    for label, pattern in PRODUCT_TYPE_RULES:
        if re.search(pattern, t_lower, flags=re.IGNORECASE):
            product_type = label
            break

    return "Unknown", product_type


# ----------------------------
# Pack Count Logic
# ----------------------------

def infer_pack_count(
    title: str,
    product_type: str,
    *,
    region: Optional[str] = None,
    default_booster_box_packs: Optional[int] = None,
    default_bundle_packs: Optional[int] = None,
) -> Optional[int]:

    if not title:
        return None

    t = title.lower()

    # Explicit pack count
    m = re.search(r"\b(\d{1,3})\s*[- ]?\s*(pack|packs|booster packs|boosters)\b", t)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    pt = (product_type or "").lower()

    if "booster bundle" in pt:
        return default_bundle_packs or 6

    if "booster box" in pt:
        return default_booster_box_packs or (30 if (region or "").upper() == "JP" else 36)

    if "booster pack" in pt:
        return 1

    return None


def compute_price_per_pack(price: Optional[float], pack_count: Optional[int]) -> Optional[float]:
    if price is None or pack_count is None or pack_count <= 0:
        return None
    return round(float(price) / int(pack_count), 4)


def compute_landed_price(price: Optional[float], shipping_cost: Optional[float]) -> Optional[float]:
    if price is None:
        return None
    if shipping_cost is None:
        return float(price)
    return float(price) + float(shipping_cost)


def compute_landed_price_per_pack(
    price: Optional[float],
    shipping_cost: Optional[float],
    pack_count: Optional[int],
) -> Optional[float]:
    landed = compute_landed_price(price, shipping_cost)
    return compute_price_per_pack(landed, pack_count)
