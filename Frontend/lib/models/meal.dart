class MealItem {
  final int id;
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

  const MealItem({
    required this.id,
    required this.foodId,
    this.foodName = '',
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
    return MealItem(
      id: (json['id'] as num?)?.toInt() ?? 0,
      foodId: (json['food_id'] as num?)?.toInt() ?? 0,
      foodName: json['food_name'] as String? ?? '',
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
    return Meal(
      id: (json['id'] as num?)?.toInt() ?? 0,
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
