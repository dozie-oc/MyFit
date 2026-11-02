class ExerciseMuscle {
  final String muscleGroup;
  final String role;

  const ExerciseMuscle({
    required this.muscleGroup,
    required this.role,
  });

  factory ExerciseMuscle.fromJson(Map<String, dynamic> json) {
    return ExerciseMuscle(
      muscleGroup: json['muscle_group'] as String? ?? '',
      role: json['role'] as String? ?? 'primary',
    );
  }

  Map<String, dynamic> toJson() => {
        'muscle_group': muscleGroup,
        'role': role,
      };
}

class CustomExerciseInput {
  final String name;
  final String category;
  final double? met;
  final String equipment;
  final String level;
  final String? description;
  final List<ExerciseMuscle> muscles;

  const CustomExerciseInput({
    required this.name,
    required this.category,
    this.met,
    this.equipment = 'bodyweight',
    this.level = 'intermediate',
    this.description,
    this.muscles = const [],
  });

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'category': category,
      if (met != null) 'met': met,
      'equipment': equipment,
      'level': level,
      if (description != null) 'description': description,
      'muscles': muscles.map((m) => m.toJson()).toList(),
    };
  }
}

class ExerciseCatalogItem {
  final int id;
  final String name;
  final String category;
  final String equipment;
  final String level;
  final bool isCustom;
  final double defaultMet;
  final List<ExerciseMuscle> muscles;

  const ExerciseCatalogItem({
    required this.id,
    required this.name,
    required this.category,
    this.equipment = 'bodyweight',
    this.level = 'intermediate',
    this.isCustom = false,
    this.defaultMet = 5.0,
    this.muscles = const [],
  });

  factory ExerciseCatalogItem.fromJson(Map<String, dynamic> json) {
    final musclesRaw = json['muscles'];
    return ExerciseCatalogItem(
      id: (json['id'] as num).toInt(),
      name: json['name'] as String,
      category: (json['category'] as String?)?.toLowerCase() ?? '',
      equipment: json['equipment'] as String? ?? 'bodyweight',
      level: json['level'] as String? ?? 'intermediate',
      isCustom: json['is_custom'] as bool? ?? false,
      defaultMet: (json['default_met'] as num?)?.toDouble() ?? 5.0,
      muscles: musclesRaw is List
          ? musclesRaw
              .map((e) => ExerciseMuscle.fromJson(e as Map<String, dynamic>))
              .toList()
          : const [],
    );
  }
}

class MuscleGroupStatus {
  final String muscleGroup;
  final String status;
  final double setsCompleted;

  const MuscleGroupStatus({
    required this.muscleGroup,
    required this.status,
    required this.setsCompleted,
  });

  factory MuscleGroupStatus.fromJson(Map<String, dynamic> json) {
    return MuscleGroupStatus(
      muscleGroup: json['muscle_group'] as String? ?? '',
      status: json['status'] as String? ?? '',
      setsCompleted: (json['sets_completed'] as num?)?.toDouble() ?? 0,
    );
  }
}

class CardioWeek {
  final double minutes;
  final int targetMinutes;
  final String status;

  const CardioWeek({
    this.minutes = 0.0,
    this.targetMinutes = 90,
    this.status = 'low',
  });

  factory CardioWeek.fromJson(Map<String, dynamic> json) {
    return CardioWeek(
      minutes: (json['minutes'] as num?)?.toDouble() ?? 0.0,
      targetMinutes: (json['target_minutes'] as num?)?.toInt() ?? 90,
      status: json['status'] as String? ?? 'low',
    );
  }
}

class TrainingAdequacy {
  final String summary;
  final String detail;
  final String sessionAction;
  final int exercisesToday;
  final double totalSetsToday;
  final List<String> recommendedNext;
  final List<MuscleGroupStatus> muscleGroups;
  final CardioWeek cardioWeek;

  const TrainingAdequacy({
    required this.summary,
    required this.detail,
    required this.sessionAction,
    required this.exercisesToday,
    required this.totalSetsToday,
    required this.recommendedNext,
    required this.muscleGroups,
    this.cardioWeek = const CardioWeek(),
  });

  factory TrainingAdequacy.fromJson(Map<String, dynamic> json) {
    final next = json['recommended_next'];
    final groups = json['muscle_groups'];
    final cw = json['cardio_week'];
    return TrainingAdequacy(
      summary: json['summary'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      sessionAction: json['session_action'] as String? ?? '',
      exercisesToday: (json['exercises_today'] as num?)?.toInt() ?? 0,
      totalSetsToday: (json['total_sets_today'] as num?)?.toDouble() ?? 0,
      recommendedNext:
          next is List ? next.map((e) => e.toString()).toList() : const [],
      muscleGroups: groups is List
          ? groups
              .map((e) => MuscleGroupStatus.fromJson(e as Map<String, dynamic>))
              .toList()
          : const [],
      cardioWeek: cw is Map<String, dynamic>
          ? CardioWeek.fromJson(cw)
          : const CardioWeek(),
    );
  }
}
