class FoodPortion {
  final int id;
  final String name;
  final double quantity;
  final String unit;
  final double gramWeight;
  final String? usdaMeasureUnit;

  const FoodPortion({
    required this.id,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.gramWeight,
    this.usdaMeasureUnit,
  });

  factory FoodPortion.fromJson(Map<String, dynamic> json) {
    return FoodPortion(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: json['name'] as String? ?? '',
      quantity: (json['quantity'] as num?)?.toDouble() ?? 0.0,
      unit: json['unit'] as String? ?? '',
      gramWeight: (json['gram_weight'] as num?)?.toDouble() ?? 0.0,
      usdaMeasureUnit: json['usda_measure_unit'] as String?,
    );
  }
}

class FoodItem {
  final int id;
  final String name;
  final int? usdaFdcId;
  final String? usdaDataType;
  final double caloriesPer100g;
  final double proteinPer100g;
  final double carbsPer100g;
  final double fatPer100g;
  final String baseUnit;
  final List<FoodPortion> portions;

  const FoodItem({
    required this.id,
    required this.name,
    this.usdaFdcId,
    this.usdaDataType,
    required this.caloriesPer100g,
    required this.proteinPer100g,
    required this.carbsPer100g,
    required this.fatPer100g,
    this.baseUnit = 'g',
    this.portions = const [],
  });

  factory FoodItem.fromJson(Map<String, dynamic> json) {
    return FoodItem(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: json['name'] as String? ?? '',
      usdaFdcId: (json['usda_fdc_id'] as num?)?.toInt(),
      usdaDataType: json['usda_data_type'] as String?,
      caloriesPer100g: (json['calories_per_100g'] as num?)?.toDouble() ?? 0.0,
      proteinPer100g: (json['protein_per_100g'] as num?)?.toDouble() ?? 0.0,
      carbsPer100g: (json['carbs_per_100g'] as num?)?.toDouble() ?? 0.0,
      fatPer100g: (json['fat_per_100g'] as num?)?.toDouble() ?? 0.0,
      baseUnit: json['base_unit'] as String? ?? 'g',
      portions: (json['portions'] as List<dynamic>?)
              ?.map((e) => FoodPortion.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}
