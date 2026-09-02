import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';

// ─────────────────────────────────────────
// DASHBOARD / HOME SCREEN
// ─────────────────────────────────────────

class DashboardScreen extends StatefulWidget {
  final Map<String, dynamic> user;
  const DashboardScreen({super.key, required this.user});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<_DashboardData> _future;
  String _today = '';

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _today =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    _future = _load();

    // Auto-reload whenever any data in the app changes
    ApiClient.dataChangeNotifier.addListener(_onDataChanged);
  }

  @override
  void dispose() {
    ApiClient.dataChangeNotifier.removeListener(_onDataChanged);
    super.dispose();
  }

  void _onDataChanged() {
    if (mounted) {
      setState(() {
        _future = _load();
      });
    }
  }

  Future<_DashboardData> _load() async {
    final results = await Future.wait([
      ApiClient.getSummary(_today).catchError((_) => <String, dynamic>{}),
      ApiClient.getMeals(_today),
      ApiClient.getExercises(_today),
      ApiClient.getHabits(),
    ]);

    Map<String, dynamic> summary = {};
    if (results[0] is Map<String, dynamic>) {
      summary = results[0] as Map<String, dynamic>;
    }

    return _DashboardData(
      summary: summary,
      meals: results[1] as List<dynamic>,
      exercises: results[2] as List<dynamic>,
      habits: results[3] as List<dynamic>,
    );
  }

  Future<void> _handleRefresh() async {
    setState(() {
      _future = _load();
    });
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.user;
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Hello, ${user['username'] ?? 'User'}',
                style: const TextStyle(fontSize: 16)),
            Text(_today,
                style: const TextStyle(
                    fontSize: 12, color: Color(0xFF9CA3AF))),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_outlined),
            onPressed: () => setState(() => _future = _load()),
          ),
        ],
      ),
      body: FutureBuilder<_DashboardData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snap.hasError) {
            return ErrorView(
                message: snap.error.toString(),
                onRetry: () => setState(() => _future = _load()));
          }
          final data = snap.data!;
          return RefreshIndicator(
            onRefresh: _handleRefresh,
            child: _DashboardContent(data: data, today: _today),
          );
        },
      ),
    );
  }
}

class _DashboardData {
  final Map<String, dynamic> summary;
  final List<dynamic> meals;
  final List<dynamic> exercises;
  final List<dynamic> habits;
  const _DashboardData(
      {required this.summary,
      required this.meals,
      required this.exercises,
      required this.habits});
}

class _DashboardContent extends StatelessWidget {
  final _DashboardData data;
  final String today;
  const _DashboardContent({required this.data, required this.today});

  @override
  Widget build(BuildContext context) {
    final s = data.summary;
    final caloriesIn = (s['calories_in'] as num?)?.toDouble() ?? 0;
    final caloriesOut = (s['calories_out'] as num?)?.toDouble() ?? 0;
    final net = caloriesIn - caloriesOut;

    final totalProtein = data.meals.fold<double>(0, (acc, m) {
      return acc + ((m['protein'] as num?)?.toDouble() ?? 0);
    });
    final totalCarbs = data.meals.fold<double>(0, (acc, m) {
      return acc + ((m['carbs'] as num?)?.toDouble() ?? 0);
    });
    final totalFat = data.meals.fold<double>(0, (acc, m) {
      return acc + ((m['fat'] as num?)?.toDouble() ?? 0);
    });

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        // ── Calorie summary card ──────────────
        const SectionHeader(title: "TODAY'S SUMMARY"),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _SummaryStat(
                          label: 'In',
                          value: caloriesIn.toStringAsFixed(0),
                          unit: 'kcal',
                          color: const Color(0xFF2563EB)),
                      _SummaryStat(
                          label: 'Burned',
                          value: caloriesOut.toStringAsFixed(0),
                          unit: 'kcal',
                          color: const Color(0xFFEF4444)),
                      _SummaryStat(
                          label: 'Net',
                          value: net.toStringAsFixed(0),
                          unit: 'kcal',
                          color: net <= 0
                              ? const Color(0xFF10B981)
                              : const Color(0xFFF59E0B)),
                    ],
                  ),
                  const SizedBox(height: 16),
                  NutrientRow(
                    calories: caloriesIn,
                    protein: totalProtein,
                    carbs: totalCarbs,
                    fat: totalFat,
                  ),
                ],
              ),
            ),
          ),
        ),

        // ── Meals ─────────────────────────────
        SectionHeader(
          title: "MEALS",
          trailing: Text('${data.meals.length} logged',
              style: const TextStyle(
                  fontSize: 12, color: Color(0xFF9CA3AF))),
        ),
        if (data.meals.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No meals logged today.',
                    style: TextStyle(color: Color(0xFF9CA3AF))),
              ),
            ),
          )
        else
          ...data.meals.map((m) => _MealTile(meal: m)),

        // ── Exercises ─────────────────────────
        SectionHeader(
          title: "EXERCISES",
          trailing: Text('${data.exercises.length} sessions',
              style: const TextStyle(
                  fontSize: 12, color: Color(0xFF9CA3AF))),
        ),
        if (data.exercises.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No exercises logged today.',
                    style: TextStyle(color: Color(0xFF9CA3AF))),
              ),
            ),
          )
        else
          ...data.exercises.map((e) => _ExerciseTile(exercise: e)),

        const SizedBox(height: 24),
      ],
    );
  }
}

class _SummaryStat extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  final Color color;
  const _SummaryStat(
      {required this.label,
      required this.value,
      required this.unit,
      required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: TextStyle(
                fontSize: 22, fontWeight: FontWeight.w700, color: color)),
        Text(unit,
            style:
                const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
        Text(label,
            style:
                const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
      ],
    );
  }
}

class _MealTile extends StatelessWidget {
  final Map<String, dynamic> meal;
  const _MealTile({required this.meal});

  @override
  Widget build(BuildContext context) {
    final cal = (meal['calories'] as num?)?.toDouble() ?? 0;
    final items = (meal['items'] as List?) ?? [];

    String itemSummary = '';
    if (items.isNotEmpty) {
      final names = items.map((it) {
        final name = (it['food_name'] as String?) ?? '';
        final gram = (it['gram_weight'] as num?)?.toStringAsFixed(0) ?? '';
        return name.isNotEmpty ? (gram.isNotEmpty ? '$name (${gram}g)' : name) : 'Food #${it['food_id']}';
      }).toList();
      itemSummary = names.join(', ');
    } else {
      itemSummary = 'No food items';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              const Icon(Icons.restaurant_outlined,
                  size: 18, color: Color(0xFF9CA3AF)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      itemSummary,
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text('${items.length} item${items.length == 1 ? '' : 's'}',
                        style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text('${cal.toStringAsFixed(0)} kcal',
                  style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF2563EB))),
            ],
          ),
        ),
      ),
    );
  }
}

class _ExerciseTile extends StatelessWidget {
  final Map<String, dynamic> exercise;
  const _ExerciseTile({required this.exercise});

  @override
  Widget build(BuildContext context) {
    final name = exercise['name'] as String? ?? '';
    final category = exercise['category'] as String? ?? '';
    final cal = (exercise['calories_burned'] as num?)?.toDouble() ?? 0;
    final mins = exercise['duration_minutes'];
    final reps = exercise['reps'];
    final sets = exercise['sets'];
    final weight = (exercise['weight_kg'] as num?)?.toDouble();
    final dist = (exercise['distance_km'] as num?)?.toDouble();
    final intensity = exercise['intensity'] as String?;

    IconData iconData = Icons.fitness_center;
    if (category == 'cardio') {
      iconData = Icons.directions_run;
    } else if (category == 'flexibility') {
      iconData = Icons.self_improvement;
    }

    final details = <String>[];
    if (sets != null && reps != null) {
      details.add('$sets sets × $reps reps');
      if (weight != null && weight > 0) details.add('@ ${weight}kg');
    } else if (reps != null) {
      details.add('$reps reps');
    }
    if (mins != null) details.add('$mins min');
    if (dist != null && dist > 0) details.add('${dist}km');
    if (intensity != null && intensity.isNotEmpty && intensity != 'moderate') {
      details.add(intensity);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(iconData, size: 18, color: const Color(0xFF9CA3AF)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                    if (details.isNotEmpty)
                      Text(
                        details.join(' · '),
                        style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
                      ),
                  ],
                ),
              ),
              Text('${cal.toStringAsFixed(0)} kcal',
                  style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFFEF4444))),
            ],
          ),
        ),
      ),
    );
  }
}
