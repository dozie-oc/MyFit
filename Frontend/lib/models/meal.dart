import 'food.dart';

const List<String> kSupportedDirectUnits = ['g', 'oz', 'ml', 'kg', 'lb'];

const Map<String, double> _kDirectUnitToGrams = {
  'g': 1.0,
  'gram': 1.0,
  'grams': 1.0,
  'kg': 1000.0,
  'kilogram': 1000.0,
  'kilograms': 1000.0,
  'oz': 28.3495,
  'ounce': 28.3495,
  'ounces': 28.3495,
  'lb': 453.592,
  'lbs': 453.592,
  'pound': 453.592,
  'pounds': 453.592,
  'ml': 1.0,
  'milliliter': 1.0,
  'milliliters': 1.0,
};

String normalizeDirectUnit(String? unit) {
  final raw = (unit ?? 'g').trim().toLowerCase();
  if (raw == 'gram' || raw == 'grams' || raw == 'g') return 'g';
  if (raw == 'kilogram' || raw == 'kilograms' || raw == 'kg') return 'kg';
  if (raw == 'ounce' || raw == 'ounces' || raw == 'oz') return 'oz';
  if (raw == 'pound' || raw == 'pounds' || raw == 'lbs' || raw == 'lb') {
    return 'lb';
  }
  if (raw == 'milliliter' || raw == 'milliliters' || raw == 'ml') return 'ml';
  return 'g';
}

double convertUnitToGrams(double quantity, String unit) {
  if (quantity <= 0) return 0.0;
  final factor = _kDirectUnitToGrams[unit.trim().toLowerCase()] ?? 1.0;
  return quantity * factor;
}

class DraftMealItem {
  final FoodItem food;
  final double quantity;
  final int? portionId;
  final String? portionName;
  final double? portionGramWeight;
  final double portionBaseQuantity;
  final String unit;

  const DraftMealItem({
    required this.food,
    required this.quantity,
    this.portionId,
    this.portionName,
    this.portionGramWeight,
    this.portionBaseQuantity = 1.0,
    this.unit = 'g',
  });

  double get gramWeight {
    if (quantity <= 0) return 0.0;
    if (portionId != null &&
        portionGramWeight != null &&
        portionGramWeight! > 0 &&
        portionBaseQuantity > 0) {
      return (quantity / portionBaseQuantity) * portionGramWeight!;
    }
    return convertUnitToGrams(quantity, unit);
  }

  double get _factor => gramWeight / 100.0;
  double get calories => food.caloriesPer100g * _factor;
  double get protein => food.proteinPer100g * _factor;
  double get carbs => food.carbsPer100g * _factor;
  double get fat => food.fatPer100g * _factor;

  FoodPortion? get selectedPortion {
    if (portionId == null) return null;
    for (final p in food.portions) {
      if (p.id == portionId) return p;
    }
    if (portionName != null && portionGramWeight != null) {
      return FoodPortion(
        id: portionId!,
        name: portionName!,
        quantity: portionBaseQuantity,
        unit: unit,
        gramWeight: portionGramWeight!,
      );
    }
    return null;
  }

  DraftMealItem withFood(
    FoodItem newFood, {
    FoodPortion? portion,
    double? quantity,
    String? unit,
  }) {
    final chosenPortion = portion ??
        (newFood.portions.isNotEmpty ? newFood.portions.first : null);
    if (chosenPortion != null && unit == null) {
      final baseQty =
          chosenPortion.quantity > 0 ? chosenPortion.quantity : 1.0;
      return DraftMealItem(
        food: newFood,
        quantity: quantity ?? baseQty,
        portionId: chosenPortion.id,
        portionName: chosenPortion.name,
        portionGramWeight: chosenPortion.gramWeight,
        portionBaseQuantity: baseQty,
        unit: chosenPortion.unit.isNotEmpty ? chosenPortion.unit : 'serving',
      );
    }
    final normalizedUnit = normalizeDirectUnit(unit ?? 'g');
    final defaultQty =
        quantity ?? (normalizedUnit == 'g' || normalizedUnit == 'ml' ? 100.0 : 1.0);
    return DraftMealItem(
      food: newFood,
      quantity: defaultQty,
      portionId: null,
      portionName: null,
      portionGramWeight: null,
      portionBaseQuantity: 1.0,
      unit: normalizedUnit,
    );
  }

  DraftMealItem withPortion(FoodPortion? portion, {double? quantity}) {
    if (portion != null) {
      final baseQty = portion.quantity > 0 ? portion.quantity : 1.0;
      return DraftMealItem(
        food: food,
        quantity: quantity ?? baseQty,
        portionId: portion.id,
        portionName: portion.name,
        portionGramWeight: portion.gramWeight,
        portionBaseQuantity: baseQty,
        unit: portion.unit.isNotEmpty ? portion.unit : 'serving',
      );
    }
    return withUnit('g', quantity: quantity ?? 100.0);
  }

  DraftMealItem withUnit(String newUnit, {double? quantity}) {
    final normalized = normalizeDirectUnit(newUnit);
    final nextQty = quantity ??
        (portionId != null
            ? (normalized == 'g' || normalized == 'ml' ? 100.0 : 1.0)
            : this.quantity);
    return DraftMealItem(
      food: food,
      quantity: nextQty,
      portionId: null,
      portionName: null,
      portionGramWeight: null,
      portionBaseQuantity: 1.0,
      unit: normalized,
    );
  }

  DraftMealItem withQuantity(double newQuantity) {
    return DraftMealItem(
      food: food,
      quantity: newQuantity < 0 ? 0.0 : newQuantity,
      portionId: portionId,
      portionName: portionName,
      portionGramWeight: portionGramWeight,
      portionBaseQuantity: portionBaseQuantity,
      unit: unit,
    );
  }

  DraftMealItem withCatalogFood(FoodItem loadedFood) {
    FoodPortion? matchedPortion;
    if (portionId != null) {
      for (final p in loadedFood.portions) {
        if (p.id == portionId) {
          matchedPortion = p;
          break;
        }
      }
    }
    return DraftMealItem(
      food: loadedFood,
      quantity: quantity,
      portionId: portionId,
      portionName: matchedPortion?.name ?? portionName,
      portionGramWeight: matchedPortion?.gramWeight ?? portionGramWeight,
      portionBaseQuantity:
          (matchedPortion != null && matchedPortion.quantity > 0)
              ? matchedPortion.quantity
              : portionBaseQuantity,
      unit: matchedPortion?.unit ?? unit,
    );
  }

  factory DraftMealItem.fromMealItem(MealItem item, {FoodItem? catalogFood}) {
    final safeGrams = item.gramWeight > 0 ? item.gramWeight : 100.0;
    final safeQty = item.quantity > 0 ? item.quantity : 1.0;
    final perPortionGrams =
        item.portionId != null ? (safeGrams / safeQty) : null;

    FoodPortion? matchedPortion;
    if (catalogFood != null && item.portionId != null) {
      for (final p in catalogFood.portions) {
        if (p.id == item.portionId) {
          matchedPortion = p;
          break;
        }
      }
    }

    final fallbackPortion = item.portionId != null
        ? FoodPortion(
            id: item.portionId!,
            name: item.portionName ?? item.unit,
            quantity: 1.0,
            unit: item.unit.isNotEmpty ? item.unit : 'serving',
            gramWeight: perPortionGrams ?? safeGrams,
          )
        : null;

    final resolvedFood = catalogFood ??
        FoodItem(
          id: item.foodId,
          name: item.foodName.isNotEmpty ? item.foodName : 'Food #${item.foodId}',
          kind: item.foodKind,
          caloriesPer100g:
              item.gramWeight > 0 ? (item.calories * 100.0 / item.gramWeight) : 0.0,
          proteinPer100g:
              item.gramWeight > 0 ? (item.protein * 100.0 / item.gramWeight) : 0.0,
          carbsPer100g:
              item.gramWeight > 0 ? (item.carbs * 100.0 / item.gramWeight) : 0.0,
          fatPer100g:
              item.gramWeight > 0 ? (item.fat * 100.0 / item.gramWeight) : 0.0,
          portions: fallbackPortion != null ? [fallbackPortion] : const [],
        );

    return DraftMealItem(
      food: resolvedFood,
      quantity: item.quantity,
      portionId: item.portionId,
      portionName: matchedPortion?.name ?? item.portionName,
      portionGramWeight: matchedPortion?.gramWeight ?? perPortionGrams,
      portionBaseQuantity:
          (matchedPortion != null && matchedPortion.quantity > 0)
              ? matchedPortion.quantity
              : 1.0,
      unit: item.portionId != null
          ? (matchedPortion?.unit ?? item.unit)
          : normalizeDirectUnit(item.unit),
    );
  }

  Map<String, dynamic> toItemPayload() => {
        'food_id': food.id,
        'quantity': quantity,
        if (portionId != null) 'portion_id': portionId,
        if (portionId == null) 'unit': normalizeDirectUnit(unit),
      };
}

class MealNutritionTotals {
  final double totalGrams;
  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  const MealNutritionTotals({
    required this.totalGrams,
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });
}

MealNutritionTotals computeMealTotals(Iterable<DraftMealItem> items) {
  double totalGrams = 0;
  double calories = 0;
  double protein = 0;
  double carbs = 0;
  double fat = 0;
  for (final item in items) {
    totalGrams += item.gramWeight;
    calories += item.calories;
    protein += item.protein;
    carbs += item.carbs;
    fat += item.fat;
  }
  return MealNutritionTotals(
    totalGrams: totalGrams,
    calories: calories,
    protein: protein,
    carbs: carbs,
    fat: fat,
  );
}

class MealItem {
  final int id;
  final int foodId;
  final String foodName;
  final String foodKind;
  final int? portionId;
  final String? portionName;
  final double quantity;
  final String unit;
  final double gramWeight;
  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  const MealItem({
    required this.id,
    required this.foodId,
    this.foodName = '',
    this.foodKind = 'catalog',
    this.portionId,
    this.portionName,
    required this.quantity,
    required this.unit,
    required this.gramWeight,
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  factory MealItem.fromJson(Map<String, dynamic> json) {
    final id = (json['id'] as num?)?.toInt();
    if (id == null) throw const FormatException('MealItem.id is required');
    final foodId = (json['food_id'] as num?)?.toInt();
    if (foodId == null) throw const FormatException('MealItem.food_id is required');
    return MealItem(
      id: id,
      foodId: foodId,
      foodName: json['food_name'] as String? ?? '',
      foodKind: json['food_kind'] as String? ?? 'catalog',
      portionId: (json['portion_id'] as num?)?.toInt(),
      portionName: json['portion_name'] as String?,
      quantity: (json['quantity'] as num?)?.toDouble() ?? 0.0,
      unit: json['unit'] as String? ?? '',
      gramWeight: (json['gram_weight'] as num?)?.toDouble() ?? 0.0,
      calories: (json['calories'] as num?)?.toDouble() ?? 0.0,
      protein: (json['protein'] as num?)?.toDouble() ?? 0.0,
      carbs: (json['carbs'] as num?)?.toDouble() ?? 0.0,
      fat: (json['fat'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class Meal {
  final int id;
  final String date;
  final String mealType;
  final double calories;
  final double protein;
  final double carbs;
  final double fat;
  final String? createdAt;
  final List<MealItem> items;

  const Meal({
    required this.id,
    required this.date,
    this.mealType = 'snack',
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
    this.createdAt,
    this.items = const [],
  });

  factory Meal.fromJson(Map<String, dynamic> json) {
    final id = (json['id'] as num?)?.toInt();
    if (id == null) throw const FormatException('Meal.id is required');
    return Meal(
      id: id,
      date: json['date'] as String? ?? '',
      mealType: json['meal_type'] as String? ?? 'snack',
      calories: (json['calories'] as num?)?.toDouble() ?? 0.0,
      protein: (json['protein'] as num?)?.toDouble() ?? 0.0,
      carbs: (json['carbs'] as num?)?.toDouble() ?? 0.0,
      fat: (json['fat'] as num?)?.toDouble() ?? 0.0,
      createdAt: json['created_at']?.toString(),
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => MealItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}
