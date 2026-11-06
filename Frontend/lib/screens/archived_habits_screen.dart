import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'habits_screen.dart';

// ─────────────────────────────────────────
// ARCHIVED HABITS SCREEN
// ─────────────────────────────────────────

class ArchivedHabitsScreen extends StatefulWidget {
  const ArchivedHabitsScreen({super.key});

  @override
  State<ArchivedHabitsScreen> createState() => _ArchivedHabitsScreenState();
}

class _ArchivedHabitsData {
  final List<Habit> habits;
  final Map<String, HabitActivityDay> activityByDate;
  const _ArchivedHabitsData({required this.habits, required this.activityByDate});
}

class _ArchivedHabitsScreenState extends State<ArchivedHabitsScreen> {
  late Future<_ArchivedHabitsData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_ArchivedHabitsData> _load() async {
    final w = gridWindow();
    final gridEnd = w.gridStart.add(const Duration(days: 34));
    final results = await Future.wait([
      ApiClient.getArchivedHabits(),
      ApiClient.getHabitActivity(
        dateFrom: fmtDate(w.gridStart),
        dateTo: fmtDate(gridEnd),
      ),
    ]);
    final habits = results[0] as List<Habit>;
    final activityList = results[1] as List<HabitActivityDay>;
    return _ArchivedHabitsData(
      habits: habits,
      activityByDate: {for (final d in activityList) d.date: d},
    );
  }

  void _reload() {
    if (mounted) {
      setState(() {
        _future = _load();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Archived Habits'),
      ),
      body: FutureBuilder<_ArchivedHabitsData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snap.hasError) {
            return ErrorView(
              message: snap.error.toString(),
              onRetry: _reload,
            );
          }
          final habits = snap.data?.habits ?? [];
          if (habits.isEmpty) {
            return RefreshIndicator(
              onRefresh: () async {
                _reload();
                await _future;
              },
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [
                  SizedBox(height: 80),
                  EmptyView(
                    icon: Icons.archive_outlined,
                    message:
                        'No archived habits.\nHabits you archive will appear here with their full history.',
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () async {
              _reload();
              await _future;
            },
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(top: 12, bottom: 80),
              itemCount: habits.length,
              itemBuilder: (_, i) => _ArchivedHabitCard(
                habit: habits[i],
                activityByDate: snap.data!.activityByDate,
                onRestored: _reload,
              ),
            ),
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────
// ARCHIVED HABIT CARD
// ─────────────────────────────────────────

class _ArchivedHabitCard extends StatelessWidget {
  final Habit habit;
  final Map<String, HabitActivityDay> activityByDate;
  final VoidCallback onRestored;

  const _ArchivedHabitCard({
    required this.habit,
    required this.activityByDate,
    required this.onRestored,
  });

  @override
  Widget build(BuildContext context) {
    final color = colorFromHex(habit.color);
    final w = gridWindow();
    final dayStates = dayStatesFromActivity(habit, activityByDate, w.gridStart, w.today);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header row
              Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          habit.name,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF111827),
                          ),
                        ),
                        if (habit.description != null && habit.description!.trim().isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                              habit.description!,
                              style: const TextStyle(
                                fontSize: 12,
                                color: Color(0xFF6B7280),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF3F4F6),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Text(
                      'Archived',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF6B7280),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              // Subtitle & Restore action
              Row(
                children: [
                  Text(
                    habit.targetPerWeek == 7
                        ? 'Daily target'
                        : '${habit.targetPerWeek}×/week target',
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xFF6B7280),
                    ),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: () => _confirmRestore(context),
                    icon: const Icon(Icons.unarchive_outlined, size: 16),
                    label: const Text('Restore', style: TextStyle(fontSize: 12)),
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // Read-only 35-day grid
              HabitCalendarGrid(
                gridStart: w.gridStart,
                today: w.today,
                dayStates: dayStates,
                color: color,
                onTapDay: (_) {},
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _confirmRestore(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Restore Habit'),
        content: Text('Restore "${habit.name}" back to active habits?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFF2563EB),
            ),
            child: const Text('Restore'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      await ApiClient.restoreHabit(habit.id);
      onRestored();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Restored "${habit.name}" to active habits')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to restore: $e')),
        );
      }
    }
  }
}
