class Exercise {
  final int id;
  final String date;
  final String name;
  final String category;
  final int? exerciseCatalogId;
  final int? workoutSessionId;
  final int? sets;
  final int? reps;
  final double? weightKg;
  final int? durationMinutes;
  final double? distanceKm;
  final String? intensity;
  final int? rir;
  final double caloriesBurned;
  final bool isPr;

  const Exercise({
    required this.id,
    required this.date,
    required this.name,
    this.category = 'other',
    this.exerciseCatalogId,
    this.workoutSessionId,
    this.sets,
    this.reps,
    this.weightKg,
    this.durationMinutes,
    this.distanceKm,
    this.intensity,
    this.rir,
    required this.caloriesBurned,
    this.isPr = false,
  });

  factory Exercise.fromJson(Map<String, dynamic> json) {
    final id = (json['id'] as num?)?.toInt();
    if (id == null) throw const FormatException('Exercise.id is required');
    return Exercise(
      id: id,
      date: json['date'] as String? ?? '',
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? 'other',
      exerciseCatalogId: (json['exercise_catalog_id'] as num?)?.toInt(),
      workoutSessionId: (json['workout_session_id'] as num?)?.toInt(),
      sets: (json['sets'] as num?)?.toInt(),
      reps: (json['reps'] as num?)?.toInt(),
      weightKg: (json['weight_kg'] as num?)?.toDouble(),
      durationMinutes: (json['duration_minutes'] as num?)?.toInt(),
      distanceKm: (json['distance_km'] as num?)?.toDouble(),
      intensity: json['intensity'] as String?,
      rir: (json['rir'] as num?)?.toInt(),
      caloriesBurned: (json['calories_burned'] as num?)?.toDouble() ?? 0.0,
      isPr: json['is_pr'] as bool? ?? false,
    );
  }
}

class ExerciseHistory {
  final Exercise? last;
  final double? bestWeightKg;
  final double? bestEst1rm;
  final int timesLogged;

  const ExerciseHistory({
    this.last,
    this.bestWeightKg,
    this.bestEst1rm,
    this.timesLogged = 0,
  });

  factory ExerciseHistory.fromJson(Map<String, dynamic> json) {
    final lastRaw = json['last'];
    return ExerciseHistory(
      last: lastRaw is Map<String, dynamic> ? Exercise.fromJson(lastRaw) : null,
      bestWeightKg: (json['best_weight_kg'] as num?)?.toDouble(),
      bestEst1rm: (json['best_est_1rm'] as num?)?.toDouble(),
      timesLogged: (json['times_logged'] as num?)?.toInt() ?? 0,
    );
  }
}
