import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import '../widgets/food_picker_sheet.dart';

class RecipeBuilderScreen extends StatefulWidget {
  final int? existingFoodId;
  final Recipe? existingRecipe;
  final String? initialName;

  const RecipeBuilderScreen({
    super.key,
    this.existingFoodId,
    this.existingRecipe,
    this.initialName,
  });

  @override
  State<RecipeBuilderScreen> createState() => _RecipeBuilderScreenState();
}

class _RecipeBuilderScreenState extends State<RecipeBuilderScreen> {
  final _nameCtrl = TextEditingController();
  final _servingsCtrl = TextEditingController(text: '4');
  final _cookedCtrl = TextEditingController();

  final List<DraftRecipeIngredient> _ingredients = [];
  bool _loadingExisting = false;
  bool _saving = false;
  int? _editingFoodId;

  bool get _isEditing => _editingFoodId != null;

  @override
  void initState() {
    super.initState();
    if (widget.existingRecipe != null) {
      _applyRecipe(widget.existingRecipe!);
    } else if (widget.existingFoodId != null) {
      _editingFoodId = widget.existingFoodId;
      _loadRecipe(widget.existingFoodId!);
    } else if (widget.initialName != null) {
      _nameCtrl.text = widget.initialName!;
    }
    _servingsCtrl.addListener(_onChanged);
    _cookedCtrl.addListener(_onChanged);
  }

  void _onChanged() {
    if (mounted) setState(() {});
  }

  void _applyRecipe(Recipe r) {
    _editingFoodId = r.foodId;
    _nameCtrl.text = r.name;
    _servingsCtrl.text = _fmtNum(r.servings);
    _cookedCtrl.text =
        r.cookedWeightG != null ? _fmtNum(r.cookedWeightG!) : '';
    _ingredients
      ..clear()
      ..addAll(r.ingredients.map((ing) => DraftRecipeIngredient(
            foodId: ing.foodId,
            foodName: ing.foodName,
            quantity: ing.quantity,
            portionId: ing.portionId,
            portionName: ing.portionName,
            unit: ing.unit,
            gramWeight: ing.gramWeight,
            calories: ing.calories,
            protein: ing.protein,
            carbs: ing.carbs,
            fat: ing.fat,
          )));
  }

  Future<void> _loadRecipe(int foodId) async {
    setState(() => _loadingExisting = true);
    try {
      final r = await ApiClient.getRecipe(foodId);
      if (mounted) {
        setState(() {
          _applyRecipe(r);
          _loadingExisting = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _loadingExisting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.message),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    }
  }

  String _fmtNum(double v) =>
      v == v.roundToDouble() ? v.toInt().toString() : v.toString();

  @override
  void dispose() {
    _nameCtrl.dispose();
    _servingsCtrl.dispose();
    _cookedCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickIngredient({String? initialQuery}) async {
    final picked = await showModalBottomSheet<PickedFoodItem>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => FoodPickerSheet(
        initialQuery: initialQuery,
        excludeRecipes: true,
        allowCreateRecipe: false,
        confirmLabel: 'Add Ingredient',
      ),
    );
    if (picked == null || !mounted) return;

    final factor = picked.gramWeight / 100.0;
    final ing = DraftRecipeIngredient(
      foodId: picked.food.id,
      foodName: picked.food.name,
      quantity: picked.quantity,
      portionId: picked.portionId,
      portionName: picked.portionName,
      unit: picked.unit,
      gramWeight: picked.gramWeight,
      calories: picked.food.caloriesPer100g * factor,
      protein: picked.food.proteinPer100g * factor,
      carbs: picked.food.carbsPer100g * factor,
      fat: picked.food.fatPer100g * factor,
    );
    setState(() => _ingredients.add(ing));
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a recipe name.')),
      );
      return;
    }
    final servings = double.tryParse(_servingsCtrl.text.trim()) ?? 0;
    if (servings <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Portions must be greater than 0.')),
      );
      return;
    }
    if (_ingredients.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add at least one ingredient.')),
      );
      return;
    }

    final cookedText = _cookedCtrl.text.trim();
    final cookedWeightG =
        cookedText.isNotEmpty ? double.tryParse(cookedText) : null;
    if (cookedText.isNotEmpty && (cookedWeightG == null || cookedWeightG <= 0)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Finished dish weight must be greater than 0g.')),
      );
      return;
    }

    setState(() => _saving = true);
    try {
      final input = RecipeInput(
        name: name,
        servings: servings,
        cookedWeightG: cookedWeightG,
        ingredients: _ingredients.map((i) => i.toItemPayload()).toList(),
      );
      final saved = _isEditing
          ? await ApiClient.updateRecipe(_editingFoodId!, input)
          : await ApiClient.createRecipe(input);
      if (mounted) {
        Navigator.pop(context, saved.toFoodItem());
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
    if (_loadingExisting) {
      return Scaffold(
        appBar: AppBar(title: const Text('Edit Recipe')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final servings = double.tryParse(_servingsCtrl.text.trim()) ?? 1;
    final cookedText = _cookedCtrl.text.trim();
    final cookedWeightG =
        cookedText.isNotEmpty ? double.tryParse(cookedText) : null;
    final preview = computeRecipePreview(
      ingredients: _ingredients,
      servings: servings,
      cookedWeightG: cookedWeightG,
    );
    final showOilPrompt = _ingredients.isNotEmpty &&
        !hasCookingFat(_ingredients.map((i) => i.foodName));

    return Scaffold(
      appBar: AppBar(
        title: Text(_isEditing ? 'Edit Recipe' : 'New Recipe'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Recipe name',
              hintText: 'e.g. Jollof Rice Pot, Egusi Soup',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _servingsCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
            ],
            decoration: const InputDecoration(
              labelText: 'How many equal portions does it make?',
              helperText: 'bowls, ladles, plates...',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _cookedCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
            ],
            decoration: const InputDecoration(
              labelText: 'I weighed the finished dish (g) (optional)',
              hintText: 'Leave blank to sum raw ingredients',
            ),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Ingredients',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                ),
              ),
              OutlinedButton.icon(
                onPressed: () => _pickIngredient(),
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add ingredient'),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_ingredients.isEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFE5E7EB)),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Text(
                'No ingredients yet. Add what went into the pot.',
                style: TextStyle(fontSize: 13, color: Color(0xFF6B7280)),
              ),
            )
          else
            ..._ingredients.asMap().entries.map((entry) {
              final idx = entry.key;
              final ing = entry.value;
              final label = ing.portionName != null
                  ? '${_fmtNum(ing.quantity)} × ${ing.portionName} (${ing.gramWeight.toStringAsFixed(0)}g)'
                  : '${ing.gramWeight.toStringAsFixed(0)}g';
              return Card(
                margin: const EdgeInsets.symmetric(vertical: 4),
                child: ListTile(
                  dense: true,
                  title: Text(
                    ing.foodName,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                  subtitle: Text(
                    '$label • ${ing.calories.toStringAsFixed(0)} kcal',
                    style: const TextStyle(fontSize: 12),
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.close, size: 16),
                    onPressed: () => setState(() => _ingredients.removeAt(idx)),
                  ),
                ),
              );
            }),
          if (showOilPrompt) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFFFBEB),
                border: Border.all(color: const Color(0xFFF59E0B)),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.oil_barrel_outlined,
                      size: 18, color: Color(0xFFD97706)),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Did you cook with oil or butter? 1 tablespoon is about 120 kcal.',
                      style: TextStyle(fontSize: 12, color: Color(0xFF92400E)),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: () => _pickIngredient(initialQuery: 'oil'),
                    child: const Text('Add oil'),
                  ),
                ],
              ),
            ),
          ],
          if (_ingredients.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFF9FAFB),
                border: Border.all(color: const Color(0xFFE5E7EB)),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '1 portion (${preview.portionGrams.toStringAsFixed(0)} g) = ${preview.caloriesPerPortion.toStringAsFixed(0)} kcal',
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  NutrientRow(
                    calories: preview.caloriesPerPortion,
                    protein: preview.proteinPerPortion,
                    carbs: preview.carbsPerPortion,
                    fat: preview.fatPerPortion,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Whole pot (${preview.cookedGrams.toStringAsFixed(0)} g): ${preview.totalCalories.toStringAsFixed(0)} kcal • ${preview.caloriesPer100g.toStringAsFixed(0)} kcal / 100g',
                    style:
                        const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : Text(_isEditing ? 'Save Changes' : 'Create Recipe'),
          ),
        ],
      ),
    );
  }
}
