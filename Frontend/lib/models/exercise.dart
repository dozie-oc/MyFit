class Exercise {
  final int id;
  final String date;
  final String name;
  final String category;
  final int? exerciseCatalogId;
  final int? sets;
  final int? reps;
  final double? weightKg;
  final int? durationMinutes;
  final double? distanceKm;
  final String? intensity;
  final int? rir;
  final double caloriesBurned;

  const Exercise({
    required this.id,
    required this.date,
    required this.name,
    this.category = 'other',
    this.exerciseCatalogId,
    this.sets,
    this.reps,
    this.weightKg,
    this.durationMinutes,
    this.distanceKm,
    this.intensity,
    this.rir,
    required this.caloriesBurned,
  });

  factory Exercise.fromJson(Map<String, dynamic> json) {
    return Exercise(
      id: (json['id'] as num?)?.toInt() ?? 0,
      date: json['date'] as String? ?? '',
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? 'other',
      exerciseCatalogId: (json['exercise_catalog_id'] as num?)?.toInt(),
      sets: (json['sets'] as num?)?.toInt(),
      reps: (json['reps'] as num?)?.toInt(),
      weightKg: (json['weight_kg'] as num?)?.toDouble(),
      durationMinutes: (json['duration_minutes'] as num?)?.toInt(),
      distanceKm: (json['distance_km'] as num?)?.toDouble(),
      intensity: json['intensity'] as String?,
      rir: (json['rir'] as num?)?.toInt(),
      caloriesBurned: (json['calories_burned'] as num?)?.toDouble() ?? 0.0,
    );
  }
}
