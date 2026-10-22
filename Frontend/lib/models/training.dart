class ExerciseCatalogItem {
  final int id;
  final String name;
  final String category;

  const ExerciseCatalogItem({
    required this.id,
    required this.name,
    required this.category,
  });

  factory ExerciseCatalogItem.fromJson(Map<String, dynamic> json) {
    return ExerciseCatalogItem(
      id: (json['id'] as num).toInt(),
      name: json['name'] as String,
      category: (json['category'] as String?)?.toLowerCase() ?? '',
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

class TrainingAdequacy {
  final String summary;
  final String detail;
  final String sessionAction;
  final int exercisesToday;
  final double totalSetsToday;
  final List<String> recommendedNext;
  final List<MuscleGroupStatus> muscleGroups;

  const TrainingAdequacy({
    required this.summary,
    required this.detail,
    required this.sessionAction,
    required this.exercisesToday,
    required this.totalSetsToday,
    required this.recommendedNext,
    required this.muscleGroups,
  });

  factory TrainingAdequacy.fromJson(Map<String, dynamic> json) {
    final next = json['recommended_next'];
    final groups = json['muscle_groups'];
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
    );
  }
}
