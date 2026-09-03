import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api_client.dart';
import '../auth_state.dart';
import '../theme.dart';
import '../main.dart' show TabActivatedNotifier;

// ─────────────────────────────────────────
// PROFILE SCREEN
// ─────────────────────────────────────────

class ProfileScreen extends StatefulWidget {
  final AuthState authState;
  final TabActivatedNotifier? tabNotifier;
  const ProfileScreen({super.key, required this.authState, this.tabNotifier});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late Future<_ProfileData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
    ApiClient.dataChangeNotifier.addListener(_onDataChanged);
    widget.tabNotifier?.addListener(_onTabActivated);
  }

  @override
  void dispose() {
    ApiClient.dataChangeNotifier.removeListener(_onDataChanged);
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

  Future<_ProfileData> _load() async {
    final results = await Future.wait([
      ApiClient.me(),
      ApiClient.getWeightLogs(),
      ApiClient.getAllSummaries(),
    ]);
    return _ProfileData(
      user: results[0] as Map<String, dynamic>,
      weightLogs: results[1] as List<dynamic>,
      summaries: results[2] as List<dynamic>,
    );
  }

  Future<void> _handleRefresh() async {
    _reload();
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          TextButton(
            onPressed: () async {
              final confirm = await showDialog<bool>(
                context: context,
                builder: (_) => AlertDialog(
                  title: const Text('Sign out?'),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Cancel')),
                    TextButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Sign out',
                            style:
                                TextStyle(color: Color(0xFFEF4444)))),
                  ],
                ),
              );
              if (confirm == true) {
                await widget.authState.logout();
              }
            },
            child: const Text('Sign out',
                style: TextStyle(color: Color(0xFFEF4444))),
          ),
        ],
      ),
      body: FutureBuilder<_ProfileData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snap.hasError) {
            return ErrorView(
                message: snap.error.toString(),
                onRetry: _reload);
          }
          final d = snap.data!;
          return RefreshIndicator(
            onRefresh: _handleRefresh,
            child: _ProfileContent(
              data: d,
              onReload: _reload,
            ),
          );
        },
      ),
    );
  }
}

class _ProfileData {
  final Map<String, dynamic> user;
  final List<dynamic> weightLogs;
  final List<dynamic> summaries;
  const _ProfileData(
      {required this.user,
      required this.weightLogs,
      required this.summaries});
}

class _ProfileContent extends StatefulWidget {
  final _ProfileData data;
  final VoidCallback onReload;
  const _ProfileContent({required this.data, required this.onReload});

  @override
  State<_ProfileContent> createState() => _ProfileContentState();
}

class _ProfileContentState extends State<_ProfileContent> {
  bool _hoveringMeasurements = false;

  void _showEditMeasurements(
      BuildContext context, double currentWeight, double currentHeight) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) => _EditMeasurementsSheet(
        initialWeight: currentWeight,
        initialHeight: currentHeight,
        onSaved: widget.onReload,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.data.user;
    final weightLogs = widget.data.weightLogs.cast<Map<String, dynamic>>();
    final summaries = widget.data.summaries.cast<Map<String, dynamic>>();

    final currentWeight = (user['weight'] as num?)?.toDouble() ??
        (weightLogs.isNotEmpty ? (weightLogs.last['weight'] as num).toDouble() : 70.0);
    final currentHeight = (user['height'] as num?)?.toDouble() ?? 175.0;

    final avgCaloriesIn = summaries.isNotEmpty
        ? summaries.fold<double>(
                0,
                (acc, s) =>
                    acc +
                    ((s['calories_in'] as num?)?.toDouble() ?? 0)) /
            summaries.length
        : 0.0;

    final avgCaloriesOut = summaries.isNotEmpty
        ? summaries.fold<double>(
                0,
                (acc, s) =>
                    acc +
                    ((s['calories_out'] as num?)?.toDouble() ?? 0)) /
            summaries.length
        : 0.0;

    // Weight Stats
    final sortedLogs = List<Map<String, dynamic>>.from(weightLogs)
      ..sort((a, b) => (b['date'] as String).compareTo(a['date'] as String));

    double? minW;
    double? maxW;
    if (sortedLogs.isNotEmpty) {
      minW = sortedLogs
          .map((l) => (l['weight'] as num).toDouble())
          .reduce((a, b) => a < b ? a : b);
      maxW = sortedLogs
          .map((l) => (l['weight'] as num).toDouble())
          .reduce((a, b) => a > b ? a : b);
    }

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        // ── Avatar / name header ──────────────
        Container(
          color: Colors.white,
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              CircleAvatar(
                radius: 30,
                backgroundColor:
                    Theme.of(context).colorScheme.primary.withValues(alpha: 0.15),
                child: Text(
                  (user['username'] as String? ?? 'U')
                      .substring(0, 1)
                      .toUpperCase(),
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(user['username'] as String? ?? '',
                      style: const TextStyle(
                          fontSize: 18, fontWeight: FontWeight.w700)),
                  Text('Age ${user['age'] ?? '—'} · Member',
                      style: const TextStyle(
                          fontSize: 13, color: Color(0xFF9CA3AF))),
                ],
              ),
            ],
          ),
        ),
        const Divider(height: 1),

        // ── Physical stats & Measurements Card ──────────────────
        SectionHeader(
          title: 'CURRENT MEASUREMENTS',
          trailing: TextButton.icon(
            onPressed: () => _showEditMeasurements(context, currentWeight, currentHeight),
            icon: const Icon(Icons.edit_outlined, size: 14),
            label: const Text('Edit', style: TextStyle(fontSize: 13)),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: MouseRegion(
            onEnter: (_) => setState(() => _hoveringMeasurements = true),
            onExit: (_) => setState(() => _hoveringMeasurements = false),
            child: Card(
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _showEditMeasurements(context, currentWeight, currentHeight),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          const Text('Body Stats',
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                          const Spacer(),
                          if (_hoveringMeasurements)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'Click to Edit',
                                style: TextStyle(
                                    fontSize: 11,
                                    color: Theme.of(context).colorScheme.primary,
                                    fontWeight: FontWeight.w600),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      InfoTile(
                        label: 'Weight',
                        value: '${currentWeight.toStringAsFixed(1)} kg',
                      ),
                      const Divider(height: 16),
                      InfoTile(
                        label: 'Height',
                        value: '${currentHeight.toStringAsFixed(0)} cm',
                      ),
                      const Divider(height: 16),
                      InfoTile(
                        label: 'Body Mass Index (BMI)',
                        value: _bmi(currentWeight, currentHeight),
                        valueColor: const Color(0xFF2563EB),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),

        // ── Weight Tracking & History ──────────
        SectionHeader(
          title: 'WEIGHT HISTORY & PROGRESS',
          trailing: TextButton.icon(
            onPressed: () => _showLogWeightDialog(context),
            icon: const Icon(Icons.add, size: 14),
            label: const Text('Log Entry', style: TextStyle(fontSize: 13)),
          ),
        ),
        if (sortedLogs.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _StatCol(
                        label: 'Latest',
                        value: '${currentWeight.toStringAsFixed(1)} kg',
                        color: Theme.of(context).colorScheme.primary),
                    if (minW != null)
                      _StatCol(
                          label: 'Lowest',
                          value: '${minW.toStringAsFixed(1)} kg',
                          color: const Color(0xFF10B981)),
                    if (maxW != null)
                      _StatCol(
                          label: 'Highest',
                          value: '${maxW.toStringAsFixed(1)} kg',
                          color: const Color(0xFFEF4444)),
                    _StatCol(
                        label: 'Entries',
                        value: sortedLogs.length.toString(),
                        color: const Color(0xFF6B7280)),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: sortedLogs.length.clamp(0, 5),
                separatorBuilder: (ctx, idx) => const Divider(height: 1, indent: 16),
                itemBuilder: (_, i) {
                  final log = sortedLogs[i];
                  final w = (log['weight'] as num).toDouble();
                  final isFirst = i == 0;
                  double? delta;
                  if (i < sortedLogs.length - 1) {
                    delta = w - (sortedLogs[i + 1]['weight'] as num).toDouble();
                  }
                  return ListTile(
                    dense: true,
                    title: Text('${w.toStringAsFixed(1)} kg',
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    subtitle: Text(log['date'] as String, style: const TextStyle(fontSize: 12)),
                    trailing: delta == null
                        ? null
                        : Text(
                            '${delta > 0 ? '+' : ''}${delta.toStringAsFixed(1)} kg',
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                color: delta > 0 ? const Color(0xFFEF4444) : const Color(0xFF10B981)),
                          ),
                    leading: isFirst
                        ? const Icon(Icons.star, size: 16, color: Color(0xFFF59E0B))
                        : null,
                  );
                },
              ),
            ),
          ),
        ] else
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No weight logs yet. Update your measurements above or tap "+ Log Entry".',
                    style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 13)),
              ),
            ),
          ),

        // ── Averages ──────────────────────
        const SectionHeader(title: 'ALL-TIME AVERAGES'),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  InfoTile(
                    label: 'Avg calories in',
                    value: '${avgCaloriesIn.toStringAsFixed(0)} kcal',
                    valueColor: const Color(0xFF2563EB),
                  ),
                  const Divider(height: 16),
                  InfoTile(
                    label: 'Avg calories burned',
                    value: '${avgCaloriesOut.toStringAsFixed(0)} kcal',
                    valueColor: const Color(0xFFEF4444),
                  ),
                  const Divider(height: 16),
                  InfoTile(
                    label: 'Days tracked',
                    value: summaries.length.toString(),
                  ),
                ],
              ),
            ),
          ),
        ),

        // ── Recent summary history ──────────
        if (summaries.isNotEmpty) ...[
          const SectionHeader(title: 'RECENT DAILY SUMMARIES'),
          ...summaries.reversed.take(7).map((s) => Padding(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 3),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    child: Row(
                      children: [
                        Expanded(
                            child: Text(s['date'] as String? ?? '',
                                style: const TextStyle(fontSize: 13))),
                        Text(
                            '${(s['calories_in'] as num?)?.toStringAsFixed(0) ?? 0} in',
                            style: const TextStyle(
                                fontSize: 12,
                                color: Color(0xFF2563EB))),
                        const Text(' · ',
                            style:
                                TextStyle(color: Color(0xFFD1D5DB))),
                        Text(
                            '${(s['calories_out'] as num?)?.toStringAsFixed(0) ?? 0} burned',
                            style: const TextStyle(
                                fontSize: 12,
                                color: Color(0xFFEF4444))),
                      ],
                    ),
                  ),
                ),
              )),
        ],
        const SizedBox(height: 32),
      ],
    );
  }

  void _showLogWeightDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) => _QuickLogWeightSheet(onSaved: widget.onReload),
    );
  }

  String _bmi(double weight, double heightCm) {
    if (heightCm <= 0 || weight <= 0) return '—';
    final h = heightCm / 100;
    final bmi = weight / (h * h);
    return bmi.toStringAsFixed(1);
  }
}

class _StatCol extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatCol(
      {required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: color)),
        const SizedBox(height: 2),
        Text(label,
            style: const TextStyle(
                fontSize: 11, color: Color(0xFF9CA3AF))),
      ],
    );
  }
}

// ─────────────────────────────────────────
// EDIT MEASUREMENTS SHEET
// ─────────────────────────────────────────

class _EditMeasurementsSheet extends StatefulWidget {
  final double initialWeight;
  final double initialHeight;
  final VoidCallback onSaved;

  const _EditMeasurementsSheet({
    required this.initialWeight,
    required this.initialHeight,
    required this.onSaved,
  });

  @override
  State<_EditMeasurementsSheet> createState() => _EditMeasurementsSheetState();
}

class _EditMeasurementsSheetState extends State<_EditMeasurementsSheet> {
  late final TextEditingController _weightCtrl;
  late final TextEditingController _heightCtrl;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _weightCtrl = TextEditingController(text: widget.initialWeight.toStringAsFixed(1));
    _heightCtrl = TextEditingController(text: widget.initialHeight.toStringAsFixed(0));
  }

  @override
  void dispose() {
    _weightCtrl.dispose();
    _heightCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final w = double.tryParse(_weightCtrl.text);
    final h = double.tryParse(_heightCtrl.text);

    if (w == null || w <= 0 || h == null || h <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please enter valid measurements.')));
      return;
    }

    setState(() => _saving = true);
    try {
      await ApiClient.updateMeasurements(weight: w, height: h);
      widget.onSaved();
      if (mounted) Navigator.pop(context);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(e.message), backgroundColor: Colors.red.shade700));
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
            const Text('Edit Body Measurements',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _weightCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Weight (kg)',
                      suffixText: 'kg',
                    ),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _heightCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Height (cm)',
                      suffixText: 'cm',
                    ),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
                  ),
                ),
              ],
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
                    : const Text('Update Measurements'),
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
// QUICK LOG WEIGHT SHEET
// ─────────────────────────────────────────

class _QuickLogWeightSheet extends StatefulWidget {
  final VoidCallback onSaved;
  const _QuickLogWeightSheet({required this.onSaved});

  @override
  State<_QuickLogWeightSheet> createState() => _QuickLogWeightSheetState();
}

class _QuickLogWeightSheetState extends State<_QuickLogWeightSheet> {
  final _ctrl = TextEditingController();
  DateTime _date = DateTime.now();
  bool _saving = false;

  @override
  void dispose() {
    _ctrl.dispose();
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

  Future<void> _save() async {
    final w = double.tryParse(_ctrl.text);
    if (w == null || w <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enter a valid weight.')));
      return;
    }
    setState(() => _saving = true);
    try {
      await ApiClient.logWeight(_dateStr, w);
      widget.onSaved();
      if (mounted) Navigator.pop(context);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(e.message), backgroundColor: Colors.red.shade700));
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
            const Text('Log Weight Entry',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),
            TextField(
              controller: _ctrl,
              autofocus: true,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
              decoration: const InputDecoration(
                labelText: 'Weight (kg)',
                suffixText: 'kg',
              ),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _pickDate,
              icon: const Icon(Icons.calendar_today, size: 16),
              label: Text('Date: $_dateStr'),
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
                    : const Text('Save Entry'),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
