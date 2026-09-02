import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';

// ─────────────────────────────────────────
// HABITS SCREEN
// ─────────────────────────────────────────

class HabitsScreen extends StatefulWidget {
  const HabitsScreen({super.key});

  @override
  State<HabitsScreen> createState() => _HabitsScreenState();
}

class _HabitsScreenState extends State<HabitsScreen> {
  late Future<List<dynamic>> _future;
  String _today = '';

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _today =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    _future = ApiClient.getHabits();
    ApiClient.dataChangeNotifier.addListener(_onDataChanged);
  }

  @override
  void dispose() {
    ApiClient.dataChangeNotifier.removeListener(_onDataChanged);
    super.dispose();
  }

  void _onDataChanged() {
    if (mounted) {
      setState(() => _future = ApiClient.getHabits());
    }
  }

  void _reload() => setState(() => _future = ApiClient.getHabits());

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
                    borderRadius: BorderRadius.vertical(
                        top: Radius.circular(16))),
                builder: (_) => const _AddHabitSheet(),
              );
              if (created == true) _reload();
            },
          ),
        ],
      ),
      body: FutureBuilder<List<dynamic>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snap.hasError) {
            return ErrorView(
                message: snap.error.toString(), onRetry: _reload);
          }
          final habits = snap.data ?? [];
          if (habits.isEmpty) {
            return RefreshIndicator(
              onRefresh: _handleRefresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [
                  SizedBox(height: 100),
                  EmptyView(
                      message: 'No habits yet. Tap + to add one.',
                      icon: Icons.checklist_outlined),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _handleRefresh,
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(top: 8, bottom: 80),
              itemCount: habits.length,
              itemBuilder: (_, i) => _HabitCard(
                habit: habits[i],
                today: _today,
                onChanged: _reload,
              ),
            ),
          );
        },
      ),
    );
  }
}

class _HabitCard extends StatefulWidget {
  final Map<String, dynamic> habit;
  final String today;
  final VoidCallback onChanged;
  const _HabitCard(
      {required this.habit,
      required this.today,
      required this.onChanged});

  @override
  State<_HabitCard> createState() => _HabitCardState();
}

class _HabitCardState extends State<_HabitCard> {
  bool? _todayCompleted;
  bool _loadingLog = true;

  @override
  void initState() {
    super.initState();
    _loadLog();
  }

  Future<void> _loadLog() async {
    try {
      final logs = await ApiClient.getHabitLogs(widget.habit['id'] as int);
      final todayLog = logs.cast<Map<String, dynamic>>().where((l) =>
          l['date'] == widget.today).toList();
      if (todayLog.isNotEmpty) {
        setState(() {
          _todayCompleted = todayLog.first['completed'] as bool;
          _loadingLog = false;
        });
      } else {
        setState(() => _loadingLog = false);
      }
    } catch (_) {
      setState(() => _loadingLog = false);
    }
  }

  Future<void> _toggle() async {
    final next = !(_todayCompleted ?? false);
    setState(() => _todayCompleted = next);
    try {
      await ApiClient.logHabit(
          widget.habit['id'] as int, widget.today, next);
    } catch (_) {
      setState(() => _todayCompleted = !next);
    }
  }

  @override
  Widget build(BuildContext context) {
    final name = widget.habit['name'] as String? ?? '';
    final desc = widget.habit['description'] as String?;
    final done = _todayCompleted ?? false;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Card(
        child: ListTile(
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          leading: _loadingLog
              ? const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : GestureDetector(
                  onTap: _toggle,
                  child: Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: done
                          ? const Color(0xFF10B981)
                          : Colors.transparent,
                      border: Border.all(
                        color: done
                            ? const Color(0xFF10B981)
                            : const Color(0xFFD1D5DB),
                        width: 2,
                      ),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: done
                        ? const Icon(Icons.check,
                            size: 14, color: Colors.white)
                        : null,
                  ),
                ),
          title: Text(name,
              style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  decoration: done
                      ? TextDecoration.lineThrough
                      : TextDecoration.none,
                  color: done
                      ? const Color(0xFF9CA3AF)
                      : const Color(0xFF111827))),
          subtitle: desc != null && desc.isNotEmpty
              ? Text(desc,
                  style: const TextStyle(fontSize: 12))
              : null,
          trailing: IconButton(
            icon: const Icon(Icons.delete_outline,
                size: 18, color: Color(0xFF9CA3AF)),
            onPressed: () async {
              try {
                await ApiClient.deleteHabit(
                    widget.habit['id'] as int);
                widget.onChanged();
              } catch (_) {}
            },
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
  bool _saving = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      await ApiClient.createHabit(
          _nameCtrl.text.trim(),
          _descCtrl.text.trim().isEmpty ? null : _descCtrl.text.trim());
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
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
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
            const Text('New Habit',
                style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),
            TextField(
              controller: _nameCtrl,
              autofocus: true,
              decoration:
                  const InputDecoration(labelText: 'Habit name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descCtrl,
              decoration: const InputDecoration(
                  labelText: 'Description (optional)'),
              maxLines: 2,
            ),
            const SizedBox(height: 20),
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
