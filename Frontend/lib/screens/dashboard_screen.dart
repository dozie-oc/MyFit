
import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'habits_screen.dart' show HabitActivityRing;

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
  DateTime _selectedDate = DateTime.now();
  late Future<_DashboardData> _future;

  @override
  void initState() {
    super.initState();
    _selectedDate = _stripTime(DateTime.now());
    _future = _load();
    ApiClient.dataChangeNotifier.addListener(_onDataChanged);
  }

  @override
  void dispose() {
    ApiClient.dataChangeNotifier.removeListener(_onDataChanged);
    super.dispose();
  }

  void _onDataChanged() {
    if (mounted) setState(() => _future = _load());
  }

  DateTime _stripTime(DateTime d) => DateTime(d.year, d.month, d.day);

  String _fmtDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<_DashboardData> _load() async {
    final dateStr = _fmtDate(_selectedDate);
    // Fetch 42 days of activity for the calendar (6 weeks back)
    final rangeStart = _selectedDate.subtract(const Duration(days: 41));
    final rangeEnd = _selectedDate.add(const Duration(days: 14));

    final results = await Future.wait([
      ApiClient.getSummary(dateStr).catchError((_) => <String, dynamic>{}),
      ApiClient.getMeals(dateStr),
      ApiClient.getExercises(dateStr),
      ApiClient.getHabits(),
      ApiClient.getHabitActivity(
        dateFrom: _fmtDate(rangeStart),
        dateTo: _fmtDate(rangeEnd),
      ),
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
      activity: results[4] as List<dynamic>,
    );
  }

  Future<void> _handleRefresh() async {
    setState(() => _future = _load());
    await _future;
  }

  void _selectDate(DateTime d) {
    final newDate = _stripTime(d);
    if (newDate == _selectedDate) return;
    setState(() {
      _selectedDate = newDate;
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      body: FutureBuilder<_DashboardData>(
        future: _future,
        builder: (context, snap) {
          final data = snap.data;
          final loading = snap.connectionState == ConnectionState.waiting &&
              data == null;

          return CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ── App bar + calendar strip ─────────────
              SliverAppBar(
                backgroundColor: Colors.white,
                surfaceTintColor: Colors.transparent,
                pinned: true,
                expandedHeight: 140,
                elevation: 0,
                titleSpacing: 0,
                flexibleSpace: FlexibleSpaceBar(
                  collapseMode: CollapseMode.pin,
                  background: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Top title area
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 52, 16, 0),
                        child: Row(
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Hello, ${widget.user['username'] ?? 'User'}',
                                  style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xFF111827)),
                                ),
                                Text(
                                  _humanDate(_selectedDate),
                                  style: const TextStyle(
                                      fontSize: 12,
                                      color: Color(0xFF9CA3AF)),
                                ),
                              ],
                            ),
                            const Spacer(),
                            IconButton(
                              icon: const Icon(Icons.refresh_outlined,
                                  size: 20),
                              onPressed: _handleRefresh,
                              color: const Color(0xFF9CA3AF),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                bottom: PreferredSize(
                  preferredSize: const Size.fromHeight(64),
                  child: _CalendarStrip(
                    selectedDate: _selectedDate,
                    habits: data?.habits ?? [],
                    activityByDate: _buildActivityMap(data?.activity ?? []),
                    onSelectDate: _selectDate,
                    onExpand: () => _openFullCalendar(data),
                  ),
                ),
              ),

              // ── Pull-to-refresh + content ────────────
              SliverToBoxAdapter(
                child: RefreshIndicator(
                  onRefresh: _handleRefresh,
                  child: loading
                      ? const Padding(
                          padding: EdgeInsets.only(top: 80),
                          child: LoadingView())
                      : snap.hasError
                          ? ErrorView(
                              message: snap.error.toString(),
                              onRetry: () =>
                                  setState(() => _future = _load()))
                          : _DashboardContent(
                              data: data!,
                              selectedDate: _selectedDate,
                            ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Map<String, Map<String, dynamic>> _buildActivityMap(
      List<dynamic> activity) {
    final m = <String, Map<String, dynamic>>{};
    for (final a in activity) {
      final d = a['date'] as String?;
      if (d != null) m[d] = a as Map<String, dynamic>;
    }
    return m;
  }

  void _openFullCalendar(_DashboardData? data) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => _FullCalendarModal(
        selectedDate: _selectedDate,
        habits: data?.habits ?? [],
        activityByDate: _buildActivityMap(data?.activity ?? []),
        onSelectDate: (d) {
          Navigator.pop(context);
          _selectDate(d);
        },
      ),
    );
  }

  String _humanDate(DateTime d) {
    const months = [
      '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    const weekdays = [
      '', 'Monday', 'Tuesday', 'Wednesday', 'Thursday',
      'Friday', 'Saturday', 'Sunday'
    ];
    return '${weekdays[d.weekday]}, ${d.day} ${months[d.month]} ${d.year}';
  }
}

// ─────────────────────────────────────────
// DATA HOLDER
// ─────────────────────────────────────────

class _DashboardData {
  final Map<String, dynamic> summary;
  final List<dynamic> meals;
  final List<dynamic> exercises;
  final List<dynamic> habits;
  final List<dynamic> activity;
  const _DashboardData({
    required this.summary,
    required this.meals,
    required this.exercises,
    required this.habits,
    required this.activity,
  });
}

// ─────────────────────────────────────────
// CALENDAR STRIP (7-day scrollable)
// ─────────────────────────────────────────

class _CalendarStrip extends StatefulWidget {
  final DateTime selectedDate;
  final List<dynamic> habits;
  final Map<String, Map<String, dynamic>> activityByDate;
  final void Function(DateTime) onSelectDate;
  final VoidCallback onExpand;

  const _CalendarStrip({
    required this.selectedDate,
    required this.habits,
    required this.activityByDate,
    required this.onSelectDate,
    required this.onExpand,
  });

  @override
  State<_CalendarStrip> createState() => _CalendarStripState();
}

class _CalendarStripState extends State<_CalendarStrip> {
  late final ScrollController _scrollCtrl;
  static const double _cellW = 52.0;

  DateTime _stripAnchor = DateTime.now(); // Monday of shown week

  @override
  void initState() {
    super.initState();
    _scrollCtrl = ScrollController();
    _stripAnchor = _mondayOf(DateTime.now());

    // After first frame, scroll so today is visible
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToSelected();
    });
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  DateTime _mondayOf(DateTime d) => d.subtract(Duration(days: d.weekday - 1));

  void _scrollToSelected() {
    final diff = widget.selectedDate
        .difference(_stripAnchor)
        .inDays
        .clamp(0, 99);
    final targetOffset = (diff * _cellW) - 100.0;
    if (_scrollCtrl.hasClients) {
      _scrollCtrl.animateTo(
        targetOffset.clamp(0.0, _scrollCtrl.position.maxScrollExtent),
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // Show 42 days: 3 weeks back to 3 weeks forward
    final start = _stripAnchor.subtract(const Duration(days: 14));
    final totalDays = 56;

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        children: [
          const Divider(height: 1),
          SizedBox(
            height: 72,
            child: Row(
              children: [
                // Scroll area
                Expanded(
                  child: ListView.builder(
                    controller: _scrollCtrl,
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 8),
                    itemCount: totalDays,
                    itemBuilder: (_, i) {
                      final d = start.add(Duration(days: i));
                      return _StripCell(
                        date: d,
                        isSelected: d == widget.selectedDate,
                        habits: widget.habits,
                        activity: widget.activityByDate[
                            _fmtDate(d)],
                        onTap: () => widget.onSelectDate(d),
                      );
                    },
                  ),
                ),
                // Expand button
                GestureDetector(
                  onTap: widget.onExpand,
                  child: Container(
                    width: 36,
                    height: double.infinity,
                    color: Colors.white,
                    child: const Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.expand_less_rounded,
                            size: 18, color: Color(0xFF9CA3AF)),
                        Icon(Icons.calendar_month_outlined,
                            size: 14, color: Color(0xFFD1D5DB)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _fmtDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

class _StripCell extends StatelessWidget {
  final DateTime date;
  final bool isSelected;
  final List<dynamic> habits;
  final Map<String, dynamic>? activity;
  final VoidCallback onTap;

  const _StripCell({
    required this.date,
    required this.isSelected,
    required this.habits,
    required this.activity,
    required this.onTap,
  });

  static const _dayLabels = ['', 'M', 'T', 'W', 'T', 'F', 'S', 'S'];

  @override
  Widget build(BuildContext context) {
    final isToday = _fmtDate(date) == _fmtDate(DateTime.now());
    final completed =
        (activity?['completed_habit_ids'] as List?)?.cast<int>() ?? [];
    final pending =
        (activity?['pending_habit_ids'] as List?)?.cast<int>() ?? [];
    final habitMaps =
        habits.whereType<Map<String, dynamic>>().toList();

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 48,
        margin: const EdgeInsets.symmetric(horizontal: 2),
        decoration: BoxDecoration(
          color: isSelected
              ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.08)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: isToday
              ? Border.all(
                  color: Theme.of(context)
                      .colorScheme
                      .primary
                      .withValues(alpha: 0.4),
                  width: 1.5)
              : null,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              _dayLabels[date.weekday],
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w500,
                color: isSelected
                    ? Theme.of(context).colorScheme.primary
                    : const Color(0xFF9CA3AF),
              ),
            ),
            const SizedBox(height: 2),
            Text(
              date.day.toString(),
              style: TextStyle(
                fontSize: 15,
                fontWeight: isToday || isSelected
                    ? FontWeight.w700
                    : FontWeight.w500,
                color: isSelected
                    ? Theme.of(context).colorScheme.primary
                    : isToday
                        ? const Color(0xFF111827)
                        : const Color(0xFF6B7280),
              ),
            ),
            const SizedBox(height: 4),
            // Activity ring
            HabitActivityRing(
              habits: habitMaps,
              completedIds: completed,
              pendingIds: pending,
              size: 20,
              strokeWidth: 3.5,
            ),
          ],
        ),
      ),
    );
  }

  String _fmtDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

// ─────────────────────────────────────────
// FULL CALENDAR MODAL
// ─────────────────────────────────────────

class _FullCalendarModal extends StatefulWidget {
  final DateTime selectedDate;
  final List<dynamic> habits;
  final Map<String, Map<String, dynamic>> activityByDate;
  final void Function(DateTime) onSelectDate;

  const _FullCalendarModal({
    required this.selectedDate,
    required this.habits,
    required this.activityByDate,
    required this.onSelectDate,
  });

  @override
  State<_FullCalendarModal> createState() => _FullCalendarModalState();
}

class _FullCalendarModalState extends State<_FullCalendarModal> {
  late PageController _pageCtrl;
  late DateTime _focusedMonth;
  late DateTime _selected;

  // Full activity fetch for all months
  Map<String, Map<String, dynamic>> _fullActivity = {};

  @override
  void initState() {
    super.initState();
    _selected = widget.selectedDate;
    _focusedMonth =
        DateTime(widget.selectedDate.year, widget.selectedDate.month);
    _fullActivity = Map.from(widget.activityByDate);

    // Start at a page that puts today's month at index 6 (6 months back as page 0)
    _pageCtrl = PageController(initialPage: 6);
    _fetchFullRange();
  }

  @override
  void dispose() {
    _pageCtrl.dispose();
    super.dispose();
  }

  Future<void> _fetchFullRange() async {
    try {
      final now = DateTime.now();
      final from = DateTime(now.year - 1, now.month);
      final to = DateTime(now.year + 1, now.month + 1, 0);
      final result = await ApiClient.getHabitActivity(
        dateFrom: _fmtDate(from),
        dateTo: _fmtDate(to),
      );
      final map = <String, Map<String, dynamic>>{};
      for (final a in result) {
        final d = a['date'] as String?;
        if (d != null) map[d] = a as Map<String, dynamic>;
      }
      if (mounted) setState(() => _fullActivity = map);
    } catch (_) {}
  }

  DateTime _monthAtPage(int page) {
    final now = DateTime.now();
    final baseMonth = DateTime(now.year, now.month);
    return DateTime(baseMonth.year, baseMonth.month + (page - 6));
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      minChildSize: 0.5,
      builder: (_, ctrl) => Column(
        children: [
          // Handle
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                  color: const Color(0xFFD1D5DB),
                  borderRadius: BorderRadius.circular(2)),
            ),
          ),

          // Month title + nav
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.chevron_left),
                  onPressed: () => _pageCtrl.previousPage(
                      duration: const Duration(milliseconds: 300),
                      curve: Curves.easeOut),
                ),
                Expanded(
                  child: Center(
                    child: Text(
                      _monthLabel(_focusedMonth),
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.chevron_right),
                  onPressed: () => _pageCtrl.nextPage(
                      duration: const Duration(milliseconds: 300),
                      curve: Curves.easeOut),
                ),
              ],
            ),
          ),

          // Day-of-week headers
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: const ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
                  .map((d) => SizedBox(
                        width: 40,
                        child: Center(
                          child: Text(d,
                              style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                  color: Color(0xFF9CA3AF))),
                        ),
                      ))
                  .toList(),
            ),
          ),
          const SizedBox(height: 4),

          // Page view of months
          Expanded(
            child: PageView.builder(
              controller: _pageCtrl,
              onPageChanged: (p) =>
                  setState(() => _focusedMonth = _monthAtPage(p)),
              itemBuilder: (_, page) {
                final month = _monthAtPage(page);
                return _MonthGrid(
                  month: month,
                  selectedDate: _selected,
                  habits: widget.habits,
                  activityByDate: _fullActivity,
                  onSelectDate: (d) {
                    setState(() => _selected = d);
                    widget.onSelectDate(d);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String _monthLabel(DateTime d) {
    const months = [
      '', 'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return '${months[d.month]} ${d.year}';
  }

  String _fmtDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

class _MonthGrid extends StatelessWidget {
  final DateTime month;
  final DateTime selectedDate;
  final List<dynamic> habits;
  final Map<String, Map<String, dynamic>> activityByDate;
  final void Function(DateTime) onSelectDate;

  const _MonthGrid({
    required this.month,
    required this.selectedDate,
    required this.habits,
    required this.activityByDate,
    required this.onSelectDate,
  });

  @override
  Widget build(BuildContext context) {
    // First day of month, aligned to Monday
    final firstOfMonth = DateTime(month.year, month.month, 1);
    final gridStart =
        firstOfMonth.subtract(Duration(days: firstOfMonth.weekday - 1));

    // Number of rows needed
    final lastOfMonth = DateTime(month.year, month.month + 1, 0);
    final totalDays =
        lastOfMonth.day + (firstOfMonth.weekday - 1) +
            (7 - lastOfMonth.weekday) % 7;
    final rows = totalDays ~/ 7;

    final today = DateTime.now();
    final todayStripped = DateTime(today.year, today.month, today.day);
    final habitMaps =
        habits.whereType<Map<String, dynamic>>().toList();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Column(
        children: List.generate(rows, (row) {
          return Expanded(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: List.generate(7, (col) {
                final d = gridStart.add(Duration(days: row * 7 + col));
                final isCurrentMonth = d.month == month.month;
                final isToday = d == todayStripped;
                final isSelected = d == selectedDate;
                final ds = _fmtDate(d);
                final activity = activityByDate[ds];
                final completed = (activity?['completed_habit_ids'] as List?)
                        ?.cast<int>() ??
                    [];
                final pending = (activity?['pending_habit_ids'] as List?)
                        ?.cast<int>() ??
                    [];

                return GestureDetector(
                  onTap: () => onSelectDate(d),
                  child: SizedBox(
                    width: 40,
                    height: double.infinity,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Date number
                        Container(
                          width: 28, height: 28,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: isSelected
                                ? Theme.of(context).colorScheme.primary
                                : isToday
                                    ? Theme.of(context)
                                        .colorScheme
                                        .primary
                                        .withValues(alpha: 0.12)
                                    : Colors.transparent,
                          ),
                          child: Center(
                            child: Text(
                              d.day.toString(),
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: isToday || isSelected
                                    ? FontWeight.w700
                                    : FontWeight.w400,
                                color: isSelected
                                    ? Colors.white
                                    : isCurrentMonth
                                        ? const Color(0xFF111827)
                                        : const Color(0xFFD1D5DB),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 3),
                        // Habit ring
                        if (isCurrentMonth &&
                            (completed.isNotEmpty || pending.isNotEmpty))
                          HabitActivityRing(
                            habits: habitMaps,
                            completedIds: completed,
                            pendingIds: pending,
                            size: 18,
                            strokeWidth: 3,
                          )
                        else
                          const SizedBox(height: 18),
                      ],
                    ),
                  ),
                );
              }),
            ),
          );
        }),
      ),
    );
  }

  String _fmtDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

// ─────────────────────────────────────────
// DASHBOARD CONTENT
// ─────────────────────────────────────────

class _DashboardContent extends StatelessWidget {
  final _DashboardData data;
  final DateTime selectedDate;
  const _DashboardContent(
      {required this.data, required this.selectedDate});

  @override
  Widget build(BuildContext context) {
    final s = data.summary;
    final caloriesIn =
        (s['calories_in'] as num?)?.toDouble() ?? 0;
    final caloriesOut =
        (s['calories_out'] as num?)?.toDouble() ?? 0;
    final net = caloriesIn - caloriesOut;

    final totalProtein = data.meals.fold<double>(
        0, (acc, m) => acc + ((m['protein'] as num?)?.toDouble() ?? 0));
    final totalCarbs = data.meals.fold<double>(
        0, (acc, m) => acc + ((m['carbs'] as num?)?.toDouble() ?? 0));
    final totalFat = data.meals.fold<double>(
        0, (acc, m) => acc + ((m['fat'] as num?)?.toDouble() ?? 0));

    final isToday = selectedDate == DateTime(DateTime.now().year,
        DateTime.now().month, DateTime.now().day);

    return Column(
      children: [
        // ── Calorie summary card ───────────────────
        const SectionHeader(title: "DAILY SUMMARY"),
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

        // ── Meals ─────────────────────────────────
        SectionHeader(
          title: 'MEALS',
          trailing: Text('${data.meals.length} logged',
              style: const TextStyle(
                  fontSize: 12, color: Color(0xFF9CA3AF))),
        ),
        if (data.meals.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                    isToday
                        ? 'No meals logged today.'
                        : 'No meals on this day.',
                    style: const TextStyle(color: Color(0xFF9CA3AF))),
              ),
            ),
          )
        else
          ...data.meals.map((m) => _MealTile(meal: m)),

        // ── Exercises ─────────────────────────────
        SectionHeader(
          title: 'EXERCISES',
          trailing: Text('${data.exercises.length} sessions',
              style: const TextStyle(
                  fontSize: 12, color: Color(0xFF9CA3AF))),
        ),
        if (data.exercises.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                    isToday
                        ? 'No exercises logged today.'
                        : 'No exercises on this day.',
                    style: const TextStyle(color: Color(0xFF9CA3AF))),
              ),
            ),
          )
        else
          ...data.exercises.map((e) => _ExerciseTile(exercise: e)),

        const SizedBox(height: 32),
      ],
    );
  }
}

// ─────────────────────────────────────────
// STAT / TILE WIDGETS
// ─────────────────────────────────────────

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
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: color)),
        Text(unit,
            style: const TextStyle(
                fontSize: 11, color: Color(0xFF9CA3AF))),
        Text(label,
            style: const TextStyle(
                fontSize: 12, color: Color(0xFF6B7280))),
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
        final gram =
            (it['gram_weight'] as num?)?.toStringAsFixed(0) ?? '';
        return name.isNotEmpty
            ? (gram.isNotEmpty ? '$name (${gram}g)' : name)
            : 'Food #${it['food_id']}';
      }).toList();
      itemSummary = names.join(', ');
    } else {
      itemSummary = 'No food items';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(
              horizontal: 16, vertical: 12),
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
                      style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                        '${items.length} item${items.length == 1 ? '' : 's'}',
                        style: const TextStyle(
                            fontSize: 11,
                            color: Color(0xFF9CA3AF))),
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
    final cal =
        (exercise['calories_burned'] as num?)?.toDouble() ?? 0;
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
    if (intensity != null &&
        intensity.isNotEmpty &&
        intensity != 'moderate') {
      details.add(intensity);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(
              horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(iconData,
                  size: 18, color: const Color(0xFF9CA3AF)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name,
                        style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500)),
                    if (details.isNotEmpty)
                      Text(
                        details.join(' · '),
                        style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFF9CA3AF)),
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
