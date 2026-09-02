import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api_client.dart';
import '../theme.dart';

// ─────────────────────────────────────────
// EXERCISES SCREEN
// ─────────────────────────────────────────

class ExercisesScreen extends StatefulWidget {
  const ExercisesScreen({super.key});

  @override
  State<ExercisesScreen> createState() => _ExercisesScreenState();
}

class _ExercisesScreenState extends State<ExercisesScreen> {
  late Future<List<dynamic>> _future;
  String _selectedCategory = 'all';

  @override
  void initState() {
    super.initState();
    _future = ApiClient.getExercises();
    ApiClient.dataChangeNotifier.addListener(_onDataChanged);
  }

  @override
  void dispose() {
    ApiClient.dataChangeNotifier.removeListener(_onDataChanged);
    super.dispose();
  }

  void _onDataChanged() {
    if (mounted) {
      setState(() => _future = ApiClient.getExercises());
    }
  }

  void _reload() => setState(() => _future = ApiClient.getExercises());

  Future<void> _handleRefresh() async {
    _reload();
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Exercises'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () async {
              final created = await showModalBottomSheet<bool>(
                context: context,
                isScrollControlled: true,
                shape: const RoundedRectangleBorder(
                    borderRadius: BorderRadius.vertical(
                        top: Radius.circular(16))),
                builder: (_) => const _LogExerciseSheet(),
              );
              if (created == true) _reload();
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Category filter chips
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _CategoryFilterChip(
                  label: 'All',
                  selected: _selectedCategory == 'all',
                  onSelected: () => setState(() => _selectedCategory = 'all'),
                ),
                const SizedBox(width: 8),
                _CategoryFilterChip(
                  label: 'Strength',
                  selected: _selectedCategory == 'strength',
                  onSelected: () => setState(() => _selectedCategory = 'strength'),
                ),
                const SizedBox(width: 8),
                _CategoryFilterChip(
                  label: 'Cardio',
                  selected: _selectedCategory == 'cardio',
                  onSelected: () => setState(() => _selectedCategory = 'cardio'),
                ),
                const SizedBox(width: 8),
                _CategoryFilterChip(
                  label: 'Flexibility',
                  selected: _selectedCategory == 'flexibility',
                  onSelected: () => setState(() => _selectedCategory = 'flexibility'),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snap) {
                if (snap.connectionState == ConnectionState.waiting) {
                  return const LoadingView();
                }
                if (snap.hasError) {
                  return ErrorView(
                      message: snap.error.toString(), onRetry: _reload);
                }
                final allExercises = snap.data ?? [];
                final exercises = _selectedCategory == 'all'
                    ? allExercises
                    : allExercises
                        .where((e) => (e['category'] as String?)?.toLowerCase() == _selectedCategory)
                        .toList();

                if (exercises.isEmpty) {
                  return RefreshIndicator(
                    onRefresh: _handleRefresh,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        const SizedBox(height: 100),
                        EmptyView(
                            message: _selectedCategory == 'all'
                                ? 'No exercises logged. Tap + to log one.'
                                : 'No $_selectedCategory exercises logged yet.',
                            icon: Icons.fitness_center),
                      ],
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: _handleRefresh,
                  child: ListView.builder(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.only(top: 8, bottom: 80),
                    itemCount: exercises.length,
                    itemBuilder: (_, i) => _ExerciseCard(
                      exercise: exercises[i],
                      onDeleted: _reload,
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _CategoryFilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onSelected;

  const _CategoryFilterChip({
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      onSelected: (_) => onSelected(),
      showCheckmark: false,
    );
  }
}

class _ExerciseCard extends StatelessWidget {
  final Map<String, dynamic> exercise;
  final VoidCallback onDeleted;
  const _ExerciseCard(
      {required this.exercise, required this.onDeleted});

  @override
  Widget build(BuildContext context) {
    final name = exercise['name'] as String? ?? '';
    final date = exercise['date'] as String? ?? '';
    final category = exercise['category'] as String? ?? 'other';
    final cal = (exercise['calories_burned'] as num?)?.toDouble() ?? 0;
    final mins = exercise['duration_minutes'];
    final reps = exercise['reps'];
    final sets = exercise['sets'];
    final weight = (exercise['weight_kg'] as num?)?.toDouble();
    final dist = (exercise['distance_km'] as num?)?.toDouble();
    final intensity = exercise['intensity'] as String?;

    IconData iconData = Icons.fitness_center;
    Color iconColor = const Color(0xFFEF4444);
    if (category == 'cardio') {
      iconData = Icons.directions_run;
      iconColor = const Color(0xFF2563EB);
    } else if (category == 'flexibility') {
      iconData = Icons.self_improvement;
      iconColor = const Color(0xFF10B981);
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
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(
              horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(iconData, size: 20, color: iconColor),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14)),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(date,
                            style: const TextStyle(
                                fontSize: 12,
                                color: Color(0xFF9CA3AF))),
                        if (details.isNotEmpty) ...[
                          const Text(' · ',
                              style: TextStyle(
                                  color: Color(0xFF9CA3AF))),
                          Expanded(
                            child: Text(
                              details.join(' · '),
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF6B7280)),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('${cal.toStringAsFixed(0)} kcal',
                      style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFFEF4444))),
                  const SizedBox(height: 4),
                  GestureDetector(
                    onTap: () async {
                      try {
                        await ApiClient.deleteExercise(
                            exercise['id'] as int);
                        onDeleted();
                      } catch (_) {}
                    },
                    child: const Icon(Icons.delete_outline,
                        size: 18, color: Color(0xFF9CA3AF)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// LOG EXERCISE SHEET
// ─────────────────────────────────────────

class _LogExerciseSheet extends StatefulWidget {
  const _LogExerciseSheet();

  @override
  State<_LogExerciseSheet> createState() => _LogExerciseSheetState();
}

class _LogExerciseSheetState extends State<_LogExerciseSheet> {
  final _nameCtrl = TextEditingController();
  final _minsCtrl = TextEditingController();
  final _setsCtrl = TextEditingController(text: '3');
  final _repsCtrl = TextEditingController(text: '10');
  final _weightCtrl = TextEditingController();
  final _distCtrl = TextEditingController();

  String _category = 'strength'; // 'strength', 'cardio', 'flexibility', 'other'
  String _intensity = 'moderate'; // 'low', 'moderate', 'high'
  int? _selectedCatalogId;
  List<dynamic> _catalog = [];

  DateTime _date = DateTime.now();
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadCatalog();
  }

  Future<void> _loadCatalog() async {
    try {
      final items = await ApiClient.getExerciseCatalog();
      if (mounted) setState(() => _catalog = items);
    } catch (_) {}
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _minsCtrl.dispose();
    _setsCtrl.dispose();
    _repsCtrl.dispose();
    _weightCtrl.dispose();
    _distCtrl.dispose();
    super.dispose();
  }

  String get _dateStr =>
      '${_date.year}-${_date.month.toString().padLeft(2, '0')}-${_date.day.toString().padLeft(2, '0')}';

  Future<void> _pickDate() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
    );
    if (d != null) setState(() => _date = d);
  }

  void _selectCatalogItem(Map<String, dynamic> item) {
    setState(() {
      _selectedCatalogId = item['id'] as int;
      _nameCtrl.text = item['name'] as String;
      _category = (item['category'] as String?)?.toLowerCase() ?? 'cardio';
    });
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Exercise name is required.')));
      return;
    }

    final mins = int.tryParse(_minsCtrl.text);
    final sets = int.tryParse(_setsCtrl.text);
    final reps = int.tryParse(_repsCtrl.text);
    final weight = double.tryParse(_weightCtrl.text);
    final dist = double.tryParse(_distCtrl.text);

    setState(() => _saving = true);
    try {
      await ApiClient.createExercise({
        'date': _dateStr,
        'name': name,
        'category': _category,
        'exercise_catalog_id': ?_selectedCatalogId,
        'sets': ?sets,
        'reps': ?reps,
        'weight_kg': ?weight,
        'duration_minutes': ?mins,
        'distance_km': ?dist,
        'intensity': _intensity,
      });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(e.message),
            backgroundColor: Colors.red.shade700));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isStrength = _category == 'strength';

    final filteredCatalog = _catalog.where((it) {
      final cat = (it['category'] as String?)?.toLowerCase() ?? '';
      return cat == _category;
    }).toList();

    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.85,
        builder: (_, ctrl) => ListView(
          controller: ctrl,
          padding: const EdgeInsets.all(20),
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                    color: const Color(0xFFD1D5DB),
                    borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),
            const Text('Log Exercise',
                style: TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),

            // Exercise Type Selector
            Row(
              children: [
                ChoiceChip(
                  label: const Text('Strength'),
                  selected: _category == 'strength',
                  onSelected: (_) => setState(() => _category = 'strength'),
                ),
                const SizedBox(width: 8),
                ChoiceChip(
                  label: const Text('Cardio'),
                  selected: _category == 'cardio',
                  onSelected: (_) => setState(() => _category = 'cardio'),
                ),
                const SizedBox(width: 8),
                ChoiceChip(
                  label: const Text('Flexibility'),
                  selected: _category == 'flexibility',
                  onSelected: (_) => setState(() => _category = 'flexibility'),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Catalogue Quick Picks
            if (filteredCatalog.isNotEmpty) ...[
              const Text('Popular Exercises',
                  style: TextStyle(fontSize: 12, color: Color(0xFF6B7280), fontWeight: FontWeight.w500)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: filteredCatalog.take(8).map((catItem) {
                  final isSelected = _nameCtrl.text == catItem['name'];
                  return ActionChip(
                    avatar: isSelected ? const Icon(Icons.check, size: 14) : null,
                    label: Text(catItem['name'] as String, style: const TextStyle(fontSize: 12)),
                    onPressed: () => _selectCatalogItem(catItem as Map<String, dynamic>),
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
            ],

            TextField(
              controller: _nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Exercise Name',
                hintText: 'e.g. Bench Press, Running, Yoga',
              ),
            ),
            const SizedBox(height: 16),

            // Dynamic fields based on Strength vs Cardio
            if (isStrength) ...[
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _setsCtrl,
                      decoration: const InputDecoration(labelText: 'Sets'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _repsCtrl,
                      decoration: const InputDecoration(labelText: 'Reps / Set'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _weightCtrl,
                      decoration: const InputDecoration(labelText: 'Weight (kg)', hintText: 'Optional'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _minsCtrl,
                decoration: const InputDecoration(
                  labelText: 'Workout Duration (min)',
                  hintText: 'Optional — estimated from sets if omitted',
                ),
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              ),
            ] else ...[
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _minsCtrl,
                      decoration: const InputDecoration(labelText: 'Duration (min) *'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _distCtrl,
                      decoration: const InputDecoration(labelText: 'Distance (km)', hintText: 'Optional'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  const Text('Intensity: ', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Low'),
                    selected: _intensity == 'low',
                    onSelected: (_) => setState(() => _intensity = 'low'),
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Moderate'),
                    selected: _intensity == 'moderate',
                    onSelected: (_) => setState(() => _intensity = 'moderate'),
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('High'),
                    selected: _intensity == 'high',
                    onSelected: (_) => setState(() => _intensity = 'high'),
                  ),
                ],
              ),
            ],

            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _pickDate,
              icon: const Icon(Icons.calendar_today, size: 16),
              label: Text('Date: $_dateStr'),
            ),
            const SizedBox(height: 24),

            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Text('Log Workout'),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
