import 'food.dart';

class RecipeIngredient {
  final int? id;
  final int foodId;
  final String foodName;
  final int? portionId;
  final String? portionName;
  final double quantity;
  final String unit;
  final double gramWeight;
  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  const RecipeIngredient({
    this.id,
    required this.foodId,
    required this.foodName,
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

  factory RecipeIngredient.fromJson(Map<String, dynamic> j) => RecipeIngredient(
        id: j['id'] as int?,
        foodId: j['food_id'] as int,
        foodName: (j['food_name'] as String?) ?? '',
        portionId: j['portion_id'] as int?,
        portionName: j['portion_name'] as String?,
        quantity: (j['quantity'] as num).toDouble(),
        unit: (j['unit'] as String?) ?? 'g',
        gramWeight: (j['gram_weight'] as num).toDouble(),
        calories: (j['calories'] as num).toDouble(),
        protein: (j['protein'] as num).toDouble(),
        carbs: (j['carbs'] as num).toDouble(),
        fat: (j['fat'] as num).toDouble(),
      );
}

class Recipe {
  final int id;
  final int foodId;
  final String name;
  final double servings;
  final double? cookedWeightG;
  final double totalGrams;
  final double cookedGrams;
  final double portionGrams;
  final double totalCalories;
  final double totalProtein;
  final double totalCarbs;
  final double totalFat;
  final double caloriesPerPortion;
  final double proteinPerPortion;
  final double carbsPerPortion;
  final double fatPerPortion;
  final double caloriesPer100g;
  final double proteinPer100g;
  final double carbsPer100g;
  final double fatPer100g;
  final List<FoodPortion> portions;
  final List<RecipeIngredient> ingredients;

  const Recipe({
    required this.id,
    required this.foodId,
    required this.name,
    required this.servings,
    this.cookedWeightG,
    required this.totalGrams,
    required this.cookedGrams,
    required this.portionGrams,
    required this.totalCalories,
    required this.totalProtein,
    required this.totalCarbs,
    required this.totalFat,
    required this.caloriesPerPortion,
    required this.proteinPerPortion,
    required this.carbsPerPortion,
    required this.fatPerPortion,
    required this.caloriesPer100g,
    required this.proteinPer100g,
    required this.carbsPer100g,
    required this.fatPer100g,
    required this.portions,
    required this.ingredients,
  });

  factory Recipe.fromJson(Map<String, dynamic> j) => Recipe(
        id: j['id'] as int,
        foodId: j['food_id'] as int,
        name: j['name'] as String,
        servings: (j['servings'] as num).toDouble(),
        cookedWeightG: (j['cooked_weight_g'] as num?)?.toDouble(),
        totalGrams: (j['total_grams'] as num).toDouble(),
        cookedGrams: (j['cooked_grams'] as num).toDouble(),
        portionGrams: (j['portion_grams'] as num).toDouble(),
        totalCalories: (j['total_calories'] as num).toDouble(),
        totalProtein: (j['total_protein'] as num).toDouble(),
        totalCarbs: (j['total_carbs'] as num).toDouble(),
        totalFat: (j['total_fat'] as num).toDouble(),
        caloriesPerPortion: (j['calories_per_portion'] as num).toDouble(),
        proteinPerPortion: (j['protein_per_portion'] as num).toDouble(),
        carbsPerPortion: (j['carbs_per_portion'] as num).toDouble(),
        fatPerPortion: (j['fat_per_portion'] as num).toDouble(),
        caloriesPer100g: (j['calories_per_100g'] as num).toDouble(),
        proteinPer100g: (j['protein_per_100g'] as num).toDouble(),
        carbsPer100g: (j['carbs_per_100g'] as num).toDouble(),
        fatPer100g: (j['fat_per_100g'] as num).toDouble(),
        portions: (j['portions'] as List<dynamic>? ?? [])
            .map((e) => FoodPortion.fromJson(e as Map<String, dynamic>))
            .toList(),
        ingredients: (j['ingredients'] as List<dynamic>? ?? [])
            .map((e) => RecipeIngredient.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  FoodItem toFoodItem() => FoodItem(
        id: foodId,
        name: name,
        caloriesPer100g: caloriesPer100g,
        proteinPer100g: proteinPer100g,
        carbsPer100g: carbsPer100g,
        fatPer100g: fatPer100g,
        baseUnit: 'g',
        kind: 'recipe',
        portions: portions,
      );
}

class RecipeInput {
  final String name;
  final double servings;
  final double? cookedWeightG;
  final List<Map<String, dynamic>> ingredients;

  const RecipeInput({
    required this.name,
    required this.servings,
    this.cookedWeightG,
    required this.ingredients,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        'servings': servings,
        if (cookedWeightG != null) 'cooked_weight_g': cookedWeightG,
        'ingredients': ingredients,
      };
}

class DraftRecipeIngredient {
  final int foodId;
  final String foodName;
  final double quantity;
  final int? portionId;
  final String? portionName;
  final String? unit;
  final double gramWeight;
  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  const DraftRecipeIngredient({
    required this.foodId,
    required this.foodName,
    required this.quantity,
    this.portionId,
    this.portionName,
    this.unit,
    required this.gramWeight,
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  Map<String, dynamic> toItemPayload() => {
        'food_id': foodId,
        'quantity': quantity,
        if (portionId != null) 'portion_id': portionId,
        if (portionId == null && unit != null) 'unit': unit,
      };
}

class RecipeNutritionPreview {
  final double totalGrams;
  final double cookedGrams;
  final double portionGrams;
  final double totalCalories;
  final double totalProtein;
  final double totalCarbs;
  final double totalFat;
  final double caloriesPerPortion;
  final double proteinPerPortion;
  final double carbsPerPortion;
  final double fatPerPortion;
  final double caloriesPer100g;
  final double proteinPer100g;
  final double carbsPer100g;
  final double fatPer100g;

  const RecipeNutritionPreview({
    required this.totalGrams,
    required this.cookedGrams,
    required this.portionGrams,
    required this.totalCalories,
    required this.totalProtein,
    required this.totalCarbs,
    required this.totalFat,
    required this.caloriesPerPortion,
    required this.proteinPerPortion,
    required this.carbsPerPortion,
    required this.fatPerPortion,
    required this.caloriesPer100g,
    required this.proteinPer100g,
    required this.carbsPer100g,
    required this.fatPer100g,
  });
}

RecipeNutritionPreview computeRecipePreview({
  required List<DraftRecipeIngredient> ingredients,
  required double servings,
  double? cookedWeightG,
}) {
  final safeServings = servings > 0 ? servings : 1.0;
  double totalGrams = 0;
  double totalCal = 0;
  double totalPro = 0;
  double totalCarb = 0;
  double totalFat = 0;

  for (final ing in ingredients) {
    totalGrams += ing.gramWeight;
    totalCal += ing.calories;
    totalPro += ing.protein;
    totalCarb += ing.carbs;
    totalFat += ing.fat;
  }

  final cooked =
      (cookedWeightG != null && cookedWeightG > 0) ? cookedWeightG : totalGrams;
  final factor = cooked > 0 ? (100.0 / cooked) : 0.0;

  return RecipeNutritionPreview(
    totalGrams: totalGrams,
    cookedGrams: cooked,
    portionGrams: cooked / safeServings,
    totalCalories: totalCal,
    totalProtein: totalPro,
    totalCarbs: totalCarb,
    totalFat: totalFat,
    caloriesPerPortion: totalCal / safeServings,
    proteinPerPortion: totalPro / safeServings,
    carbsPerPortion: totalCarb / safeServings,
    fatPerPortion: totalFat / safeServings,
    caloriesPer100g: totalCal * factor,
    proteinPer100g: totalPro * factor,
    carbsPer100g: totalCarb * factor,
    fatPer100g: totalFat * factor,
  );
}

final RegExp _cookingFatPattern =
    RegExp(r'\b(oil|butter|margarine|ghee|lard)\b', caseSensitive: false);

bool hasCookingFat(Iterable<String> ingredientNames) {
  for (final name in ingredientNames) {
    if (_cookingFatPattern.hasMatch(name)) return true;
  }
  return false;
}
