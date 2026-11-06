class RecommendationItem {
  final String name;
  final int? exerciseCatalogId;
  final String? description;
  final String? category;
  final int? sets;
  final int? reps;
  final double? weightKg;
  final int? restSeconds;
  final String? lastPerformance;
  final int? durationMinutes;
  final int? foodId;
  final double? quantity;
  final double? gramWeight;
  final String? unit;
  final double? calories;
  final double? protein;
  final double? carbs;
  final double? fat;

  const RecommendationItem({
    required this.name,
    this.exerciseCatalogId,
    this.description,
    this.category,
    this.sets,
    this.reps,
    this.weightKg,
    this.restSeconds,
    this.lastPerformance,
    this.durationMinutes,
    this.foodId,
    this.quantity,
    this.gramWeight,
    this.unit,
    this.calories,
    this.protein,
    this.carbs,
    this.fat,
  });

  factory RecommendationItem.fromJson(Map<String, dynamic> json) {
    return RecommendationItem(
      name: json['name'] as String? ?? '',
      exerciseCatalogId: (json['exercise_catalog_id'] as num?)?.toInt(),
      description: json['description'] as String?,
      category: json['category'] as String?,
      sets: (json['sets'] as num?)?.toInt(),
      reps: (json['reps'] as num?)?.toInt(),
      weightKg: (json['weight_kg'] as num?)?.toDouble(),
      restSeconds: (json['rest_seconds'] as num?)?.toInt(),
      lastPerformance: json['last_performance'] as String?,
      durationMinutes: (json['duration_minutes'] as num?)?.toInt(),
      foodId: (json['food_id'] as num?)?.toInt(),
      quantity: (json['quantity'] as num?)?.toDouble(),
      gramWeight: (json['gram_weight'] as num?)?.toDouble(),
      unit: json['unit'] as String?,
      calories: (json['calories'] as num?)?.toDouble(),
      protein: (json['protein'] as num?)?.toDouble(),
      carbs: (json['carbs'] as num?)?.toDouble(),
      fat: (json['fat'] as num?)?.toDouble(),
    );
  }
}

class Recommendation {
  final bool hasRecommendation;
  final String? type; // 'meal' | 'exercise'
  final String title;
  final String reason;
  final String? mealType;
  final List<RecommendationItem> items;

  const Recommendation({
    required this.hasRecommendation,
    this.type,
    this.title = '',
    this.reason = '',
    this.mealType,
    this.items = const [],
  });

  const Recommendation.none() : this(hasRecommendation: false);

  factory Recommendation.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'];
    return Recommendation(
      hasRecommendation: json['has_recommendation'] as bool? ?? false,
      type: json['type'] as String?,
      title: json['title'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
      mealType: json['meal_type'] as String?,
      items: rawItems is List
          ? rawItems
              .map((e) =>
                  RecommendationItem.fromJson(e as Map<String, dynamic>))
              .toList()
          : const [],
    );
  }
}
