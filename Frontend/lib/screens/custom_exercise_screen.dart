import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import '../services/api_client.dart';

class CustomExerciseScreen extends StatefulWidget {
  final ExerciseCatalogItem? existing;
  final String? initialName;
  final String? initialCategory;

  const CustomExerciseScreen({
    super.key,
    this.existing,
    this.initialName,
    this.initialCategory,
  });

  @override
  State<CustomExerciseScreen> createState() => _CustomExerciseScreenState();
}

class _CustomExerciseScreenState extends State<CustomExerciseScreen> {
  static const Map<String, String> _muscleLabels = {
    'chest': 'Chest',
    'back': 'Back',
    'shoulders': 'Shoulders',
    'biceps': 'Biceps',
    'triceps': 'Triceps',
    'forearms': 'Forearms',
    'quadriceps': 'Quads',
    'hamstrings': 'Hamstrings',
    'glutes': 'Glutes',
    'calves': 'Calves',
    'abs_core': 'Core',
  };

  static const Map<String, String> _equipmentLabels = {
    'bodyweight': 'Bodyweight',
    'barbell': 'Barbell',
    'dumbbell': 'Dumbbell',
    'machines': 'Machines',
    'cables': 'Cables',
    'bands': 'Bands',
    'kettlebell': 'Kettlebell',
  };

  static const Map<String, String> _levelLabels = {
    'beginner': 'Beginner',
    'intermediate': 'Intermediate',
    'advanced': 'Advanced',
  };

  final _nameCtrl = TextEditingController();
  final _metCtrl = TextEditingController();
  final _descCtrl = TextEditingController();

  String _category = 'strength';
  String _equipment = 'bodyweight';
  String _level = 'intermediate';
  final Set<String> _primaryMuscles = {};
  final Set<String> _secondaryMuscles = {};
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final ex = widget.existing;
    if (ex != null) {
      _nameCtrl.text = ex.name;
      if (['strength', 'cardio', 'flexibility'].contains(ex.category)) {
        _category = ex.category;
      }
      final firstEquip = ex.equipment.split('|').first;
      if (_equipmentLabels.containsKey(firstEquip)) {
        _equipment = firstEquip;
      }
      if (_levelLabels.containsKey(ex.level)) {
        _level = ex.level;
      }
      _metCtrl.text = ex.defaultMet.toString();
      for (final m in ex.muscles) {
        if (m.role == 'primary') {
          _primaryMuscles.add(m.muscleGroup);
        } else {
          _secondaryMuscles.add(m.muscleGroup);
        }
      }
    } else {
      if (widget.initialName != null) {
        _nameCtrl.text = widget.initialName!;
      }
      if (widget.initialCategory != null &&
          ['strength', 'cardio', 'flexibility']
              .contains(widget.initialCategory)) {
        _category = widget.initialCategory!;
      }
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _metCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  void _togglePrimary(String group) {
    setState(() {
      if (_primaryMuscles.contains(group)) {
        _primaryMuscles.remove(group);
      } else {
        if (_primaryMuscles.length + _secondaryMuscles.length >= 6 &&
            !_secondaryMuscles.contains(group)) {
          return;
        }
        _secondaryMuscles.remove(group);
        _primaryMuscles.add(group);
      }
    });
  }

  void _toggleSecondary(String group) {
    setState(() {
      if (_secondaryMuscles.contains(group)) {
        _secondaryMuscles.remove(group);
      } else {
        if (_primaryMuscles.length + _secondaryMuscles.length >= 6 &&
            !_primaryMuscles.contains(group)) {
          return;
        }
        _primaryMuscles.remove(group);
        _secondaryMuscles.add(group);
      }
    });
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Exercise name is required.')),
      );
      return;
    }
    if (_category == 'strength' && _primaryMuscles.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pick at least one main muscle group.')),
      );
      return;
    }

    final metVal = double.tryParse(_metCtrl.text.trim());
    final descText = _descCtrl.text.trim();
    final muscles = _category == 'strength'
        ? <ExerciseMuscle>[
            ..._primaryMuscles.map(
                (g) => ExerciseMuscle(muscleGroup: g, role: 'primary')),
            ..._secondaryMuscles.map(
                (g) => ExerciseMuscle(muscleGroup: g, role: 'secondary')),
          ]
        : const <ExerciseMuscle>[];

    final input = CustomExerciseInput(
      name: name,
      category: _category,
      met: metVal,
      equipment: _equipment,
      level: _level,
      description: descText.isEmpty ? null : descText,
      muscles: muscles,
    );

    setState(() => _saving = true);
    try {
      final saved = widget.existing != null
          ? await ApiClient.updateCustomExercise(widget.existing!.id, input)
          : await ApiClient.createCustomExercise(input);
      if (mounted) {
        Navigator.pop(context, saved);
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.message),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isStrength = _category == 'strength';
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.existing != null
            ? 'Edit custom exercise'
            : 'Create custom exercise'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Exercise Name',
              hintText: 'e.g. Ring Push-up, Sled Push',
            ),
          ),
          const SizedBox(height: 20),
          const Text('Category',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              ChoiceChip(
                label: const Text('Strength'),
                selected: _category == 'strength',
                onSelected: (_) => setState(() => _category = 'strength'),
              ),
              ChoiceChip(
                label: const Text('Cardio'),
                selected: _category == 'cardio',
                onSelected: (_) => setState(() => _category = 'cardio'),
              ),
              ChoiceChip(
                label: const Text('Flexibility'),
                selected: _category == 'flexibility',
                onSelected: (_) => setState(() => _category = 'flexibility'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          const Text('Equipment',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: _equipmentLabels.entries.map((entry) {
              return ChoiceChip(
                label: Text(entry.value),
                selected: _equipment == entry.key,
                onSelected: (_) => setState(() => _equipment = entry.key),
              );
            }).toList(),
          ),
          if (isStrength) ...[
            const SizedBox(height: 20),
            const Text('Main muscles (pick at least one)',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: _muscleLabels.entries.map((entry) {
                return FilterChip(
                  label: Text(entry.value),
                  selected: _primaryMuscles.contains(entry.key),
                  onSelected: (_) => _togglePrimary(entry.key),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
            const Text('Also works (optional)',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: _muscleLabels.entries.map((entry) {
                return FilterChip(
                  label: Text(entry.value),
                  selected: _secondaryMuscles.contains(entry.key),
                  onSelected: (_) => _toggleSecondary(entry.key),
                );
              }).toList(),
            ),
          ],
          const SizedBox(height: 16),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('More options',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            children: [
              const Align(
                alignment: Alignment.centerLeft,
                child: Text('Difficulty level',
                    style:
                        TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
              ),
              const SizedBox(height: 6),
              Align(
                alignment: Alignment.centerLeft,
                child: Wrap(
                  spacing: 8,
                  children: _levelLabels.entries.map((entry) {
                    return ChoiceChip(
                      label: Text(entry.value),
                      selected: _level == entry.key,
                      onSelected: (_) => setState(() => _level = entry.key),
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _metCtrl,
                decoration: const InputDecoration(
                  labelText: 'MET (intensity factor)',
                  helperText:
                      'light about 3, moderate about 5, vigorous about 8',
                ),
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _descCtrl,
                decoration: const InputDecoration(
                  labelText: 'Description (optional)',
                ),
              ),
              const SizedBox(height: 12),
            ],
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
                          strokeWidth: 2, color: Colors.white),
                    )
                  : Text(widget.existing != null
                      ? 'Save Changes'
                      : 'Create Exercise'),
            ),
          ),
        ],
      ),
    );
  }
}

