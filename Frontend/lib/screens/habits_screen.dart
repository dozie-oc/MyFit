import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import '../main.dart' show TabActivatedNotifier;

// ─────────────────────────────────────────
// HABITS SCREEN — HabitKit-style
// ─────────────────────────────────────────

// 8-colour palette (matches backend HABIT_COLOR_PALETTE)
const List<Color> kHabitPalette = [
  Color(0xFF6366F1), // indigo
  Color(0xFF10B981), // emerald
  Color(0xFFF59E0B), // amber
  Color(0xFFEF4444), // red
  Color(0xFF3B82F6), // blue
  Color(0xFFEC4899), // pink
  Color(0xFF8B5CF6), // violet
  Color(0xFF14B8A6), // teal
];

Color _colorFromHex(String hex) {
  final h = hex.replaceFirst('#', '');
  return Color(int.parse('FF$h', radix: 16));
}

String _fmtDate(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

// ─────────────────────────────────────────
// DAY STATE (derived from the server's /habits/activity)
// ─────────────────────────────────────────

enum DayState { completed, eligible, targetMet, future }

/// Today plus the Monday-anchored start of the 5-week grid.
({DateTime today, DateTime gridStart}) _gridWindow() {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final mondayOfThisWeek = today.subtract(Duration(days: today.weekday - 1));
  return (
    today: today,
    gridStart: mondayOfThisWeek.subtract(const Duration(days: 28)),
  );
}

class _HabitsData {
  final List<Habit> habits;
  final Map<String, HabitActivityDay> activityByDate;
  const _HabitsData({required this.habits, required this.activityByDate});
}

Map<String, HabitActivityDay> _indexActivity(List<HabitActivityDay> days) {
  return {
    for (final d in days) d.date: d,
  };
}

/// Map the backend's per-day completed/pending id lists to a [DayState]
/// for every day in the 35-day grid. The backend owns the week-target
/// accounting; a day that is neither completed nor pending (but is on or
/// after the habit's creation date and not in the future) means the
/// weekly target was already met.
Map<String, DayState> _dayStatesFromActivity(
  Habit habit,
  Map<String, HabitActivityDay> activityByDate,
  DateTime gridStart,
  DateTime today,
) {
  final habitId = habit.id;

  DateTime? habitCreatedAt;
  final parsed = DateTime.tryParse(habit.createdAt ?? '');
  if (parsed != null) {
    habitCreatedAt = DateTime(parsed.year, parsed.month, parsed.day);
  }

  final result = <String, DayState>{};
  for (int i = 0; i < 35; i++) {
    final d = gridStart.add(Duration(days: i));
    final ds = _fmtDate(d);

    if (d.isAfter(today) ||
        (habitCreatedAt != null && d.isBefore(habitCreatedAt))) {
      result[ds] = DayState.future;
      continue;
    }

    final activity = activityByDate[ds];
    final completed = activity?.completedHabitIds ?? const [];
    final pending = activity?.pendingHabitIds ?? const [];

    if (completed.contains(habitId)) {
      result[ds] = DayState.completed;
    } else if (pending.contains(habitId)) {
      result[ds] = DayState.eligible;
    } else {
      result[ds] = DayState.targetMet;
    }
  }
  return result;
}

// ─────────────────────────────────────────
// SCREEN
// ─────────────────────────────────────────

class HabitsScreen extends StatefulWidget {
  final TabActivatedNotifier? tabNotifier;
  const HabitsScreen({super.key, this.tabNotifier});

  @override
  State<HabitsScreen> createState() => _HabitsScreenState();
}

class _HabitsScreenState extends State<HabitsScreen> {
  late Future<_HabitsData> _future;

  /// Habits (with logs) plus the server-computed per-day eligibility for
  /// the visible grid window. The server is the single source of truth
  /// for week-target accounting.
  Future<_HabitsData> _load() async {
    final w = _gridWindow();
    final gridEnd = w.gridStart.add(const Duration(days: 34));
    final results = await Future.wait([
      ApiClient.getHabits(),
      ApiClient.getHabitActivity(
        dateFrom: _fmtDate(w.gridStart),
        dateTo: _fmtDate(gridEnd),
      ),
    ]);
    return _HabitsData(
      habits: results[0] as List<Habit>,
      activityByDate: _indexActivity(results[1] as List<HabitActivityDay>),
    );
  }

  @override
  void initState() {
    super.initState();
    _future = _load();
    ApiClient.addDataListener(_onDataChanged, {DataScope.habits});
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
        _future = _load();
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
        title: const Text('Habits'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () async {
              final created = await showModalBottomSheet<bool>(
                context: context,
                isScrollControlled: true,
                shape: const RoundedRectangleBorder(
                    borderRadius:
                        BorderRadius.vertical(top: Radius.circular(20))),
                builder: (_) => const _AddHabitSheet(),
              );
              if (created == true) _reload();
            },
          ),
        ],
      ),
      body: FutureBuilder<_HabitsData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snap.hasError) {
            return ErrorView(
                message: snap.error.toString(), onRetry: _reload);
          }
          final habits = snap.data?.habits ?? [];
          if (habits.isEmpty) {
            return RefreshIndicator(
              onRefresh: _handleRefresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [
                  SizedBox(height: 80),
                  EmptyView(
                      message:
                          'No habits yet.\nTap + to add your first habit.',
                      icon: Icons.checklist_outlined),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _handleRefresh,
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(top: 12, bottom: 100),
              itemCount: habits.length,
              itemBuilder: (_, i) => _HabitCard(
                habit: habits[i],
                activityByDate: snap.data!.activityByDate,
                onChanged: _reload,
              ),
            ),
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────
// HABIT CARD
// ─────────────────────────────────────────

class _HabitCard extends StatefulWidget {
  final Habit habit;
  final Map<String, HabitActivityDay> activityByDate;
  final VoidCallback onChanged;
  const _HabitCard({
    required this.habit,
    required this.activityByDate,
    required this.onChanged,
  });

  @override
  State<_HabitCard> createState() => _HabitCardState();
}

class _HabitCardState extends State<_HabitCard> {
  late Map<String, DayState> _dayStates;
  late DateTime _gridStart;
  late DateTime _today;

  @override
  void initState() {
    super.initState();
    _initGrid();
  }

  @override
  void didUpdateWidget(_HabitCard old) {
    super.didUpdateWidget(old);
    _initGrid();
  }

  void _initGrid() {
    final w = _gridWindow();
    _today = w.today;
    _gridStart = w.gridStart;
    _dayStates = _dayStatesFromActivity(
        widget.habit, widget.activityByDate, _gridStart, _today);
  }

  Color get _habitColor => _colorFromHex(widget.habit.color);

  Future<void> _tapDay(DateTime day) async {
    final ds = _fmtDate(day);
    final currentState = _dayStates[ds];
    if (currentState == DayState.future) return;

    final habitId = widget.habit.id;

    // Optimistic local update — flip state immediately for instant visual feedback.
    final wasCompleted = currentState == DayState.completed;
    setState(() {
      _dayStates[ds] = wasCompleted ? DayState.eligible : DayState.completed;
    });

    try {
      if (wasCompleted) {
        await ApiClient.logHabit(habitId, ds, false);
      } else {
        await ApiClient.logHabit(habitId, ds, true);
      }
      // logHabit() emits a DataScope.habits change, which reloads this
      // screen (and the dashboard) with accurate week-target accounting.
    } catch (_) {
      // Revert optimistic update on failure
      if (mounted) {
        setState(() {
          _dayStates[ds] = currentState ?? DayState.eligible;
        });
      }
    }
  }

  int _completedThisWeek() {
    int count = 0;
    final now = _today;
    // Monday of current week
    final monday = now.subtract(Duration(days: now.weekday - 1));
    for (int i = 0; i < 7; i++) {
      final d = monday.add(Duration(days: i));
      if (d.isAfter(now)) break;
      final ds = _fmtDate(d);
      if (_dayStates[ds] == DayState.completed) count++;
    }
    return count;
  }

  @override
  Widget build(BuildContext context) {
    final name = widget.habit.name;
    final target = widget.habit.targetPerWeek;
    final doneThisWeek = _completedThisWeek();
    final color = _habitColor;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Header row ──────────────────────────
              Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                        color: color,
                        shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(name,
                        style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF111827))),
                  ),
                  // Edit button
                  GestureDetector(
                    onTap: () async {
                      await showModalBottomSheet<bool>(
                        context: context,
                        isScrollControlled: true,
                        shape: const RoundedRectangleBorder(
                            borderRadius: BorderRadius.vertical(
                                top: Radius.circular(20))),
                        builder: (_) => _EditHabitSheet(
                          habit: widget.habit,
                        ),
                      );
                      widget.onChanged();
                    },
                    child: const Icon(Icons.edit_outlined,
                        size: 16, color: Color(0xFF9CA3AF)),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: () async {
                      try {
                        await ApiClient.deleteHabit(widget.habit.id);
                        widget.onChanged();
                      } catch (_) {}
                    },
                    child: const Icon(Icons.delete_outline,
                        size: 16, color: Color(0xFF9CA3AF)),
                  ),
                ],
              ),

              const SizedBox(height: 4),

              // ── Progress subtitle ───────────────────
              Row(
                children: [
                  Text(
                    target == 7
                        ? 'Daily · $doneThisWeek/7 this week'
                        : '$target×/week · $doneThisWeek/$target this week',
                    style: const TextStyle(
                        fontSize: 12, color: Color(0xFF6B7280)),
                  ),
                  const Spacer(),
                  // Today quick-toggle
                  GestureDetector(
                    onTap: () => _tapDay(_today),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: _dayStates[_fmtDate(_today)] ==
                                DayState.completed
                            ? color
                            : color.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _dayStates[_fmtDate(_today)] ==
                                    DayState.completed
                                ? Icons.check
                                : Icons.add,
                            size: 12,
                            color: _dayStates[_fmtDate(_today)] ==
                                    DayState.completed
                                ? Colors.white
                                : color,
                          ),
                          const SizedBox(width: 3),
                          Text(
                            _dayStates[_fmtDate(_today)] ==
                                    DayState.completed
                                ? 'Done'
                                : 'Log today',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: _dayStates[_fmtDate(_today)] ==
                                      DayState.completed
                                  ? Colors.white
                                  : color,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // ── 30-day mini calendar grid ────────────
              _HabitCalendarGrid(
                gridStart: _gridStart,
                today: _today,
                dayStates: _dayStates,
                color: color,
                onTapDay: _tapDay,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// HABIT CALENDAR GRID (30-day)
// ─────────────────────────────────────────

class _HabitCalendarGrid extends StatelessWidget {
  final DateTime gridStart;
  final DateTime today;
  final Map<String, DayState> dayStates;
  final Color color;
  final void Function(DateTime) onTapDay;

  const _HabitCalendarGrid({
    required this.gridStart,
    required this.today,
    required this.dayStates,
    required this.color,
    required this.onTapDay,
  });

  @override
  Widget build(BuildContext context) {
    // Day-of-week headers (M T W T F S S)
    const headers = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Day-of-week headers
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: headers
              .map((h) => SizedBox(
                    width: 28,
                    child: Center(
                      child: Text(h,
                          style: const TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w500,
                              color: Color(0xFFD1D5DB))),
                    ),
                  ))
              .toList(),
        ),
        const SizedBox(height: 4),

        // 5-week grid
        for (int row = 0; row < 5; row++)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: List.generate(7, (col) {
                final d = gridStart.add(Duration(days: row * 7 + col));
                final ds = _fmtDate(d);
                final state = dayStates[ds];

                final canTap = !d.isAfter(today) && state != null;
                return GestureDetector(
                  onTap: canTap ? () => onTapDay(d) : null,
                  child: _DayCell(
                    day: d,
                    today: today,
                    state: state,
                    color: color,
                  ),
                );
              }),
            ),
          ),
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  final DateTime day;
  final DateTime today;
  final DayState? state;
  final Color color;

  const _DayCell({
    required this.day,
    required this.today,
    required this.state,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isToday = day == today;
    final dayNum = day.day.toString();

    Color? bgColor;
    Color textColor = const Color(0xFF9CA3AF);

    switch (state) {
      case DayState.completed:
        bgColor = color;
        textColor = Colors.white;
      case DayState.eligible:
        bgColor = color.withValues(alpha: 0.18);
        textColor = color.withValues(alpha: 0.85);
      case DayState.targetMet:
        bgColor = null;
        textColor = const Color(0xFFD1D5DB);
      case DayState.future:
        bgColor = null;
        textColor = const Color(0xFFD1D5DB);
      case null:
        // Day outside window (padding)
        bgColor = null;
        textColor = Colors.transparent;
    }

    return SizedBox(
      width: 28,
      height: 28,
      child: Container(
        decoration: BoxDecoration(
          color: bgColor,
          shape: BoxShape.circle,
          border: isToday
              ? Border.all(color: color, width: 1.5)
              : null,
        ),
        child: Center(
          child: Text(
            state == null ? '' : dayNum,
            style: TextStyle(
                fontSize: 11,
                fontWeight: isToday ? FontWeight.w700 : FontWeight.w500,
                color: textColor),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// ADD HABIT SHEET
// ─────────────────────────────────────────

class _AddHabitSheet extends StatefulWidget {
  const _AddHabitSheet();

  @override
  State<_AddHabitSheet> createState() => _AddHabitSheetState();
}

class _AddHabitSheetState extends State<_AddHabitSheet> {
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  int _targetPerWeek = 7;
  int _selectedColorIndex = 0;
  bool _saving = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  String _freqLabel(int n) {
    if (n == 7) return 'Daily (every day)';
    if (n == 1) return 'Once per week';
    return '$n times per week';
  }

  String _colorHex(int i) {
    const hexes = [
      '#6366F1', '#10B981', '#F59E0B', '#EF4444',
      '#3B82F6', '#EC4899', '#8B5CF6', '#14B8A6',
    ];
    return hexes[i % hexes.length];
  }

  Future<void> _save() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      await ApiClient.createHabit(
        _nameCtrl.text.trim(),
        description: _descCtrl.text.trim().isEmpty
            ? null
            : _descCtrl.text.trim(),
        color: _colorHex(_selectedColorIndex),
        targetPerWeek: _targetPerWeek,
      );
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
    return Padding(
      padding:
          EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                    color: const Color(0xFFD1D5DB),
                    borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),
            const Text('New Habit',
                style: TextStyle(
                    fontSize: 17, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),

            TextField(
              controller: _nameCtrl,
              autofocus: true,
              decoration:
                  const InputDecoration(labelText: 'Habit name'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _descCtrl,
              decoration: const InputDecoration(
                  labelText: 'Description (optional)'),
              maxLines: 2,
            ),

            const SizedBox(height: 16),

            // Colour picker
            const Text('Colour',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF6B7280))),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              children: List.generate(kHabitPalette.length, (i) {
                final selected = i == _selectedColorIndex;
                return GestureDetector(
                  onTap: () =>
                      setState(() => _selectedColorIndex = i),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    width: 32, height: 32,
                    decoration: BoxDecoration(
                      color: kHabitPalette[i],
                      shape: BoxShape.circle,
                      border: selected
                          ? Border.all(
                              color: Colors.white, width: 3)
                          : null,
                      boxShadow: selected
                          ? [
                              BoxShadow(
                                  color: kHabitPalette[i]
                                      .withValues(alpha: 0.5),
                                  blurRadius: 6)
                            ]
                          : null,
                    ),
                    child: selected
                        ? const Icon(Icons.check,
                            size: 16, color: Colors.white)
                        : null,
                  ),
                );
              }),
            ),

            const SizedBox(height: 18),

            // Frequency
            const Text('Frequency',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF6B7280))),
            const SizedBox(height: 6),
            Text(_freqLabel(_targetPerWeek),
                style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: kHabitPalette[_selectedColorIndex])),
            Slider(
              value: _targetPerWeek.toDouble(),
              min: 1,
              max: 7,
              divisions: 6,
              activeColor: kHabitPalette[_selectedColorIndex],
              onChanged: (v) =>
                  setState(() => _targetPerWeek = v.round()),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: const [
                Text('1×/wk',
                    style: TextStyle(
                        fontSize: 11, color: Color(0xFF9CA3AF))),
                Text('Daily',
                    style: TextStyle(
                        fontSize: 11, color: Color(0xFF9CA3AF))),
              ],
            ),

            const SizedBox(height: 24),

            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                    backgroundColor:
                        kHabitPalette[_selectedColorIndex]),
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(
                        width: 18, height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white))
                    : const Text('Add Habit'),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// EDIT HABIT SHEET
// ─────────────────────────────────────────

class _EditHabitSheet extends StatefulWidget {
  final Habit habit;
  const _EditHabitSheet({required this.habit});

  @override
  State<_EditHabitSheet> createState() => _EditHabitSheetState();
}

class _EditHabitSheetState extends State<_EditHabitSheet> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _descCtrl;
  late int _targetPerWeek;
  late int _selectedColorIndex;
  bool _saving = false;

  static const _hexes = [
    '#6366F1', '#10B981', '#F59E0B', '#EF4444',
    '#3B82F6', '#EC4899', '#8B5CF6', '#14B8A6',
  ];

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.habit.name);
    _descCtrl = TextEditingController(text: widget.habit.description ?? '');
    _targetPerWeek = widget.habit.targetPerWeek;
    final currentHex = widget.habit.color;
    _selectedColorIndex =
        _hexes.indexOf(currentHex).clamp(0, _hexes.length - 1);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  String _freqLabel(int n) {
    if (n == 7) return 'Daily (every day)';
    if (n == 1) return 'Once per week';
    return '$n times per week';
  }

  Future<void> _save() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      await ApiClient.updateHabit(
        widget.habit.id,
        name: _nameCtrl.text.trim(),
        description: _descCtrl.text.trim().isEmpty
            ? null
            : _descCtrl.text.trim(),
        color: _hexes[_selectedColorIndex],
        targetPerWeek: _targetPerWeek,
      );
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
    return Padding(
      padding:
          EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                    color: const Color(0xFFD1D5DB),
                    borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),
            const Text('Edit Habit',
                style: TextStyle(
                    fontSize: 17, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),

            TextField(
                controller: _nameCtrl,
                decoration:
                    const InputDecoration(labelText: 'Habit name')),
            const SizedBox(height: 10),
            TextField(
              controller: _descCtrl,
              decoration: const InputDecoration(
                  labelText: 'Description (optional)'),
              maxLines: 2,
            ),

            const SizedBox(height: 16),

            const Text('Colour',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF6B7280))),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              children: List.generate(kHabitPalette.length, (i) {
                final selected = i == _selectedColorIndex;
                return GestureDetector(
                  onTap: () =>
                      setState(() => _selectedColorIndex = i),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    width: 32, height: 32,
                    decoration: BoxDecoration(
                      color: kHabitPalette[i],
                      shape: BoxShape.circle,
                      border: selected
                          ? Border.all(
                              color: Colors.white, width: 3)
                          : null,
                      boxShadow: selected
                          ? [
                              BoxShadow(
                                  color: kHabitPalette[i]
                                      .withValues(alpha: 0.5),
                                  blurRadius: 6)
                            ]
                          : null,
                    ),
                    child: selected
                        ? const Icon(Icons.check,
                            size: 16, color: Colors.white)
                        : null,
                  ),
                );
              }),
            ),

            const SizedBox(height: 18),

            const Text('Frequency',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF6B7280))),
            const SizedBox(height: 6),
            Text(_freqLabel(_targetPerWeek),
                style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: kHabitPalette[_selectedColorIndex])),
            Slider(
              value: _targetPerWeek.toDouble(),
              min: 1,
              max: 7,
              divisions: 6,
              activeColor: kHabitPalette[_selectedColorIndex],
              onChanged: (v) =>
                  setState(() => _targetPerWeek = v.round()),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: const [
                Text('1×/wk',
                    style: TextStyle(
                        fontSize: 11, color: Color(0xFF9CA3AF))),
                Text('Daily',
                    style: TextStyle(
                        fontSize: 11, color: Color(0xFF9CA3AF))),
              ],
            ),

            const SizedBox(height: 24),

            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                    backgroundColor:
                        kHabitPalette[_selectedColorIndex]),
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(
                        width: 18, height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Text('Save Changes'),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// ACTIVITY RING WIDGET (reused by dashboard)
// ─────────────────────────────────────────

class HabitActivityRing extends StatelessWidget {
  /// All habits (need id + color).
  final List<Habit> habits;

  /// IDs of completed habits for this day.
  final List<int> completedIds;

  /// IDs of eligible-but-not-done habits for this day.
  final List<int> pendingIds;

  final double size;
  final double strokeWidth;

  const HabitActivityRing({
    super.key,
    required this.habits,
    required this.completedIds,
    required this.pendingIds,
    this.size = 24,
    this.strokeWidth = 3.5,
  });

  @override
  Widget build(BuildContext context) {
    if (habits.isEmpty && completedIds.isEmpty && pendingIds.isEmpty) {
      return SizedBox(width: size, height: size);
    }

    // Build relevant segment list (completed + pending)
    final segments = <_RingSegment>[];
    for (final h in habits) {
      final id = h.id;
      final color = _colorFromHex(h.color);
      if (completedIds.contains(id)) {
        segments.add(_RingSegment(color: color, opacity: 1.0));
      } else if (pendingIds.contains(id)) {
        segments.add(_RingSegment(color: color, opacity: 0.25));
      }
    }

    if (segments.isEmpty) {
      return SizedBox(width: size, height: size);
    }

    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RingPainter(segments: segments, strokeWidth: strokeWidth),
      ),
    );
  }
}

class _RingSegment {
  final Color color;
  final double opacity;
  const _RingSegment({required this.color, required this.opacity});
}

class _RingPainter extends CustomPainter {
  final List<_RingSegment> segments;
  final double strokeWidth;

  const _RingPainter(
      {required this.segments, required this.strokeWidth});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final radius = (math.min(cx, cy)) - strokeWidth / 2;
    final rect =
        Rect.fromCircle(center: Offset(cx, cy), radius: radius);

    final n = segments.length;
    const gapAngle = 0.06; // radians gap between segments
    final sweepPerSegment =
        (2 * math.pi - n * gapAngle) / n;

    for (int i = 0; i < n; i++) {
      final startAngle =
          -math.pi / 2 + i * (sweepPerSegment + gapAngle);
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round
        ..color = segments[i]
            .color
            .withValues(alpha: segments[i].opacity);
      canvas.drawArc(rect, startAngle, sweepPerSegment, false, paint);
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.segments != segments || old.strokeWidth != strokeWidth;
}
