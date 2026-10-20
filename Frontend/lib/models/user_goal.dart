class UserGoal {
  final int? id;
  final String? goalType;
  final double? targetWeight;
  final String? targetDate;
  final String? activityLevel;
  final int? trainingDaysPerWeek;
  final String? trainingExperience;
  final String? availableEquipment;
  final String? dietaryPreference;
  final String? foodsToAvoid;

  const UserGoal({
    this.id,
    this.goalType,
    this.targetWeight,
    this.targetDate,
    this.activityLevel,
    this.trainingDaysPerWeek,
    this.trainingExperience,
    this.availableEquipment,
    this.dietaryPreference,
    this.foodsToAvoid,
  });

  const UserGoal.empty()
      : id = null,
        goalType = null,
        targetWeight = null,
        targetDate = null,
        activityLevel = null,
        trainingDaysPerWeek = null,
        trainingExperience = null,
        availableEquipment = null,
        dietaryPreference = null,
        foodsToAvoid = null;

  bool get hasGoal =>
      id != null || (goalType != null && goalType!.trim().isNotEmpty);

  List<String> get equipmentList {
    if (availableEquipment == null || availableEquipment!.trim().isEmpty) {
      return const [];
    }
    return availableEquipment!
        .split(',')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
  }

  factory UserGoal.fromJson(Map<String, dynamic> json) {
    return UserGoal(
      id: json['id'] as int?,
      goalType: json['goal_type'] as String?,
      targetWeight: (json['target_weight'] as num?)?.toDouble(),
      targetDate: json['target_date'] as String?,
      activityLevel: json['activity_level'] as String?,
      trainingDaysPerWeek: json['training_days_per_week'] as int?,
      trainingExperience: json['training_experience'] as String?,
      availableEquipment: json['available_equipment'] as String?,
      dietaryPreference: json['dietary_preference'] as String?,
      foodsToAvoid: json['foods_to_avoid'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'goal_type': goalType,
      'target_weight': targetWeight,
      'target_date': targetDate,
      'activity_level': activityLevel,
      'training_days_per_week': trainingDaysPerWeek,
      'training_experience': trainingExperience,
      'available_equipment': availableEquipment,
      'dietary_preference': dietaryPreference,
      'foods_to_avoid': foodsToAvoid,
    };
  }
}
