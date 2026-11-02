import re
from collections.abc import Iterable
from sqlalchemy import or_

from src.models import FoodItem, FoodPortion

AVOID_ALIASES = {
    "dairy": {"milk", "cheese", "yogurt", "yoghurt", "butter", "cream", "whey", "kefir"},
    "gluten": {"wheat", "bread", "pasta", "oat", "barley", "rye", "couscous", "cereal", "noodle", "flour"},
    "nut": {"peanut", "almond", "cashew", "walnut", "pecan", "hazelnut", "pistachio"},
    "seafood": {"fish", "shrimp", "prawn", "crab", "lobster", "salmon", "tuna", "sardine", "cod"},
    "shellfish": {"shrimp", "prawn", "crab", "lobster", "oyster", "mussel", "clam"},
    "meat": {"beef", "pork", "lamb", "chicken", "turkey", "bacon", "sausage", "ham"},
    "soy": {"tofu", "tempeh", "edamame", "miso"},
}


def _word_in_text(word: str, text: str) -> bool:
    """
    Return True if `word` appears as a whole token in `text`.
    Tokens are separated by any non-alphanumeric character.
    e.g. 'butter' in 'peanut butter' -> True
         'butter' in 'buttermilk'    -> False
    """
    pattern = r"(?<![\w])" + re.escape(word) + r"(?![\w])"
    return bool(re.search(pattern, text))


def parse_avoid_terms(text: str | None) -> list[str]:
    if not text:
        return []
    parts = re.split(r"[,;\n]+| and ", text.lower())
    return [p.strip() for p in parts if p and p.strip()]


def matches_avoid(food_name: str, terms: Iterable[str]) -> bool:
    lower_name = food_name.lower()
    for raw in terms:
        for term in parse_avoid_terms(raw) if any(sep in raw for sep in (",", ";", "\n", " and ")) else [raw.strip().lower()]:
            if not term:
                continue
            if len(term) > 3 and term.endswith("s") and not term.endswith(("ss", "us", "is")):
                singular = term[:-1]
            else:
                singular = term
            variants = {term, singular, f"{term}s"}
            for alias in AVOID_ALIASES.get(singular, ()):
                variants.add(alias)
                variants.add(f"{alias}s")
            for variant in variants:
                if variant and _word_in_text(variant, lower_name):
                    return True
    return False


def visible_food(user_id: int, include_hidden: bool = False) -> list:
    """WHERE conditions for foods a user may see: shared catalog + their own."""
    conds = [
        FoodItem.deleted_at.is_(None),
        or_(FoodItem.user_id.is_(None), FoodItem.user_id == user_id),
    ]
    if not include_hidden:
        conds.append(FoodItem.kind != "quick")
    return conds


def visible_portion(user_id: int):
    return or_(FoodPortion.user_id.is_(None), FoodPortion.user_id == user_id)


