class DailySummary {
  final String date;
  final int caloriesIn;
  final int caloriesOut;
  final int netCalories;

  const DailySummary({
    required this.date,
    required this.caloriesIn,
    required this.caloriesOut,
    required this.netCalories,
  });

  const DailySummary.empty([String defaultDate = ''])
      : date = defaultDate,
        caloriesIn = 0,
        caloriesOut = 0,
        netCalories = 0;

  double get caloriesInDouble => caloriesIn.toDouble();
  double get caloriesOutDouble => caloriesOut.toDouble();
  double get netCaloriesDouble => netCalories.toDouble();

  factory DailySummary.fromJson(Map<String, dynamic> json) {
    final calIn = (json['calories_in'] as num?)?.round() ?? 0;
    final calOut = (json['calories_out'] as num?)?.round() ?? 0;
    final net = (json['net_calories'] as num?)?.round() ?? (calIn - calOut);

    return DailySummary(
      date: json['date'] as String? ?? '',
      caloriesIn: calIn,
      caloriesOut: calOut,
      netCalories: net,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'calories_in': caloriesIn,
      'calories_out': caloriesOut,
      'net_calories': netCalories,
    };
  }

  DailySummary copyWith({
    String? date,
    int? caloriesIn,
    int? caloriesOut,
    int? netCalories,
  }) {
    return DailySummary(
      date: date ?? this.date,
      caloriesIn: caloriesIn ?? this.caloriesIn,
      caloriesOut: caloriesOut ?? this.caloriesOut,
      netCalories: netCalories ?? this.netCalories,
    );
  }
}
