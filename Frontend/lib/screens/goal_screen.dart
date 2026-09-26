import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';

// ─────────────────────────────────────────
// GOAL SCREEN
// Used from Profile tab and onboarding flow.
// ─────────────────────────────────────────

class GoalScreen extends StatefulWidget {
  /// When true, shows a "Get started →" button instead of Save and hides
  /// the back arrow (used during onboarding after registration).
  final bool isOnboarding;
  const GoalScreen({super.key, this.isOnboarding = false});

  @override
  State<GoalScreen> createState() => _GoalScreenState();
}

class _GoalScreenState extends State<GoalScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _error;

  // ── Goal fields ──────────────────────────────────────
  String? _goalType;
  final _targetWeightCtrl = TextEditingController();
  String? _activityLevel;
  int? _trainingDays;
  String? _experience;
  final List<String> _equipment = [];
  String? _dietaryPref;
  final _avoidCtrl = TextEditingController();

  static const _goalOptions = [
    ('lose_weight', 'Lose Weight', Icons.trending_down_rounded),
    ('gain_weight', 'Gain Weight', Icons.trending_up_rounded),
    ('build_muscle', 'Build Muscle', Icons.fitness_center_rounded),
    ('maintain_weight', 'Maintain Weight', Icons.balance_rounded),
    ('improve_fitness', 'Improve Fitness', Icons.directions_run_rounded),
    ('improve_endurance', 'Improve Endurance', Icons.timer_outlined),
    ('get_stronger', 'Get Stronger', Icons.bolt_rounded),
  ];

  static const _activityOptions = [
    ('sedentary', 'Sedentary', 'Little or no exercise'),
    ('lightly_active', 'Lightly Active', '1–3 days/week'),
    ('moderately_active', 'Moderately Active', '3–5 days/week'),
    ('very_active', 'Very Active', '6–7 days/week'),
    ('extremely_active', 'Extremely Active', 'Physical job + exercise'),
  ];

  static const _experienceOptions = [
    ('beginner', 'Beginner', '< 1 year'),
    ('intermediate', 'Intermediate', '1–3 years'),
    ('advanced', 'Advanced', '3+ years'),
  ];

  static const _equipmentOptions = [
    ('barbell', 'Barbell'),
    ('dumbbell', 'Dumbbells'),
    ('machines', 'Machines'),
    ('cables', 'Cables'),
    ('bodyweight', 'Bodyweight only'),
    ('bands', 'Resistance Bands'),
    ('kettlebell', 'Kettlebell'),
    ('none', 'No equipment'),
  ];

  static const _dietaryOptions = [
    ('omnivore', 'Omnivore'),
    ('vegetarian', 'Vegetarian'),
    ('vegan', 'Vegan'),
    ('pescatarian', 'Pescatarian'),
    ('other', 'Other'),
  ];

  @override
  void initState() {
    super.initState();
    _loadGoal();
  }

  @override
  void dispose() {
    _targetWeightCtrl.dispose();
    _avoidCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadGoal() async {
    try {
      final goal = await ApiClient.getGoal();
      if (mounted) {
        setState(() {
          _goalType = goal['goal_type'] as String?;
          final tw = goal['target_weight'];
          if (tw != null) _targetWeightCtrl.text = tw.toString();
          _activityLevel = goal['activity_level'] as String?;
          _trainingDays = goal['training_days_per_week'] as int?;
          _experience = goal['training_experience'] as String?;
          final eq = goal['available_equipment'] as String?;
          if (eq != null && eq.isNotEmpty) {
            _equipment
              ..clear()
              ..addAll(eq.split(',').map((e) => e.trim()));
          }
          _dietaryPref = goal['dietary_preference'] as String?;
          final avoid = goal['foods_to_avoid'] as String?;
          if (avoid != null) _avoidCtrl.text = avoid;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() { _loading = false; });
    }
  }

  Future<void> _save() async {
    setState(() { _saving = true; _error = null; });
    try {
      final twText = _targetWeightCtrl.text.trim();
      final tw = twText.isNotEmpty ? double.tryParse(twText) : null;
      final eqStr = _equipment.isNotEmpty ? _equipment.join(',') : null;
      final body = <String, dynamic>{
        'goal_type': _goalType,
        'target_weight': tw,
        'activity_level': _activityLevel,
        'training_days_per_week': _trainingDays,
        'training_experience': _experience,
        'available_equipment': eqStr,
        'dietary_preference': _dietaryPref,
        'foods_to_avoid': _avoidCtrl.text.trim().isEmpty
            ? null
            : _avoidCtrl.text.trim(),
      };
      await ApiClient.upsertGoal(body);
      if (mounted) {
        if (widget.isOnboarding) {
          Navigator.of(context).pop(true);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Goal saved!')),
          );
          Navigator.of(context).pop(true);
        }
      }
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _saving = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isOnboarding ? 'Set Up Your Goal' : 'Fitness Goal'),
        automaticallyImplyLeading: !widget.isOnboarding,
      ),
      body: _loading
          ? const LoadingView()
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
              children: [
                if (widget.isOnboarding) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Tell us about your goal so we can give you personalised recommendations. You can always update this later.',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 14),
                  ),
                  const SizedBox(height: 16),
                ],

                // ── Goal type ─────────────────────────
                _sectionHeader('What is your primary goal?'),
                _GoalGrid(
                  options: _goalOptions,
                  selected: _goalType,
                  onSelect: (v) => setState(() => _goalType = v),
                ),

                const SizedBox(height: 20),

                // ── Activity level ────────────────────
                _sectionHeader('Activity level'),
                ..._activityOptions.map((opt) => _OptionTile(
                      label: opt.$2,
                      subtitle: opt.$3,
                      selected: _activityLevel == opt.$1,
                      onTap: () => setState(() => _activityLevel = opt.$1),
                    )),

                const SizedBox(height: 20),

                // ── Training frequency ────────────────
                _sectionHeader('Training days per week'),
                _TrainingDaysPicker(
                  value: _trainingDays,
                  onChanged: (v) => setState(() => _trainingDays = v),
                ),

                const SizedBox(height: 20),

                // ── Experience ─────────────────────────
                _sectionHeader('Training experience'),
                ..._experienceOptions.map((opt) => _OptionTile(
                      label: opt.$2,
                      subtitle: opt.$3,
                      selected: _experience == opt.$1,
                      onTap: () => setState(() => _experience = opt.$1),
                    )),

                const SizedBox(height: 20),

                // ── Equipment ─────────────────────────
                _sectionHeader('Available equipment'),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: _equipmentOptions.map((opt) {
                    final selected = _equipment.contains(opt.$1);
                    return FilterChip(
                      label: Text(opt.$2),
                      selected: selected,
                      onSelected: (v) => setState(() {
                        if (v) {
                          _equipment.add(opt.$1);
                        } else {
                          _equipment.remove(opt.$1);
                        }
                      }),
                      selectedColor: Theme.of(context)
                          .colorScheme
                          .primary
                          .withValues(alpha: 0.15),
                      checkmarkColor: Theme.of(context).colorScheme.primary,
                    );
                  }).toList(),
                ),

                const SizedBox(height: 20),

                // ── Target weight ──────────────────────
                if (_goalType == 'lose_weight' ||
                    _goalType == 'gain_weight' ||
                    _goalType == 'maintain_weight') ...[
                  _sectionHeader('Target weight (kg) — optional'),
                  TextField(
                    controller: _targetWeightCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      hintText: 'e.g. 75',
                      suffixText: 'kg',
                    ),
                  ),
                  const SizedBox(height: 20),
                ],

                // ── Dietary preference ─────────────────
                _sectionHeader('Dietary preference'),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: _dietaryOptions.map((opt) {
                    final selected = _dietaryPref == opt.$1;
                    return ChoiceChip(
                      label: Text(opt.$2),
                      selected: selected,
                      onSelected: (v) =>
                          setState(() => _dietaryPref = v ? opt.$1 : null),
                      selectedColor: Theme.of(context)
                          .colorScheme
                          .primary
                          .withValues(alpha: 0.15),
                    );
                  }).toList(),
                ),

                const SizedBox(height: 20),

                // ── Foods to avoid ─────────────────────
                _sectionHeader('Foods to avoid — optional'),
                TextField(
                  controller: _avoidCtrl,
                  decoration: const InputDecoration(
                    hintText: 'e.g. gluten, dairy, nuts',
                  ),
                ),

                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Color(0xFFEF4444))),
                ],

                const SizedBox(height: 24),

                FilledButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(widget.isOnboarding ? 'Get started →' : 'Save goal'),
                ),

                if (widget.isOnboarding)
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: const Text('Skip for now'),
                  ),
              ],
            ),
    );
  }

  Widget _sectionHeader(String title) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(title,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Color(0xFF6B7280))),
      );
}

// ── Goal grid ──────────────────────────────────────────────

class _GoalGrid extends StatelessWidget {
  final List<(String, String, IconData)> options;
  final String? selected;
  final void Function(String) onSelect;

  const _GoalGrid(
      {required this.options,
      required this.selected,
      required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: 2.8,
      children: options.map((opt) {
        final isSelected = selected == opt.$1;
        return GestureDetector(
          onTap: () => onSelect(opt.$1),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: isSelected
                  ? Theme.of(context)
                      .colorScheme
                      .primary
                      .withValues(alpha: 0.10)
                  : Colors.white,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: isSelected
                    ? Theme.of(context).colorScheme.primary
                    : const Color(0xFFE5E7EB),
                width: isSelected ? 1.5 : 1,
              ),
            ),
            child: Row(
              children: [
                Icon(opt.$3,
                    size: 18,
                    color: isSelected
                        ? Theme.of(context).colorScheme.primary
                        : const Color(0xFF9CA3AF)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    opt.$2,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: isSelected
                          ? Theme.of(context).colorScheme.primary
                          : const Color(0xFF111827),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

// ── Option tile ────────────────────────────────────────────

class _OptionTile extends StatelessWidget {
  final String label;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;

  const _OptionTile({
    required this.label,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        margin: const EdgeInsets.only(bottom: 6),
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: selected
              ? Theme.of(context)
                  .colorScheme
                  .primary
                  .withValues(alpha: 0.08)
              : Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: selected
                ? Theme.of(context).colorScheme.primary
                : const Color(0xFFE5E7EB),
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                          color: selected
                              ? Theme.of(context).colorScheme.primary
                              : const Color(0xFF111827))),
                  Text(subtitle,
                      style: const TextStyle(
                          fontSize: 12, color: Color(0xFF9CA3AF))),
                ],
              ),
            ),
            if (selected)
              Icon(Icons.check_circle_rounded,
                  size: 18,
                  color: Theme.of(context).colorScheme.primary),
          ],
        ),
      ),
    );
  }
}

// ── Training days picker ────────────────────────────────────

class _TrainingDaysPicker extends StatelessWidget {
  final int? value;
  final void Function(int) onChanged;

  const _TrainingDaysPicker({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(7, (i) {
        final day = i + 1;
        final selected = value == day;
        return Expanded(
          child: GestureDetector(
            onTap: () => onChanged(day),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              margin: const EdgeInsets.symmetric(horizontal: 2),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: selected
                    ? Theme.of(context).colorScheme.primary
                    : Colors.white,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: selected
                      ? Theme.of(context).colorScheme.primary
                      : const Color(0xFFE5E7EB),
                ),
              ),
              child: Center(
                child: Text(
                  '$day',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: selected ? Colors.white : const Color(0xFF6B7280),
                  ),
                ),
              ),
            ),
          ),
        );
      }),
    );
  }
}
