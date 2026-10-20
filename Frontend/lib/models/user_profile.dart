class UserProfile {
  final int id;
  final String username;
  final double? weight;
  final double? height;
  final String? birthdate;
  final int? age;

  const UserProfile({
    required this.id,
    required this.username,
    this.weight,
    this.height,
    this.birthdate,
    this.age,
  });

  const UserProfile.empty()
      : id = 0,
        username = '',
        weight = null,
        height = null,
        birthdate = null,
        age = null;

  double? get bmi {
    if (height == null || height! <= 0 || weight == null || weight! <= 0) {
      return null;
    }
    final hMeters = height! / 100.0;
    return weight! / (hMeters * hMeters);
  }

  String get formattedBmi => bmi != null ? bmi!.toStringAsFixed(1) : '—';

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: (json['id'] as num?)?.toInt() ?? 0,
      username: json['username'] as String? ?? '',
      weight: (json['weight'] as num?)?.toDouble(),
      height: (json['height'] as num?)?.toDouble(),
      birthdate: json['birthdate'] as String?,
      age: json['age'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'weight': weight,
      'height': height,
      'birthdate': birthdate,
      'age': age,
    };
  }

  UserProfile copyWith({
    int? id,
    String? username,
    double? weight,
    double? height,
    String? birthdate,
    int? age,
  }) {
    return UserProfile(
      id: id ?? this.id,
      username: username ?? this.username,
      weight: weight ?? this.weight,
      height: height ?? this.height,
      birthdate: birthdate ?? this.birthdate,
      age: age ?? this.age,
    );
  }
}
