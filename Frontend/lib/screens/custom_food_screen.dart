import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_client.dart';

class CustomFoodScreen extends StatefulWidget {
  final FoodItem? existingFood;
  final String? initialName;

  const CustomFoodScreen({
    super.key,
    this.existingFood,
    this.initialName,
  });

  @override
  State<CustomFoodScreen> createState() => _CustomFoodScreenState();
}

class _CustomFoodScreenState extends State<CustomFoodScreen> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _servingGramsCtrl;
  late final TextEditingController _servingNameCtrl;
  late final TextEditingController _calCtrl;
  late final TextEditingController _proteinCtrl;
  late final TextEditingController _carbsCtrl;
  late final TextEditingController _fatCtrl;

  String _basis = 'serving';
  bool _saving = false;

  bool get _isEditing => widget.existingFood != null;

  @override
  void initState() {
    super.initState();
    final f = widget.existingFood;
    if (f != null) {
      final p = f.portions.isNotEmpty ? f.portions.first : null;
      if (p != null) {
        _basis = 'serving';
        final sg = p.gramWeight;
        final factor = sg / 100.0;
        _nameCtrl = TextEditingController(text: f.name);
        _servingGramsCtrl = TextEditingController(text: _fmt(sg));
        _servingNameCtrl = TextEditingController(text: p.unit);
        _calCtrl =
            TextEditingController(text: _fmt(f.caloriesPer100g * factor));
        _proteinCtrl =
            TextEditingController(text: _fmt(f.proteinPer100g * factor));
        _carbsCtrl = TextEditingController(text: _fmt(f.carbsPer100g * factor));
        _fatCtrl = TextEditingController(text: _fmt(f.fatPer100g * factor));
      } else {
        _basis = 'per_100g';
        _nameCtrl = TextEditingController(text: f.name);
        _servingGramsCtrl = TextEditingController(text: '100');
        _servingNameCtrl = TextEditingController(text: 'serving');
        _calCtrl = TextEditingController(text: _fmt(f.caloriesPer100g));
        _proteinCtrl = TextEditingController(text: _fmt(f.proteinPer100g));
        _carbsCtrl = TextEditingController(text: _fmt(f.carbsPer100g));
        _fatCtrl = TextEditingController(text: _fmt(f.fatPer100g));
      }
    } else {
      _nameCtrl = TextEditingController(text: widget.initialName ?? '');
      _servingGramsCtrl = TextEditingController(text: '100');
      _servingNameCtrl = TextEditingController(text: 'serving');
      _calCtrl = TextEditingController();
      _proteinCtrl = TextEditingController(text: '0');
      _carbsCtrl = TextEditingController(text: '0');
      _fatCtrl = TextEditingController(text: '0');
    }

    for (final c in [
      _servingGramsCtrl,
      _calCtrl,
      _proteinCtrl,
      _carbsCtrl,
      _fatCtrl,
    ]) {
      c.addListener(_onFieldChanged);
    }
  }

  static String _fmt(double v) =>
      v == v.roundToDouble() ? v.toInt().toString() : v.toStringAsFixed(1);

  void _onFieldChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _servingGramsCtrl.dispose();
    _servingNameCtrl.dispose();
    _calCtrl.dispose();
    _proteinCtrl.dispose();
    _carbsCtrl.dispose();
    _fatCtrl.dispose();
    super.dispose();
  }

  double get _servingGrams {
    final g = double.tryParse(_servingGramsCtrl.text.trim()) ?? 100.0;
    return g > 0 ? g : 100.0;
  }

  double get _calories => double.tryParse(_calCtrl.text.trim()) ?? 0.0;
  double get _protein => double.tryParse(_proteinCtrl.text.trim()) ?? 0.0;
  double get _carbs => double.tryParse(_carbsCtrl.text.trim()) ?? 0.0;
  double get _fat => double.tryParse(_fatCtrl.text.trim()) ?? 0.0;

  double get _kcalPer100g =>
      _basis == 'serving' ? _calories * (100.0 / _servingGrams) : _calories;

  bool get _macrosMismatch {
    if (_calories <= 0) return false;
    final fromMacros = 4.0 * _protein + 4.0 * _carbs + 9.0 * _fat;
    if (fromMacros <= 0) return false;
    return ((fromMacros - _calories).abs() / _calories) > 0.25;
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Food name is required.')),
      );
      return;
    }
    final cal = double.tryParse(_calCtrl.text.trim());
    if (cal == null || cal < 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter valid calories.')),
      );
      return;
    }
    final sg = _servingGrams;
    final sname = _servingNameCtrl.text.trim().isEmpty
        ? 'serving'
        : _servingNameCtrl.text.trim();

    final input = CustomFoodInput(
      name: name,
      basis: _basis,
      servingGrams: sg,
      servingName: sname,
      calories: cal,
      protein: _protein,
      carbs: _carbs,
      fat: _fat,
    );

    setState(() => _saving = true);
    try {
      final saved = _isEditing
          ? await ApiClient.updateCustomFood(widget.existingFood!.id, input)
          : await ApiClient.createCustomFood(input);
      if (mounted) Navigator.pop(context, saved);
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
    return Scaffold(
      appBar: AppBar(
        title: Text(_isEditing ? 'Edit Custom Food' : 'New Custom Food'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Food name',
              hintText: 'e.g. Jollof Rice (cooked)',
            ),
          ),
          const SizedBox(height: 16),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'serving', label: Text('Per serving')),
              ButtonSegment(value: 'per_100g', label: Text('Per 100 g')),
            ],
            selected: {_basis},
            onSelectionChanged: (sel) => setState(() => _basis = sel.first),
          ),
          if (_basis == 'serving') ...[
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  flex: 2,
                  child: TextField(
                    controller: _servingGramsCtrl,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(
                      labelText: 'Serving size (g)',
                      helperText:
                          'Not sure? Leave 100 and enter the numbers for one serving.',
                      helperMaxLines: 2,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _servingNameCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Serving unit',
                      hintText: 'serving',
                    ),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: _calCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: _basis == 'serving'
                  ? 'Calories per serving (kcal) *'
                  : 'Calories per 100 g (kcal) *',
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '= ${_kcalPer100g.toStringAsFixed(0)} kcal per 100 g',
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Color(0xFF4B5563),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _proteinCtrl,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Protein (g)'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _carbsCtrl,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Carbs (g)'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _fatCtrl,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Fat (g)'),
                ),
              ),
            ],
          ),
          if (_macrosMismatch) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFF59E0B)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: Color(0xFFB45309)),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      "These numbers don't quite add up",
                      style: TextStyle(fontSize: 12, color: Color(0xFF92400E)),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

