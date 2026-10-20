class Habit {
  final int id;
  final String name;
  final String? description;
  final String frequency;
  final String color;
  final int targetPerWeek;
  final String? createdAt;

  const Habit({
    required this.id,
    required this.name,
    this.description,
    this.frequency = 'daily',
    this.color = '#6366F1',
    this.targetPerWeek = 7,
    this.createdAt,
  });

  factory Habit.fromJson(Map<String, dynamic> json) {
    return Habit(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: json['name'] as String? ?? '',
      description: json['description'] as String?,
      frequency: json['frequency'] as String? ?? 'daily',
      color: json['color'] as String? ?? '#6366F1',
      targetPerWeek: (json['target_per_week'] as num?)?.toInt() ?? 7,
      createdAt: json['created_at']?.toString(),
    );
  }
}

class HabitActivityDay {
  final String date;
  final List<int> completedHabitIds;
  final List<int> pendingHabitIds;

  const HabitActivityDay({
    required this.date,
    this.completedHabitIds = const [],
    this.pendingHabitIds = const [],
  });

  factory HabitActivityDay.fromJson(Map<String, dynamic> json) {
    return HabitActivityDay(
      date: json['date'] as String? ?? '',
      completedHabitIds: (json['completed_habit_ids'] as List<dynamic>?)
              ?.map((e) => (e as num).toInt())
              .toList() ??
          const [],
      pendingHabitIds: (json['pending_habit_ids'] as List<dynamic>?)
              ?.map((e) => (e as num).toInt())
              .toList() ??
          const [],
    );
  }
}
