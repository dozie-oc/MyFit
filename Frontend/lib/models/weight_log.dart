class WeightLog {
  final int id;
  final String date;
  final double weight;

  const WeightLog({
    required this.id,
    required this.date,
    required this.weight,
  });

  factory WeightLog.fromJson(Map<String, dynamic> json) {
    final id = (json['id'] as num?)?.toInt();
    if (id == null) {
      throw const FormatException('WeightLog.id is required');
    }
    return WeightLog(
      id: id,
      date: json['date'] as String? ?? '',
      weight: (json['weight'] as num?)?.toDouble() ?? 0.0,
    );
  }
}
