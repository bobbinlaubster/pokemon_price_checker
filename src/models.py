from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ResultRow:
    timestamp: str
    franchise: str

    site_name: str
    product_name: str
    set_name: str
    product_type: str
    sku_or_url: str

    price: Optional[float]
    currency: str
    in_stock: Optional[bool]
    shipping_if_available: Optional[float]

    condition: str

    variant_name: Optional[str] = None
    seal_status: Optional[str] = None
    unit_type: Optional[str] = None
    boxes_per_case: Optional[int] = None

    pack_count: Optional[int] = None
    price_per_pack: Optional[float] = None
    notes: str = ""

    def to_dict(self):
        return asdict(self)
