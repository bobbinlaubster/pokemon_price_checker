from dataclasses import dataclass
from typing import List, Optional
import yaml


@dataclass
class SetRule:
    """
    Defines how a set should be detected and handled.
    """
    name: str
    keywords: List[str]
    allowed_product_types: List[str]

    franchise: str = "Pokemon"  # NEW: "Pokemon" | "One Piece" | etc.
    region: str = "EN"          # "EN" | "JP" (and CN exceptions handled in normalize.py)
    default_booster_box_packs: Optional[int] = None
    default_bundle_packs: Optional[int] = None


def load_sets(path: str) -> List[SetRule]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    rules: List[SetRule] = []
    for s in data.get("sets", []) or []:
        rules.append(
            SetRule(
                name=str(s.get("name", "")).strip(),
                keywords=[
                    str(k).strip().lower()
                    for k in (s.get("keywords") or [])
                    if str(k).strip()
                ],
                allowed_product_types=[
                    str(t).strip()
                    for t in (s.get("allowed_product_types") or [])
                    if str(t).strip()
                ],
                franchise=str(s.get("franchise", "Pokemon")).strip(),
                region=str(s.get("region", "EN")).strip().upper(),
                default_booster_box_packs=(
                    int(s["default_booster_box_packs"])
                    if s.get("default_booster_box_packs") is not None
                    else None
                ),
                default_bundle_packs=(
                    int(s["default_bundle_packs"])
                    if s.get("default_bundle_packs") is not None
                    else None
                ),
            )
        )

    return rules


def match_set(title: str, rules: List[SetRule]) -> Optional[SetRule]:
    """
    First match wins. Order in sets.yaml matters.
    """
    if not title:
        return None

    t = title.lower()
    for rule in rules:
        for kw in rule.keywords:
            if kw and kw in t:
                return rule
    return None
