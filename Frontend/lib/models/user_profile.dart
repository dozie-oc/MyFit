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
    final id = (json['id'] as num?)?.toInt();
    if (id == null) throw const FormatException('UserProfile.id is required');
    return UserProfile(
      id: id,
      username: json['username'] as String? ?? '',
      weight: (json['weight'] as num?)?.toDouble(),
      height: (json['height'] as num?)?.toDouble(),
      birthdate: json['birthdate'] as String?,
      age: json['age'] as int?,
    );
  }
}
