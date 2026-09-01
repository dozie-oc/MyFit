from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from src.models import FoodItem, FoodPortion
from src.schemas import FoodSearchResult
from src.services.usda_client import USDAClient


# ============================================================
# USDA NUTRIENT IDS
# ============================================================

ENERGY_NUTRIENT_ID = 1008
PROTEIN_NUTRIENT_ID = 1003
FAT_NUTRIENT_ID = 1004
CARBOHYDRATE_NUTRIENT_ID = 1005


# ============================================================
# APPLICATION-LEVEL DATA STRUCTURES
# ============================================================


@dataclass(slots=True)
class NormalizedNutrients:
    """
    Nutritional values normalized to a 100g basis.
    """

    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float


@dataclass(slots=True)
class NormalizedPortion:
    """
    A USDA portion converted into an application-level portion.
    """

    name: str
    quantity: float
    unit: str
    gram_weight: float
    usda_measure_unit: str | None = None


@dataclass(slots=True)
class NormalizedFood:
    """
    Application-level representation of a USDA food before it is
    persisted in the database.
    """

    name: str
    usda_fdc_id: int
    usda_data_type: str | None

    nutrients: NormalizedNutrients
    portions: list[NormalizedPortion]


# ============================================================
# FOOD SERVICE
# ============================================================


class FoodService:
    """
    Application service responsible for food-related business logic.

    Responsibilities:

        USDA response
            ↓
        normalization
            ↓
        FoodItem / FoodPortion persistence
            ↓
        food and portion lookup
            ↓
        nutrition calculations

    The USDAClient is responsible only for HTTP communication.

    Database commits are intentionally NOT performed inside this
    service. The caller controls the transaction.
    """

    def __init__(
        self,
        session: Session,
        usda_client: USDAClient,
    ):
        self.session = session
        self.usda_client = usda_client

    # ============================================================
    # USDA SEARCH
    # ============================================================

    async def search_foods(
        self,
        query: str,
        *,
        page_size: int = 25,
        page_number: int = 1,
        data_types: list[str] | None = None,
    ) -> tuple[list[FoodSearchResult], int]:

        query = query.strip()

        if not query:
            raise ValueError(
                "Food search query cannot be empty."
            )

        if page_size < 1 or page_size > 50:
            raise ValueError(
                "Page size must be between 1 and 50."
            )

        if page_number < 1:
            raise ValueError(
                "Page number must be greater than zero."
            )

        response = await self.usda_client.search_foods(
            query,
            page_size=page_size,
            page_number=page_number,
            data_types=data_types,
        )

        results: list[FoodSearchResult] = []

        for food in response.get("foods", []):
            if not isinstance(food, dict):
                continue

            fdc_id = food.get("fdcId")

            description = (
                food.get("description")
                or ""
            ).strip()

            if fdc_id is None or not description:
                continue

            try:
                fdc_id = int(fdc_id)
            except (TypeError, ValueError):
                continue

            results.append(
                FoodSearchResult(
                    fdc_id=fdc_id,
                    name=description,
                    data_type=food.get("dataType"),
                )
            )

        try:
            total_hits = int(
                response.get(
                    "totalHits",
                    len(results),
                )
            )
        except (TypeError, ValueError):
            total_hits = len(results)

        return results, total_hits

    # ============================================================
    # USDA → APPLICATION NORMALIZATION
    # ============================================================

    @staticmethod
    def _extract_nutrients(
        food_data: dict,
    ) -> NormalizedNutrients:

        values: dict[int, float] = {
            ENERGY_NUTRIENT_ID: 0.0,
            PROTEIN_NUTRIENT_ID: 0.0,
            CARBOHYDRATE_NUTRIENT_ID: 0.0,
            FAT_NUTRIENT_ID: 0.0,
        }

        for nutrient in food_data.get(
            "foodNutrients",
            [],
        ):
            if not isinstance(nutrient, dict):
                continue

            nutrient_id = nutrient.get("nutrientId")

            if nutrient_id not in values:
                continue

            amount = nutrient.get("value")

            if amount is None:
                continue

            try:
                values[nutrient_id] = max(
                    0.0,
                    float(amount),
                )
            except (TypeError, ValueError):
                continue

        return NormalizedNutrients(
            calories_per_100g=values[
                ENERGY_NUTRIENT_ID
            ],
            protein_per_100g=values[
                PROTEIN_NUTRIENT_ID
            ],
            carbs_per_100g=values[
                CARBOHYDRATE_NUTRIENT_ID
            ],
            fat_per_100g=values[
                FAT_NUTRIENT_ID
            ],
        )

    @staticmethod
    def _format_quantity(
        amount: float,
    ) -> str:

        if amount.is_integer():
            return str(int(amount))

        return f"{amount:g}"

    @classmethod
    def _extract_portions(
        cls,
        food_data: dict,
    ) -> list[NormalizedPortion]:

        portions: list[NormalizedPortion] = []

        seen: set[tuple[str, float, float]] = set()

        for portion in food_data.get(
            "foodPortions",
            [],
        ):
            if not isinstance(portion, dict):
                continue

            raw_gram_weight = portion.get(
                "gramWeight"
            )

            try:
                gram_weight = float(
                    raw_gram_weight
                )
            except (TypeError, ValueError):
                continue

            if gram_weight <= 0:
                continue

            raw_amount = portion.get(
                "amount"
            )

            try:
                amount = (
                    float(raw_amount)
                    if raw_amount is not None
                    else 1.0
                )
            except (TypeError, ValueError):
                amount = 1.0

            if amount <= 0:
                amount = 1.0

            modifier = str(
                portion.get("modifier")
                or ""
            ).strip()

            measure_unit = (
                portion.get("measureUnit")
                or {}
            )

            if isinstance(measure_unit, dict):
                unit_name = (
                    measure_unit.get("name")
                    or measure_unit.get("abbreviation")
                    or ""
                )
            else:
                unit_name = ""

            if not unit_name:
                unit_name = str(
                    portion.get(
                        "measureUnitName"
                    )
                    or ""
                ).strip()

            if not unit_name:
                unit_name = modifier or "serving"

            quantity_text = cls._format_quantity(
                amount
            )

            display_parts = [
                quantity_text,
                modifier,
                unit_name,
            ]

            display_name = " ".join(
                part
                for part in display_parts
                if part
            ).strip()

            if not display_name:
                display_name = "serving"

            duplicate_key = (
                display_name.lower(),
                round(amount, 6),
                round(gram_weight, 6),
            )

            if duplicate_key in seen:
                continue

            seen.add(duplicate_key)

            portions.append(
                NormalizedPortion(
                    name=display_name,
                    quantity=amount,
                    unit=unit_name,
                    gram_weight=gram_weight,
                    usda_measure_unit=unit_name,
                )
            )

        return portions

    @classmethod
    def normalize_usda_food(
        cls,
        food_data: dict,
    ) -> NormalizedFood:

        fdc_id = food_data.get("fdcId")

        if fdc_id is None:
            raise ValueError(
                "USDA food response does not contain an fdcId."
            )

        try:
            fdc_id = int(fdc_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "USDA food contains an invalid fdcId."
            ) from exc

        description = str(
            food_data.get("description")
            or ""
        ).strip()

        if not description:
            raise ValueError(
                "USDA food does not contain a usable description."
            )

        nutrients = cls._extract_nutrients(
            food_data
        )

        portions = cls._extract_portions(
            food_data
        )

        return NormalizedFood(
            name=description,
            usda_fdc_id=fdc_id,
            usda_data_type=food_data.get(
                "dataType"
            ),
            nutrients=nutrients,
            portions=portions,
        )

    # ============================================================
    # DATABASE LOOKUPS
    # ============================================================

    def get_local_food(
        self,
        food_id: int,
    ) -> FoodItem | None:

        return self.session.exec(
            select(FoodItem).where(
                FoodItem.id == food_id,
                FoodItem.deleted_at.is_(None),
            )
        ).first()

    def get_local_food_by_usda_id(
        self,
        fdc_id: int,
    ) -> FoodItem | None:

        return self.session.exec(
            select(FoodItem).where(
                FoodItem.usda_fdc_id == fdc_id,
                FoodItem.deleted_at.is_(None),
            )
        ).first()

    def get_food_by_usda_id(
        self,
        fdc_id: int,
    ) -> FoodItem | None:

        return self.session.exec(
            select(FoodItem).where(
                FoodItem.usda_fdc_id == fdc_id,
            )
        ).first()

    def get_food_portion(
        self,
        portion_id: int,
    ) -> FoodPortion | None:

        return self.session.exec(
            select(FoodPortion).where(
                FoodPortion.id == portion_id,
            )
        ).first()

    def get_food_portion_for_food(
        self,
        *,
        food_id: int,
        portion_id: int,
    ) -> FoodPortion | None:

        return self.session.exec(
            select(FoodPortion).where(
                FoodPortion.id == portion_id,
                FoodPortion.food_id == food_id,
            )
        ).first()

    # ============================================================
    # USDA IMPORT
    # ============================================================

    async def import_usda_food(
        self,
        fdc_id: int,
    ) -> FoodItem:

        if fdc_id <= 0:
            raise ValueError(
                "USDA FDC ID must be greater than zero."
            )

        existing_food = self.get_food_by_usda_id(
            fdc_id
        )

        # Active food already exists.
        if (
            existing_food is not None
            and existing_food.deleted_at is None
        ):
            return existing_food

        food_data = await self.usda_client.get_food(
            fdc_id
        )

        normalized = self.normalize_usda_food(
            food_data
        )

        if existing_food is not None:
            # Restore and refresh a soft-deleted food.
            food = existing_food

            food.name = normalized.name

            food.usda_data_type = (
                normalized.usda_data_type
            )

            food.calories_per_100g = (
                normalized.nutrients.calories_per_100g
            )

            food.protein_per_100g = (
                normalized.nutrients.protein_per_100g
            )

            food.carbs_per_100g = (
                normalized.nutrients.carbs_per_100g
            )

            food.fat_per_100g = (
                normalized.nutrients.fat_per_100g
            )

            food.deleted_at = None

            food.updated_at = datetime.now(
                timezone.utc
            )

            existing_portions = self.session.exec(
                select(FoodPortion).where(
                    FoodPortion.food_id == food.id
                )
            ).all()

            for portion in existing_portions:
                self.session.delete(portion)

        else:
            food = FoodItem(
                name=normalized.name,
                usda_fdc_id=normalized.usda_fdc_id,
                usda_data_type=normalized.usda_data_type,
                calories_per_100g=(
                    normalized.nutrients.calories_per_100g
                ),
                protein_per_100g=(
                    normalized.nutrients.protein_per_100g
                ),
                carbs_per_100g=(
                    normalized.nutrients.carbs_per_100g
                ),
                fat_per_100g=(
                    normalized.nutrients.fat_per_100g
                ),
                base_unit="g",
            )

            self.session.add(food)

        # Get the FoodItem primary key before creating portions.
        self.session.flush()

        for portion in normalized.portions:
            self.session.add(
                FoodPortion(
                    food_id=food.id,
                    name=portion.name,
                    quantity=portion.quantity,
                    unit=portion.unit,
                    gram_weight=portion.gram_weight,
                    usda_measure_unit=(
                        portion.usda_measure_unit
                    ),
                )
            )

        self.session.flush()

        return food

    # ============================================================
    # NUTRITION CALCULATION
    # ============================================================

    @staticmethod
    def calculate_nutrition_from_grams(
        food: FoodItem,
        gram_weight: float,
    ) -> dict[str, float]:

        if gram_weight <= 0:
            raise ValueError(
                "Gram weight must be greater than zero."
            )

        multiplier = gram_weight / 100.0

        return {
            "calories": (
                food.calories_per_100g
                * multiplier
            ),
            "protein": (
                food.protein_per_100g
                * multiplier
            ),
            "carbs": (
                food.carbs_per_100g
                * multiplier
            ),
            "fat": (
                food.fat_per_100g
                * multiplier
            ),
        }

    @staticmethod
    def calculate_gram_weight(
        *,
        quantity: float,
        portion: FoodPortion | None = None,
        unit: str | None = None,
    ) -> float:

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if portion is not None:

            if portion.gram_weight <= 0:
                raise ValueError(
                    "Food portion has an invalid gram weight."
                )

            if portion.quantity <= 0:
                raise ValueError(
                    "Food portion has an invalid quantity."
                )

            return (
                quantity
                * portion.gram_weight
                / portion.quantity
            )

        if unit is None:
            raise ValueError(
                "A unit is required when no food portion is supplied."
            )

        normalized_unit = unit.strip().lower()

        if normalized_unit in {
            "g",
            "gram",
            "grams",
        }:
            return quantity

        raise ValueError(
            "Unsupported direct food unit. "
            "Use a FoodPortion or enter the quantity in grams."
        )

    # ============================================================
    # PORTION RESOLUTION
    # ============================================================

    def resolve_gram_weight(
        self,
        *,
        food_id: int,
        quantity: float,
        portion_id: int | None,
        unit: str | None,
    ) -> float:

        if portion_id is not None:

            portion = self.get_food_portion_for_food(
                food_id=food_id,
                portion_id=portion_id,
            )

            if portion is None:
                raise ValueError(
                    "The selected food portion does not belong "
                    "to the specified food."
                )

            return self.calculate_gram_weight(
                quantity=quantity,
                portion=portion,
            )

        return self.calculate_gram_weight(
            quantity=quantity,
            unit=unit,
        )