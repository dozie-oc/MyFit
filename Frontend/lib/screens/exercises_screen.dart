import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'custom_exercise_screen.dart';
import 'recommendation_sheet.dart';
import '../main.dart' show TabActivatedNotifier;

// ─────────────────────────────────────────
// EXERCISES SCREEN
// ─────────────────────────────────────────

class ExercisesScreen extends StatefulWidget {
  final TabActivatedNotifier? tabNotifier;
  const ExercisesScreen({super.key, this.tabNotifier});

  @override
  State<ExercisesScreen> createState() => _ExercisesScreenState();
}

class _ExercisesScreenState extends State<ExercisesScreen> {
  late Future<List<Exercise>> _future;
  String _selectedCategory = 'all';

  @override
  void initState() {
    super.initState();
    _future = ApiClient.getExercises();
    ApiClient.addDataListener(_onDataChanged, {DataScope.exercises});
    widget.tabNotifier?.addListener(_onTabActivated);
  }

  @override
  void dispose() {
    ApiClient.removeDataListener(_onDataChanged);
    widget.tabNotifier?.removeListener(_onTabActivated);
    super.dispose();
  }

  void _onDataChanged() {
    _reload();
  }

  void _onTabActivated() {
    _reload();
  }

  void _reload() {
    if (mounted) {
      setState(() {
        _future = ApiClient.getExercises();
      });
    }
  }

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
      floatingActionButton: const RecommendationFAB(filterType: 'exercise'),
      body: Column(
        children: [
          // Training adequacy status banner
          const _TrainingAdequacyBanner(),
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
            child: FutureBuilder<List<Exercise>>(
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
                        .where((e) => e.category.toLowerCase() == _selectedCategory)
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
                      onEdited: _reload,
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
  final Exercise exercise;
  final VoidCallback onDeleted;
  final VoidCallback? onEdited;
  const _ExerciseCard({
    required this.exercise,
    required this.onDeleted,
    this.onEdited,
  });

  @override
  Widget build(BuildContext context) {
    final name = exercise.name;
    final date = exercise.date;
    final category = exercise.category;
    final cal = exercise.caloriesBurned;
    final mins = exercise.durationMinutes;
    final reps = exercise.reps;
    final sets = exercise.sets;
    final weight = exercise.weightKg;
    final dist = exercise.distanceKm;
    final intensity = exercise.intensity;
    final effortLabel = exercise.effortLabel;

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
    if (effortLabel != null) details.add('Effort: $effortLabel');
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
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      GestureDetector(
                        onTap: () async {
                          final updated = await showModalBottomSheet<bool>(
                            context: context,
                            isScrollControlled: true,
                            shape: const RoundedRectangleBorder(
                              borderRadius: BorderRadius.vertical(
                                  top: Radius.circular(16)),
                            ),
                            builder: (_) =>
                                _LogExerciseSheet(existing: exercise),
                          );
                          if (updated == true) {
                            (onEdited ?? onDeleted)();
                          }
                        },
                        child: const Icon(Icons.edit_outlined,
                            size: 18, color: Color(0xFF9CA3AF)),
                      ),
                      const SizedBox(width: 10),
                      GestureDetector(
                        onTap: () async {
                          try {
                            await ApiClient.deleteExercise(exercise.id);
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
  final Exercise? existing;
  const _LogExerciseSheet({this.existing});

  @override
  State<_LogExerciseSheet> createState() => _LogExerciseSheetState();
}

class _LogExerciseSheetState extends State<_LogExerciseSheet> {
  final _nameCtrl = TextEditingController();
  final _minsCtrl = TextEditingController();
  // Strength fields — default values only shown for strength category
  final _setsCtrl = TextEditingController();
  final _repsCtrl = TextEditingController();
  final _weightCtrl = TextEditingController();
  // Cardio-only field
  final _distCtrl = TextEditingController();
  // Effort rating (1-5) — optional perceived effort indicator for strength
  int? _effortRating;

  String _category = 'strength'; // 'strength', 'cardio', 'flexibility', 'other'
  String _intensity = 'moderate'; // 'low', 'moderate', 'high'
  int? _selectedCatalogId;
  List<ExerciseCatalogItem> _catalog = [];
  Timer? _historyDebounce;
  ExerciseHistory? _history;

  DateTime _date = DateTime.now();
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final ex = widget.existing;
    if (ex != null) {
      _nameCtrl.text = ex.name;
      _category = ex.category.isNotEmpty ? ex.category.toLowerCase() : 'strength';
      _selectedCatalogId = ex.exerciseCatalogId;
      if (ex.sets != null) _setsCtrl.text = ex.sets.toString();
      if (ex.reps != null) _repsCtrl.text = ex.reps.toString();
      if (ex.weightKg != null) _weightCtrl.text = ex.weightKg.toString();
      if (ex.durationMinutes != null) {
        _minsCtrl.text = ex.durationMinutes.toString();
      }
      if (ex.distanceKm != null) _distCtrl.text = ex.distanceKm.toString();
      if (ex.intensity != null && ex.intensity!.isNotEmpty) {
        _intensity = ex.intensity!;
      }
      _effortRating = ex.effortRating;
      final parsedDate = DateTime.tryParse(ex.date);
      if (parsedDate != null) _date = parsedDate;
    } else {
      // Strength defaults — only populated when category = strength
      _setsCtrl.text = '3';
      _repsCtrl.text = '10';
    }
    _nameCtrl.addListener(_onNameChanged);
    _loadCatalog();
    if (ex != null && _category == 'strength') {
      _fetchHistory(catalogId: _selectedCatalogId, name: ex.name);
    }
  }

  Future<void> _loadCatalog() async {
    try {
      final items = await ApiClient.getExerciseCatalog();
      if (mounted) setState(() => _catalog = items);
    } catch (_) {}
  }

  void _onNameChanged() {
    final text = _nameCtrl.text.trim();
    if (_selectedCatalogId != null) {
      final match = _catalog.where((c) => c.id == _selectedCatalogId).firstOrNull;
      if (match != null && match.name.toLowerCase() != text.toLowerCase()) {
        _selectedCatalogId = null;
      }
    }
    _historyDebounce?.cancel();
    if (_category != 'strength' || text.length < 3) {
      if (_history != null && mounted) {
        setState(() => _history = null);
      }
      return;
    }
    _historyDebounce = Timer(const Duration(milliseconds: 500), () {
      _fetchHistory(catalogId: _selectedCatalogId, name: text);
    });
  }

  Future<void> _fetchHistory({int? catalogId, required String name}) async {
    final queryName = name.trim();
    if (_category != 'strength' || queryName.isEmpty) return;
    try {
      final hist = await ApiClient.getExerciseHistory(
        catalogId: catalogId,
        name: queryName,
      );
      if (!mounted) return;
      if (_nameCtrl.text.trim().toLowerCase() != queryName.toLowerCase()) {
        return;
      }
      setState(() => _history = hist);
    } catch (_) {}
  }

  String _formatHistorySummary(ExerciseHistory hist) {
    final last = hist.last!;
    final parts = <String>[];
    final wStr = last.weightKg != null && last.weightKg! > 0
        ? '${last.weightKg! % 1 == 0 ? last.weightKg!.toInt() : last.weightKg} kg'
        : 'bodyweight';
    final rStr = last.reps != null ? ' x ${last.reps}' : '';
    final sStr = last.sets != null ? ' x ${last.sets}' : '';
    parts.add('Last: $wStr$rStr$sStr');

    final parsed = DateTime.tryParse(last.date);
    if (parsed != null) {
      final today = DateTime.now();
      final todayDate = DateTime(today.year, today.month, today.day);
      final logDate = DateTime(parsed.year, parsed.month, parsed.day);
      final diff = todayDate.difference(logDate).inDays;
      if (diff <= 0) {
        parts.add('today');
      } else if (diff == 1) {
        parts.add('1 day ago');
      } else {
        parts.add('$diff days ago');
      }
    }

    if (hist.bestEst1rm != null && hist.bestEst1rm! > 0) {
      final rm = hist.bestEst1rm! % 1 == 0
          ? hist.bestEst1rm!.toInt().toString()
          : hist.bestEst1rm!.toStringAsFixed(1);
      parts.add('Best est. 1RM $rm kg');
    }
    return parts.join(' - ');
  }

  void _applyLastHistory() {
    final last = _history?.last;
    if (last == null) return;
    setState(() {
      if (last.sets != null) _setsCtrl.text = last.sets.toString();
      if (last.reps != null) _repsCtrl.text = last.reps.toString();
      if (last.weightKg != null) _weightCtrl.text = last.weightKg.toString();
    });
  }

  @override
  void dispose() {
    _historyDebounce?.cancel();
    _nameCtrl.removeListener(_onNameChanged);
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

  void _switchCategory(String newCat) {
    setState(() {
      _category = newCat;
      _selectedCatalogId = null;
      // Clear fields that don't apply to the new category
      if (newCat == 'strength') {
        _setsCtrl.text = '3';
        _repsCtrl.text = '10';
        _minsCtrl.clear();
        _distCtrl.clear();
      } else {
        // Non-strength: clear sets/reps/weight/effortRating
        _setsCtrl.clear();
        _repsCtrl.clear();
        _weightCtrl.clear();
        _effortRating = null;
        if (newCat == 'flexibility') {
          // Flexibility: also clear distance (not applicable)
          _distCtrl.clear();
          _intensity = 'low';
        } else {
          _intensity = 'moderate';
        }
      }
    });
  }

  void _selectCatalogItem(ExerciseCatalogItem item) {
    final cat = item.category.isEmpty ? 'cardio' : item.category;
    if (cat != _category) {
      _switchCategory(cat);
    }
    setState(() {
      _selectedCatalogId = item.id;
      _nameCtrl.text = item.name;
    });
    if (cat == 'strength') {
      _historyDebounce?.cancel();
      _fetchHistory(catalogId: item.id, name: item.name);
    }
  }

  Future<void> _openCreateCustomExercise() async {
    final created = await Navigator.push<ExerciseCatalogItem>(
      context,
      MaterialPageRoute(
        builder: (_) => CustomExerciseScreen(
          initialName: _nameCtrl.text.trim(),
          initialCategory: _category == 'other' ? 'strength' : _category,
        ),
      ),
    );
    if (created != null && mounted) {
      await _loadCatalog();
      _selectCatalogItem(created);
    }
  }

  Future<void> _showCustomItemActions(ExerciseCatalogItem item) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title: const Text('Edit custom exercise'),
              onTap: () => Navigator.pop(ctx, 'edit'),
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline, color: Colors.red),
              title: const Text('Delete custom exercise',
                  style: TextStyle(color: Colors.red)),
              onTap: () => Navigator.pop(ctx, 'delete'),
            ),
          ],
        ),
      ),
    );
    if (!mounted || action == null) return;
    if (action == 'edit') {
      final updated = await Navigator.push<ExerciseCatalogItem>(
        context,
        MaterialPageRoute(
          builder: (_) => CustomExerciseScreen(existing: item),
        ),
      );
      if (updated != null && mounted) {
        await _loadCatalog();
        _selectCatalogItem(updated);
      }
    } else if (action == 'delete') {
      try {
        await ApiClient.deleteCustomExercise(item.id);
        if (mounted) {
          if (_selectedCatalogId == item.id) {
            setState(() => _selectedCatalogId = null);
          }
          await _loadCatalog();
        }
      } catch (_) {}
    }
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Exercise name is required.')));
      return;
    }

    final mins = int.tryParse(_minsCtrl.text.trim());

    // Only parse strength fields when category is strength
    final isStrength = _category == 'strength';
    final isCardio = _category == 'cardio';
    final sets = isStrength ? int.tryParse(_setsCtrl.text.trim()) : null;
    final reps = isStrength ? int.tryParse(_repsCtrl.text.trim()) : null;
    final weight =
        isStrength ? double.tryParse(_weightCtrl.text.trim()) : null;
    final dist =
        isCardio ? double.tryParse(_distCtrl.text.trim()) : null;

    setState(() => _saving = true);
    try {
      final effortVal = isStrength ? _effortRating : null;
      final body = <String, dynamic>{
        'date': _dateStr,
        'name': name,
        'category': _category,
        if (_selectedCatalogId != null) 'exercise_catalog_id': _selectedCatalogId,
        if (sets != null) 'sets': sets,
        if (reps != null) 'reps': reps,
        if (weight != null) 'weight_kg': weight,
        if (mins != null) 'duration_minutes': mins,
        if (dist != null) 'distance_km': dist,
        'intensity': _intensity,
        if (effortVal != null || widget.existing != null)
          'effort_rating': effortVal,
      };
      final Exercise saved;
      if (widget.existing != null) {
        saved = await ApiClient.updateExercise(widget.existing!.id, body);
      } else {
        saved = await ApiClient.createExercise(body);
      }
      if (mounted) {
        if (saved.isPr) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('New personal best')),
          );
        }
        Navigator.pop(context, true);
      }
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
    final isCardio = _category == 'cardio';
    final isFlexibility = _category == 'flexibility';

    final filteredCatalog =
        _catalog.where((it) => it.category == _category).toList();

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
            Text(
                widget.existing != null ? 'Edit exercise' : 'Log Exercise',
                style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),

            // ── Category Selector ─────────────────
            Wrap(
              spacing: 8,
              children: [
                ChoiceChip(
                  label: const Text('Strength'),
                  selected: _category == 'strength',
                  onSelected: (_) => _switchCategory('strength'),
                ),
                ChoiceChip(
                  label: const Text('Cardio'),
                  selected: _category == 'cardio',
                  onSelected: (_) => _switchCategory('cardio'),
                ),
                ChoiceChip(
                  label: const Text('Flexibility'),
                  selected: _category == 'flexibility',
                  onSelected: (_) => _switchCategory('flexibility'),
                ),
                ChoiceChip(
                  label: const Text('Other'),
                  selected: _category == 'other',
                  onSelected: (_) => _switchCategory('other'),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // ── Catalogue Quick Picks ─────────────
            if (filteredCatalog.isNotEmpty) ...[
              const Text('Popular Exercises',
                  style: TextStyle(
                      fontSize: 12,
                      color: Color(0xFF6B7280),
                      fontWeight: FontWeight.w500)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  ...filteredCatalog.where((it) => it.isCustom),
                  ...filteredCatalog.where((it) => !it.isCustom).take(8),
                ].map((catItem) {
                  final isSelected = _nameCtrl.text == catItem.name;
                  final chip = ActionChip(
                    avatar: isSelected
                        ? const Icon(Icons.check, size: 14)
                        : null,
                    label: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(catItem.name,
                            style: const TextStyle(fontSize: 12)),
                        if (catItem.isCustom) ...[
                          const SizedBox(width: 4),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 4, vertical: 1),
                            decoration: BoxDecoration(
                              color: const Color(0xFFE0E7FF),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'Custom',
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF4338CA),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    onPressed: () => _selectCatalogItem(catItem),
                  );
                  if (catItem.isCustom) {
                    return GestureDetector(
                      onLongPress: () => _showCustomItemActions(catItem),
                      child: chip,
                    );
                  }
                  return chip;
                }).toList(),
              ),
              const SizedBox(height: 8),
            ],
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: _openCreateCustomExercise,
                icon: const Icon(Icons.add, size: 16),
                label: const Text("Can't find it? Create your own",
                    style: TextStyle(fontSize: 12)),
              ),
            ),
            const SizedBox(height: 8),

            TextField(
              controller: _nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Exercise Name',
                hintText: 'e.g. Bench Press, Running, Yoga',
              ),
            ),
            if (isStrength && _history != null && _history!.last != null) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      _formatHistorySummary(_history!),
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF6B7280),
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: _applyLastHistory,
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: const Size(0, 28),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: const Text('Use last',
                        style: TextStyle(fontSize: 12)),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 16),

            // ── STRENGTH fields ───────────────────
            if (isStrength) ...[
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _setsCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Sets'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _repsCtrl,
                      decoration: const InputDecoration(
                          labelText: 'Reps / Set'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _weightCtrl,
                      decoration: const InputDecoration(
                          labelText: 'Weight (kg)',
                          hintText: 'Optional'),
                      keyboardType: const TextInputType.numberWithOptions(
                          decimal: true),
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(
                            RegExp(r'[\d.]'))
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _minsCtrl,
                decoration: const InputDecoration(
                  labelText: 'Duration (min)',
                  hintText: 'Estimated from sets if omitted',
                ),
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              ),
              const SizedBox(height: 12),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Effort Rating (optional)',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF374151),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: Exercise.effortLabels.entries.map((entry) {
                  final rating = entry.key;
                  final label = entry.value;
                  final selected = _effortRating == rating;
                  return ChoiceChip(
                    label: Text('$rating · $label'),
                    selected: selected,
                    onSelected: (v) {
                      setState(() {
                        _effortRating = v ? rating : null;
                      });
                    },
                  );
                }).toList(),
              ),
              if (_effortRating != null &&
                  Exercise.effortDescriptions[_effortRating] != null) ...[
                const SizedBox(height: 6),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    Exercise.effortDescriptions[_effortRating]!,
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xFF6B7280),
                    ),
                  ),
                ),
              ],
            ],

            // ── CARDIO fields ─────────────────────
            if (isCardio) ...[
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _minsCtrl,
                      decoration: const InputDecoration(
                          labelText: 'Duration (min) *'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _distCtrl,
                      decoration: const InputDecoration(
                          labelText: 'Distance (km)',
                          hintText: 'Optional'),
                      keyboardType: const TextInputType.numberWithOptions(
                          decimal: true),
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(
                            RegExp(r'[\d.]'))
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              _IntensityPicker(
                value: _intensity,
                onChanged: (v) => setState(() => _intensity = v),
              ),
            ],

            // ── FLEXIBILITY fields ────────────────
            if (isFlexibility) ...[
              TextField(
                controller: _minsCtrl,
                decoration: const InputDecoration(
                  labelText: 'Duration (min) *',
                  hintText: 'e.g. 20 (minutes of stretching)',
                ),
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              ),
            ],

            // ── OTHER fields ──────────────────────
            if (!isStrength && !isCardio && !isFlexibility) ...[
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _minsCtrl,
                      decoration: const InputDecoration(
                          labelText: 'Duration (min)'),
                      keyboardType: TextInputType.number,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              _IntensityPicker(
                value: _intensity,
                onChanged: (v) => setState(() => _intensity = v),
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
                    : Text(widget.existing != null
                        ? 'Save Changes'
                        : 'Log Workout'),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// INTENSITY PICKER (shared by cardio/other)
// ─────────────────────────────────────────

class _IntensityPicker extends StatelessWidget {
  final String value;
  final void Function(String) onChanged;
  const _IntensityPicker({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Text('Intensity: ',
            style:
                TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
        const SizedBox(width: 8),
        ChoiceChip(
          label: const Text('Low'),
          selected: value == 'low',
          onSelected: (_) => onChanged('low'),
        ),
        const SizedBox(width: 8),
        ChoiceChip(
          label: const Text('Moderate'),
          selected: value == 'moderate',
          onSelected: (_) => onChanged('moderate'),
        ),
        const SizedBox(width: 8),
        ChoiceChip(
          label: const Text('High'),
          selected: value == 'high',
          onSelected: (_) => onChanged('high'),
        ),
      ],
    );
  }
}


// ─────────────────────────────────────────
// TRAINING ADEQUACY BANNER
// ─────────────────────────────────────────

class _TrainingAdequacyBanner extends StatefulWidget {
  const _TrainingAdequacyBanner();

  @override
  State<_TrainingAdequacyBanner> createState() => _TrainingAdequacyBannerState();
}

class _TrainingAdequacyBannerState extends State<_TrainingAdequacyBanner> {
  Future<TrainingAdequacy>? _future;
  bool _expanded = false;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.getTrainingAdequacy();
    ApiClient.addDataListener(
        _onDataChanged, {DataScope.exercises, DataScope.goal});
  }

  @override
  void dispose() {
    ApiClient.removeDataListener(_onDataChanged);
    super.dispose();
  }

  void _onDataChanged() {
    if (mounted) {
      setState(() => _future = ApiClient.getTrainingAdequacy());
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<TrainingAdequacy>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting || snap.hasError || snap.data == null) {
          return const SizedBox.shrink();
        }

        final data = snap.data!;
        final summary = data.summary;
        final detail = data.detail;
        final sessionAction = data.sessionAction;
        final exercisesToday = data.exercisesToday;
        final totalSets = data.totalSetsToday;
        final recommendedNext = data.recommendedNext;
        final muscleGroups = data.muscleGroups;

        // Determine banner style based on session action
        Color bannerColor;
        IconData bannerIcon;
        switch (sessionAction) {
          case 'workout_adequate':
            bannerColor = const Color(0xFF10B981); // green
            bannerIcon = Icons.check_circle_rounded;
            break;
          case 'rest':
            bannerColor = const Color(0xFF6366F1); // indigo
            bannerIcon = Icons.hotel_rounded;
            break;
          default: // continue_workout
            bannerColor = const Color(0xFFF59E0B); // amber
            bannerIcon = Icons.trending_up_rounded;
        }

        return AnimatedSize(
          duration: const Duration(milliseconds: 200),
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            decoration: BoxDecoration(
              color: bannerColor.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: bannerColor.withValues(alpha: 0.25)),
            ),
            child: InkWell(
              onTap: () => setState(() => _expanded = !_expanded),
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header row
                    Row(
                      children: [
                        Icon(bannerIcon, size: 18, color: bannerColor),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                summary,
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700,
                                  color: bannerColor,
                                ),
                              ),
                              if (exercisesToday > 0)
                                Text(
                                  '$exercisesToday exercises · ${totalSets.toStringAsFixed(0)} total sets',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: Color(0xFF9CA3AF),
                                  ),
                                ),
                              Text(
                                'Cardio this week: ${data.cardioWeek.minutes.toStringAsFixed(0)} / ${data.cardioWeek.targetMinutes} min',
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: Color(0xFF6B7280),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          _expanded ? Icons.expand_less : Icons.expand_more,
                          size: 18,
                          color: const Color(0xFF9CA3AF),
                        ),
                      ],
                    ),

                    // Expanded detail
                    if (_expanded) ...[
                      const SizedBox(height: 8),
                      Text(
                        detail,
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280), height: 1.4),
                      ),

                      // Recommended next actions
                      if (recommendedNext.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        ...recommendedNext.map((r) => Padding(
                          padding: const EdgeInsets.only(bottom: 3),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.arrow_forward_rounded, size: 12, color: bannerColor),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  r,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: bannerColor,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        )),
                      ],

                      // Muscle group mini-bars (only show muscles with > 0 sets)
                      if (muscleGroups.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: muscleGroups
                              .where((mg) => mg.setsCompleted > 0)
                              .map((mg) {
                                final name = mg.muscleGroup.replaceAll('_', '/');
                                final status = mg.status;
                                final sets = mg.setsCompleted;

                                Color chipColor;
                                switch (status) {
                                  case 'adequate':
                                    chipColor = const Color(0xFF10B981);
                                    break;
                                  case 'high':
                                    chipColor = const Color(0xFF6366F1);
                                    break;
                                  default: // undertrained
                                    chipColor = const Color(0xFFF59E0B);
                                }

                                return Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: chipColor.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Text(
                                    '$name ${sets.toStringAsFixed(1)}s',
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w500,
                                      color: chipColor,
                                    ),
                                  ),
                                );
                              })
                              .toList(),
                        ),
                      ],
                    ],
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
