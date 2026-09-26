import 'package:flutter/material.dart';
import '../services/api_client.dart';

// ─────────────────────────────────────────
// RECOMMENDATION SHEET
//
// Shared across Today, Meals, and Exercise
// screens.  Shown as a modal bottom sheet.
// ─────────────────────────────────────────

/// Show the recommendation bottom sheet.
///
/// [filterType] constrains results to 'meal' or 'exercise' if non-null.
/// When null, the server's best recommendation is shown regardless of type.
Future<void> showRecommendationSheet(
  BuildContext context, {
  String? filterType, // 'meal' | 'exercise' | null
}) async {
  await showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => _RecommendationSheet(filterType: filterType),
  );
}

class _RecommendationSheet extends StatefulWidget {
  final String? filterType;
  const _RecommendationSheet({this.filterType});

  @override
  State<_RecommendationSheet> createState() => _RecommendationSheetState();
}

class _RecommendationSheetState extends State<_RecommendationSheet> {
  late String? _selectedType;
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _selectedType = widget.filterType;
    _future = ApiClient.getTodayRecommendation(_selectedType);
  }

  void _switchType(String? type) {
    if (_selectedType == type) return;
    setState(() {
      _selectedType = type;
      _future = ApiClient.getTodayRecommendation(_selectedType);
    });
  }

  void _reload() {
    setState(() {
      _future = ApiClient.getTodayRecommendation(_selectedType);
    });
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.60,
      maxChildSize: 0.92,
      minChildSize: 0.35,
      builder: (_, ctrl) => Column(
        children: [
          // Handle
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFD1D5DB),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: Theme.of(context)
                        .colorScheme
                        .primary
                        .withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    Icons.auto_awesome_rounded,
                    size: 18,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Recommended for you',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w700)),
                      Text('Based on your goal and today\'s activity',
                          style: TextStyle(
                              fontSize: 12, color: Color(0xFF9CA3AF))),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // Category filter pills
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              children: [
                _TabPill(
                  label: 'For You',
                  icon: Icons.auto_awesome_rounded,
                  isSelected: _selectedType == null,
                  onTap: () => _switchType(null),
                ),
                const SizedBox(width: 8),
                _TabPill(
                  label: 'Exercise',
                  icon: Icons.fitness_center_rounded,
                  isSelected: _selectedType == 'exercise',
                  onTap: () => _switchType('exercise'),
                ),
                const SizedBox(width: 8),
                _TabPill(
                  label: 'Meal',
                  icon: Icons.restaurant_rounded,
                  isSelected: _selectedType == 'meal',
                  onTap: () => _switchType('meal'),
                ),
              ],
            ),
          ),

          const Divider(height: 18),

          // Content
          Expanded(
            child: FutureBuilder<Map<String, dynamic>>(
              future: _future,
              builder: (ctx, snap) {
                if (snap.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snap.hasError) {
                  return _ErrorContent(
                    message: snap.error.toString(),
                    onRetry: _reload,
                  );
                }
                return _RecommendationContent(
                  data: snap.data!,
                  filterType: _selectedType,
                  scrollController: ctrl,
                  onRefresh: _reload,
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _TabPill extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;

  const _TabPill({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final primary = theme.colorScheme.primary;

    return Expanded(
      child: Material(
        color: isSelected
            ? primary.withValues(alpha: 0.12)
            : const Color(0xFFF3F4F6),
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 8),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: isSelected
                    ? primary.withValues(alpha: 0.5)
                    : Colors.transparent,
              ),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icon,
                  size: 14,
                  color: isSelected ? primary : const Color(0xFF6B7280),
                ),
                const SizedBox(width: 5),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                    color: isSelected ? primary : const Color(0xFF4B5563),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ErrorContent extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorContent({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline,
                size: 36, color: Color(0xFF9CA3AF)),
            const SizedBox(height: 12),
            Text(message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
            const SizedBox(height: 16),
            TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

class _RecommendationContent extends StatelessWidget {
  final Map<String, dynamic> data;
  final String? filterType;
  final ScrollController scrollController;
  final VoidCallback onRefresh;

  const _RecommendationContent({
    required this.data,
    required this.filterType,
    required this.scrollController,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final hasRec = data['has_recommendation'] as bool? ?? false;
    final type = data['type'] as String?;
    final title = data['title'] as String? ?? '';
    final reason = data['reason'] as String? ?? '';
    final items = (data['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    final typeMatches = filterType == null || type == filterType;

    return ListView(
      controller: scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      children: [
        if (!hasRec || !typeMatches) ...[
          _NoRecommendation(
            filterType: filterType,
            reason: typeMatches
                ? reason
                : filterType == 'meal'
                    ? 'No meal recommendation right now. $reason'
                    : 'No exercise recommendation right now. $reason',
          ),
        ] else ...[
          // Type badge
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: type == 'meal'
                      ? const Color(0xFF2563EB).withValues(alpha: 0.10)
                      : const Color(0xFF10B981).withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      type == 'meal'
                          ? Icons.restaurant_rounded
                          : Icons.fitness_center_rounded,
                      size: 12,
                      color: type == 'meal'
                          ? const Color(0xFF2563EB)
                          : const Color(0xFF10B981),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      type == 'meal' ? 'Meal' : 'Exercise',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: type == 'meal'
                            ? const Color(0xFF2563EB)
                            : const Color(0xFF10B981),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 10),

          // Title
          Text(title,
              style: const TextStyle(
                  fontSize: 17, fontWeight: FontWeight.w700)),

          const SizedBox(height: 6),

          // Reason
          Text(reason,
              style:
                  const TextStyle(fontSize: 13, color: Color(0xFF6B7280))),

          const SizedBox(height: 16),

          // Items
          if (items.isNotEmpty) ...[
            ...items.map((item) => _ItemCard(item: item, type: type)),
          ],

          const SizedBox(height: 16),

          // Action button
          if (items.isNotEmpty)
            FilledButton.icon(
              icon: Icon(type == 'meal'
                  ? Icons.add_circle_outline
                  : Icons.play_arrow_rounded),
              label: Text(type == 'meal'
                  ? 'Add to today\'s meals'
                  : 'Log this exercise'),
              onPressed: () => _handleAdd(context, type, items),
            ),

          const SizedBox(height: 24),
        ],
      ],
    );
  }

  Future<void> _handleAdd(
    BuildContext context,
    String? type,
    List<Map<String, dynamic>> items,
  ) async {
    if (type == 'exercise' && items.isNotEmpty) {
      final item = items.first;
      final name = item['name'] as String? ?? 'Exercise';
      final category = item['category'] as String? ?? 'strength';
      final sets = item['sets'] as int?;
      final reps = item['reps'] as int?;
      final duration = item['duration_minutes'] as int?;

      try {
        final today = DateTime.now();
        final dateStr =
            '${today.year}-${today.month.toString().padLeft(2, '0')}-${today.day.toString().padLeft(2, '0')}';
        await ApiClient.createExercise({
          'date': dateStr,
          'name': name,
          'category': category,
          'sets': ?sets,
          'reps': ?reps,
          'duration_minutes': ?duration,
          'intensity': 'moderate',
        });
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('$name logged!')),
          );
          onRefresh();
          Navigator.pop(context);
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')),
          );
        }
      }
    } else if (type == 'meal') {
      if (context.mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
                'Use the + button to add these foods to your meal log.'),
          ),
        );
      }
    }
  }
}

class _NoRecommendation extends StatelessWidget {
  final String? filterType;
  final String reason;
  const _NoRecommendation({this.filterType, required this.reason});

  @override
  Widget build(BuildContext context) {
    final lower = reason.toLowerCase();
    final isDone = lower.contains('great job') ||
        lower.contains('all set') ||
        lower.contains('targets') ||
        lower.contains('on track') ||
        lower.contains('great work');

    final title = isDone
        ? (filterType == 'exercise'
            ? 'Workout Complete!'
            : filterType == 'meal'
                ? 'Nutrition on Track!'
                : "You're all set!")
        : (filterType == 'exercise'
            ? 'No Exercise Recommendation'
            : filterType == 'meal'
                ? 'No Meal Recommendation'
                : 'No Recommendation');

    final icon = isDone
        ? Icons.check_circle_rounded
        : (filterType == 'exercise'
            ? Icons.fitness_center_outlined
            : filterType == 'meal'
                ? Icons.restaurant_outlined
                : Icons.info_outline_rounded);

    final color = isDone ? const Color(0xFF10B981) : const Color(0xFF6B7280);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.10),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 32, color: color),
            ),
            const SizedBox(height: 16),
            Text(title,
                textAlign: TextAlign.center,
                style:
                    const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(
              reason,
              textAlign: TextAlign.center,
              style: const TextStyle(
                  fontSize: 13, color: Color(0xFF6B7280), height: 1.4),
            ),
          ],
        ),
      ),
    );
  }
}

class _ItemCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final String? type;
  const _ItemCard({required this.item, required this.type});

  @override
  Widget build(BuildContext context) {
    final name = item['name'] as String? ?? '';
    final cal = (item['calories'] as num?)?.toDouble();
    final protein = (item['protein'] as num?)?.toDouble();
    final carbs = (item['carbs'] as num?)?.toDouble();
    final fat = (item['fat'] as num?)?.toDouble();
    final sets = item['sets'] as int?;
    final reps = item['reps'] as int?;
    final duration = item['duration_minutes'] as int?;
    final desc = item['description'] as String?;
    final category = item['category'] as String?;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                type == 'meal'
                    ? Icons.restaurant_outlined
                    : category == 'cardio'
                        ? Icons.directions_run_outlined
                        : category == 'flexibility'
                            ? Icons.self_improvement_outlined
                            : Icons.fitness_center_outlined,
                size: 16,
                color: const Color(0xFF9CA3AF),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(name,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          if (desc != null && desc.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(desc,
                style:
                    const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
          ],
          if (type == 'meal' &&
              (cal != null || protein != null)) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                if (cal != null)
                  _Macro(
                      label: 'kcal',
                      value: cal.toStringAsFixed(0),
                      color: const Color(0xFFEF4444)),
                if (protein != null)
                  _Macro(
                      label: 'protein',
                      value: '${protein.toStringAsFixed(1)}g',
                      color: const Color(0xFF2563EB)),
                if (carbs != null)
                  _Macro(
                      label: 'carbs',
                      value: '${carbs.toStringAsFixed(1)}g',
                      color: const Color(0xFFF59E0B)),
                if (fat != null)
                  _Macro(
                      label: 'fat',
                      value: '${fat.toStringAsFixed(1)}g',
                      color: const Color(0xFF10B981)),
              ],
            ),
          ],
          if (type == 'exercise') ...[
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              children: [
                if (sets != null && reps != null)
                  _Badge(label: '$sets × $reps reps'),
                if (duration != null)
                  _Badge(label: '$duration min'),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _Macro extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _Macro({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value,
              style: TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600, color: color)),
          Text(label,
              style:
                  const TextStyle(fontSize: 10, color: Color(0xFF9CA3AF))),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  const _Badge({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: Theme.of(context).colorScheme.primary)),
    );
  }
}

// ─────────────────────────────────────────
// FLOATING RECOMMENDATION BUTTON
// ─────────────────────────────────────────

/// A floating action button styled for the recommendation feature.
/// Placed at the bottom-right of a screen.
class RecommendationFAB extends StatelessWidget {
  final String? filterType;

  const RecommendationFAB({super.key, this.filterType});

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: "Don't know what to do? Get a recommendation.",
      child: FloatingActionButton(
        heroTag: 'rec_fab_${filterType ?? "all"}',
        onPressed: () => showRecommendationSheet(
          context,
          filterType: filterType,
        ),
        backgroundColor: Theme.of(context).colorScheme.primary,
        foregroundColor: Colors.white,
        mini: false,
        child: const Icon(Icons.auto_awesome_rounded, size: 24),
      ),
    );
  }
}
