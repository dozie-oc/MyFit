import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'recommendation_sheet.dart';
import '../widgets/food_picker_sheet.dart';
import '../main.dart' show TabActivatedNotifier;

// ─────────────────────────────────────────
// MEALS SCREEN
// ─────────────────────────────────────────

class MealsScreen extends StatefulWidget {
  final TabActivatedNotifier? tabNotifier;
  const MealsScreen({super.key, this.tabNotifier});

  @override
  State<MealsScreen> createState() => _MealsScreenState();
}

class _MealsScreenState extends State<MealsScreen> {
  late Future<List<Meal>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.getMeals();
    ApiClient.addDataListener(_onDataChanged, {DataScope.meals});
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
        _future = ApiClient.getMeals();
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
        title: const Text('Meals'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () async {
              final created = await Navigator.push<bool>(
                context,
                MaterialPageRoute(builder: (_) => const MealEditorScreen()),
              );
              if (created == true) _reload();
            },
          ),
        ],
      ),
      floatingActionButton: const RecommendationFAB(filterType: 'meal'),
      body: FutureBuilder<List<Meal>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snap.hasError) {
            return ErrorView(
                message: snap.error.toString(), onRetry: _reload);
          }
          final meals = snap.data ?? [];
          if (meals.isEmpty) {
            return RefreshIndicator(
              onRefresh: _handleRefresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [
                  SizedBox(height: 100),
                  EmptyView(
                      message: 'No meals logged yet. Tap + to add one.',
                      icon: Icons.restaurant_menu_outlined),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _handleRefresh,
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(top: 8, bottom: 80),
              itemCount: meals.length,
              itemBuilder: (_, i) => _MealCard(
                meal: meals[i],
                onDeleted: _reload,
              ),
            ),
          );
        },
      ),
    );
  }
}

class _MealCard extends StatelessWidget {
  final Meal meal;
  final VoidCallback onDeleted;
  const _MealCard({required this.meal, required this.onDeleted});

  @override
  Widget build(BuildContext context) {
    final date = meal.date;
    final cal = meal.calories;
    final protein = meal.protein;
    final carbs = meal.carbs;
    final fat = meal.fat;
    final items = meal.items;

    String itemSummary = '';
    if (items.isNotEmpty) {
      final names = items.map((it) {
        final prefix = it.foodKind == 'quick' ? '≈ ' : '';
        final name = it.foodName;
        final gram = it.gramWeight > 0 ? it.gramWeight.toStringAsFixed(0) : '';
        if (name.isEmpty) return 'Food #${it.foodId}';
        if (it.foodKind == 'quick') return '$prefix$name';
        return gram.isNotEmpty ? '$prefix$name (${gram}g)' : '$prefix$name';
      }).toList();
      itemSummary = names.join(', ');
    } else {
      itemSummary = 'No food items';
    }

    final mealType = meal.mealType.toUpperCase();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      child: Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: () => _showDetail(context, meal, onDeleted),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        mealType,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(date,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600, fontSize: 14)),
                    const Spacer(),
                    Text('${cal.toStringAsFixed(0)} kcal',
                        style: const TextStyle(
                            color: Color(0xFF2563EB),
                            fontWeight: FontWeight.w600)),
                  ],
                ),
                const SizedBox(height: 4),
                Text(itemSummary,
                    style: const TextStyle(
                        fontSize: 13, color: Color(0xFF4B5563), fontWeight: FontWeight.w500),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 12),
                NutrientRow(
                    calories: cal,
                    protein: protein,
                    carbs: carbs,
                    fat: fat),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showDetail(BuildContext context, Meal meal,
      VoidCallback onDeleted) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) =>
          _MealDetailSheet(meal: meal, onDeleted: onDeleted),
    );
  }
}

class _MealDetailSheet extends StatelessWidget {
  final Meal meal;
  final VoidCallback onDeleted;
  const _MealDetailSheet(
      {required this.meal, required this.onDeleted});

  @override
  Widget build(BuildContext context) {
    final items = meal.items;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.65,
      builder: (_, ctrl) => ListView(
        controller: ctrl,
        padding: const EdgeInsets.all(20),
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
          Row(
            children: [
              Text(
                '${meal.mealType.toUpperCase()} · ${meal.date}',
                style: const TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.delete_outline,
                    color: Color(0xFFEF4444)),
                onPressed: () async {
                  Navigator.pop(context);
                  try {
                    await ApiClient.deleteMeal(meal.id);
                    onDeleted();
                  } catch (_) {}
                },
              ),
            ],
          ),
          NutrientRow(
            calories: meal.calories,
            protein: meal.protein,
            carbs: meal.carbs,
            fat: meal.fat,
          ),
          const SizedBox(height: 16),
          const Text('Food Items',
              style: TextStyle(
                  fontSize: 12,
                  color: Color(0xFF9CA3AF),
                  fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          ...items.map((item) {
            final cal = item.calories;
            final prefix = item.foodKind == 'quick' ? '≈ ' : '';
            final foodName = item.foodName.isNotEmpty ? item.foodName : 'Food #${item.foodId}';
            final portionName = item.portionName;
            final gramWeight = item.gramWeight > 0 ? item.gramWeight.toStringAsFixed(0) : '?';

            final labelText = item.foodKind == 'quick'
                ? '$prefix$foodName'
                : (portionName != null && portionName.isNotEmpty
                    ? '$prefix$foodName ($portionName · ${gramWeight}g)'
                    : '$prefix$foodName (${gramWeight}g)');

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: InfoTile(
                label: labelText,
                value: '${cal.toStringAsFixed(0)} kcal',
                valueColor: const Color(0xFF2563EB),
              ),
            );
          }),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.edit_outlined, size: 16),
                  label: const Text('Edit meal'),
                  onPressed: () async {
                    final navigator = Navigator.of(context);
                    navigator.pop();
                    final updated = await navigator.push<bool>(
                      MaterialPageRoute(
                        builder: (_) => MealEditorScreen(existingMeal: meal),
                      ),
                    );
                    if (updated == true) {
                      onDeleted();
                    }
                  },
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.replay_outlined, size: 16),
                  label: const Text('Log again'),
                  onPressed: () async {
                    final now = DateTime.now();
                    final today =
                        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
                    try {
                      await ApiClient.copyMeal(meal.id, date: today);
                      if (context.mounted) {
                        Navigator.pop(context);
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text('Logged again for today')),
                        );
                      }
                    } on ApiException catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(e.message),
                            backgroundColor: Colors.red.shade700,
                          ),
                        );
                      }
                    }
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────
// MEAL EDITOR SCREEN (CREATE OR EDIT MEAL)
// ─────────────────────────────────────────

const Map<String, String> _kDirectUnitLabels = {
  'g': 'Grams (g)',
  'oz': 'Ounces (oz)',
  'ml': 'Milliliters (ml)',
  'kg': 'Kilograms (kg)',
  'lb': 'Pounds (lb)',
};

class MealEditorScreen extends StatefulWidget {
  final Meal? existingMeal;
  final List<DraftMealItem>? initialItems;
  final bool loadCatalogOnInit;
  final Future<PickedFoodItem?> Function(
      BuildContext context, DraftMealItem? existingItem)? onPickFood;
  final Future<void> Function(
      Map<String, dynamic> payload, int? existingMealId)? onSubmitMeal;

  const MealEditorScreen({
    super.key,
    this.existingMeal,
    this.initialItems,
    this.loadCatalogOnInit = true,
    this.onPickFood,
    this.onSubmitMeal,
  });

  @override
  State<MealEditorScreen> createState() => _MealEditorScreenState();
}

class _MealEditorScreenState extends State<MealEditorScreen> {
  late DateTime _date;
  late String _mealType;
  final List<DraftMealItem> _items = [];
  bool _saving = false;

  bool get _isEditing => widget.existingMeal != null;

  @override
  void initState() {
    super.initState();
    final existing = widget.existingMeal;
    if (existing != null) {
      _date = DateTime.tryParse(existing.date) ?? DateTime.now();
      _mealType = existing.mealType.isNotEmpty ? existing.mealType : 'snack';
      _items.addAll(
        existing.items.map((item) => DraftMealItem.fromMealItem(item)),
      );
      if (widget.loadCatalogOnInit) {
        _hydrateCatalogFoods();
      }
    } else {
      _date = DateTime.now();
      final hour = _date.hour;
      if (hour < 11) {
        _mealType = 'breakfast';
      } else if (hour < 16) {
        _mealType = 'lunch';
      } else if (hour < 21) {
        _mealType = 'dinner';
      } else {
        _mealType = 'snack';
      }
    }

    if (widget.initialItems != null) {
      _items
        ..clear()
        ..addAll(widget.initialItems!);
    }
  }

  Future<void> _hydrateCatalogFoods() async {
    try {
      final foods = await ApiClient.getFoods();
      if (!mounted) return;
      final byId = {for (final f in foods) f.id: f};
      setState(() {
        for (var i = 0; i < _items.length; i++) {
          final current = _items[i];
          final loaded = byId[current.food.id];
          if (loaded != null) {
            _items[i] = current.withCatalogFood(loaded);
          }
        }
      });
    } catch (_) {
      // Keep snapshot-derived food details if catalog fetch fails offline.
    }
  }

  Future<void> _pickDate() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
    );
    if (d != null) setState(() => _date = d);
  }

  String get _dateStr =>
      '${_date.year}-${_date.month.toString().padLeft(2, '0')}-${_date.day.toString().padLeft(2, '0')}';

  Future<PickedFoodItem?> _openPicker({DraftMealItem? existingItem}) {
    if (widget.onPickFood != null) {
      return widget.onPickFood!(context, existingItem);
    }
    return showModalBottomSheet<PickedFoodItem>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) => FoodPickerSheet(
        initialFood: existingItem?.food,
        initialPortionId: existingItem?.portionId,
        initialQuantity: existingItem?.quantity,
        initialUnit: existingItem?.portionId == null ? existingItem?.unit : null,
        confirmLabel: existingItem != null ? 'Update Food' : 'Add to Meal',
      ),
    );
  }

  Future<void> _addItem() async {
    final picked = await _openPicker();
    if (picked != null && mounted) {
      setState(() {
        _items.add(picked.toDraftMealItem());
      });
    }
  }

  Future<void> _changeItemFood(int index) async {
    if (index < 0 || index >= _items.length) return;
    final current = _items[index];
    final picked = await _openPicker(existingItem: current);
    if (picked != null && mounted) {
      setState(() {
        _items[index] = picked.toDraftMealItem();
      });
    }
  }

  void _updateItem(int index, DraftMealItem updated) {
    if (index < 0 || index >= _items.length) return;
    setState(() {
      _items[index] = updated;
    });
  }

  void _removeItem(int index) {
    if (index < 0 || index >= _items.length) return;
    setState(() {
      _items.removeAt(index);
    });
  }

  Future<void> _showQuickAddDialog() async {
    final nameCtrl = TextEditingController();
    final calCtrl = TextEditingController();
    final proCtrl = TextEditingController();
    final carbCtrl = TextEditingController();
    final fatCtrl = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Quick add (estimate)'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'What did you eat?',
                  hintText: 'e.g. Lunch plate',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: calCtrl,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'About how many calories (kcal)? *',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: proCtrl,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Protein (g)'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: carbCtrl,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Carbs (g)'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: fatCtrl,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Fat (g)'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Log estimate'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;
    final name = nameCtrl.text.trim();
    final cal = double.tryParse(calCtrl.text.trim());
    if (name.isEmpty || cal == null || cal < 0) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enter a name and calories.')),
        );
      }
      return;
    }

    setState(() => _saving = true);
    try {
      await ApiClient.quickAddMeal(
        date: _dateStr,
        mealType: _mealType,
        name: name,
        calories: cal,
        protein: double.tryParse(proCtrl.text.trim()) ?? 0,
        carbs: double.tryParse(carbCtrl.text.trim()) ?? 0,
        fat: double.tryParse(fatCtrl.text.trim()) ?? 0,
      );
      if (mounted) Navigator.pop(context, true);
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

  Future<void> _save() async {
    if (_items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Add at least one food item.')));
      return;
    }
    if (_items.any((it) => it.quantity <= 0)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Each food item must have a quantity greater than 0.')));
      return;
    }

    setState(() => _saving = true);
    try {
      final payload = <String, dynamic>{
        'date': _dateStr,
        'meal_type': _mealType,
        'items': _items.map((it) => it.toItemPayload()).toList(),
      };

      if (widget.onSubmitMeal != null) {
        await widget.onSubmitMeal!(payload, widget.existingMeal?.id);
      } else if (_isEditing) {
        await ApiClient.updateMeal(widget.existingMeal!.id, payload);
      } else {
        await ApiClient.createMeal(payload);
      }
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
    final totals = computeMealTotals(_items);

    return Scaffold(
      appBar: AppBar(
        title: Text(_isEditing ? 'Edit Meal' : 'New Meal'),
        actions: [
          TextButton(
            key: const Key('save-meal-button'),
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          OutlinedButton.icon(
            onPressed: _pickDate,
            icon: const Icon(Icons.calendar_today, size: 16),
            label: Text('Date: $_dateStr'),
          ),
          const SizedBox(height: 16),
          const Text('Meal Type',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'breakfast', label: Text('Breakfast')),
              ButtonSegment(value: 'lunch', label: Text('Lunch')),
              ButtonSegment(value: 'dinner', label: Text('Dinner')),
              ButtonSegment(value: 'snack', label: Text('Snack')),
            ],
            selected: {_mealType},
            onSelectionChanged: (newVal) {
              setState(() => _mealType = newVal.first);
            },
          ),
          const SizedBox(height: 16),
          Container(
            key: const Key('meal-totals-card'),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFFF9FAFB),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFE5E7EB)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text(
                      'Meal Totals',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF111827),
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '${_items.length} ${_items.length == 1 ? 'item' : 'items'} · ${totals.totalGrams.toStringAsFixed(0)}g',
                      key: const Key('meal-totals-weight'),
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                NutrientRow(
                  calories: totals.calories,
                  protein: totals.protein,
                  carbs: totals.carbs,
                  fat: totals.fat,
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            runSpacing: 4,
            children: [
              const Text('Items',
                  style: TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 15)),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (!_isEditing)
                    TextButton.icon(
                      onPressed: _saving ? null : _showQuickAddDialog,
                      icon: const Icon(Icons.bolt, size: 16),
                      label: const Text('Quick add'),
                    ),
                  TextButton.icon(
                    key: const Key('add-food-button'),
                    onPressed: _saving ? null : _addItem,
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('Add food'),
                  ),
                ],
              ),
            ],
          ),
          if (_items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(
                  child: Text('No items yet. Tap "+ Add food" above.',
                      style: TextStyle(color: Color(0xFF9CA3AF)))),
            )
          else
            ..._items.asMap().entries.map((e) {
              final i = e.key;
              final item = e.value;
              return _MealDraftItemCard(
                key: ValueKey('draft-meal-item-$i-${item.food.id}'),
                index: i,
                item: item,
                onChangeFood: () => _changeItemFood(i),
                onChanged: (updated) => _updateItem(i, updated),
                onRemove: () => _removeItem(i),
              );
            }),
        ],
      ),
    );
  }
}

class _MealDraftItemCard extends StatefulWidget {
  final int index;
  final DraftMealItem item;
  final VoidCallback onChangeFood;
  final ValueChanged<DraftMealItem> onChanged;
  final VoidCallback onRemove;

  const _MealDraftItemCard({
    super.key,
    required this.index,
    required this.item,
    required this.onChangeFood,
    required this.onChanged,
    required this.onRemove,
  });

  @override
  State<_MealDraftItemCard> createState() => _MealDraftItemCardState();
}

class _MealDraftItemCardState extends State<_MealDraftItemCard> {
  late final TextEditingController _qtyCtrl;

  @override
  void initState() {
    super.initState();
    _qtyCtrl = TextEditingController(text: _formatNumber(widget.item.quantity));
  }

  @override
  void didUpdateWidget(covariant _MealDraftItemCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final currentParsed = double.tryParse(_qtyCtrl.text.trim());
    if (oldWidget.item.food.id != widget.item.food.id ||
        oldWidget.item.portionId != widget.item.portionId ||
        oldWidget.item.unit != widget.item.unit ||
        (currentParsed != null &&
            (currentParsed - widget.item.quantity).abs() > 1e-4)) {
      _qtyCtrl.text = _formatNumber(widget.item.quantity);
    }
  }

  @override
  void dispose() {
    _qtyCtrl.dispose();
    super.dispose();
  }

  String _formatNumber(double val) {
    if (val == val.roundToDouble()) return val.toInt().toString();
    return val.toStringAsFixed(1);
  }

  List<FoodPortion> _availablePortions(DraftMealItem item) {
    final list = <FoodPortion>[...item.food.portions];
    if (item.portionId != null &&
        !list.any((p) => p.id == item.portionId) &&
        item.portionGramWeight != null) {
      list.insert(
        0,
        FoodPortion(
          id: item.portionId!,
          name: item.portionName ?? item.unit,
          quantity: item.portionBaseQuantity,
          unit: item.unit,
          gramWeight: item.portionGramWeight!,
        ),
      );
    }
    return list;
  }

  String _dropdownValue(DraftMealItem item, List<FoodPortion> portions) {
    if (item.portionId != null &&
        portions.any((p) => p.id == item.portionId)) {
      return 'portion:${item.portionId}';
    }
    final normalizedUnit = normalizeDirectUnit(item.unit);
    return 'unit:$normalizedUnit';
  }

  void _onPortionOrUnitSelected(
    String? selection,
    DraftMealItem item,
    List<FoodPortion> portions,
  ) {
    if (selection == null) return;
    if (selection.startsWith('portion:')) {
      final id = int.tryParse(selection.substring('portion:'.length));
      if (id == null) return;
      FoodPortion? matched;
      for (final p in portions) {
        if (p.id == id) {
          matched = p;
          break;
        }
      }
      if (matched != null) {
        final nextQty = item.portionId == null
            ? (matched.quantity > 0 ? matched.quantity : 1.0)
            : item.quantity;
        final updated = item.withPortion(matched, quantity: nextQty);
        _qtyCtrl.text = _formatNumber(updated.quantity);
        widget.onChanged(updated);
      }
    } else if (selection.startsWith('unit:')) {
      final newUnit = selection.substring('unit:'.length);
      final updated = item.withUnit(newUnit);
      _qtyCtrl.text = _formatNumber(updated.quantity);
      widget.onChanged(updated);
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    final i = widget.index;
    final portions = _availablePortions(item);
    final selectedValue = _dropdownValue(item, portions);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(6),
                    onTap: widget.onChangeFood,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.food.name,
                          key: Key('item-food-name-$i'),
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${item.gramWeight.toStringAsFixed(0)}g · ${item.calories.toStringAsFixed(0)} kcal · P ${item.protein.toStringAsFixed(1)}g · C ${item.carbs.toStringAsFixed(1)}g · F ${item.fat.toStringAsFixed(1)}g',
                          key: Key('item-macros-$i'),
                          style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFF4B5563),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                IconButton(
                  key: Key('change-food-$i'),
                  tooltip: 'Change food',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.swap_horiz,
                      size: 20, color: Color(0xFF2563EB)),
                  onPressed: widget.onChangeFood,
                ),
                IconButton(
                  key: Key('remove-item-$i'),
                  tooltip: 'Remove item',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.delete_outline,
                      size: 20, color: Color(0xFFEF4444)),
                  onPressed: widget.onRemove,
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                SizedBox(
                  width: 96,
                  child: TextField(
                    key: Key('item-qty-$i'),
                    controller: _qtyCtrl,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    inputFormatters: [
                      FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
                    ],
                    decoration: InputDecoration(
                      labelText: item.portionId != null ? 'Servings' : 'Amount',
                      isDense: true,
                    ),
                    onChanged: (raw) {
                      final parsed = double.tryParse(raw.trim()) ?? 0.0;
                      widget.onChanged(item.withQuantity(parsed));
                    },
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    key: Key('item-unit-portion-$i-$selectedValue'),
                    initialValue: selectedValue,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Portion / Unit',
                      isDense: true,
                    ),
                    items: [
                      ...portions.map(
                        (p) => DropdownMenuItem<String>(
                          value: 'portion:${p.id}',
                          child: Text(
                            '${p.name} (${p.gramWeight.toStringAsFixed(0)}g)',
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 13),
                          ),
                        ),
                      ),
                      ...kSupportedDirectUnits.map(
                        (u) => DropdownMenuItem<String>(
                          value: 'unit:$u',
                          child: Text(
                            _kDirectUnitLabels[u] ?? u,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 13),
                          ),
                        ),
                      ),
                    ],
                    onChanged: (val) =>
                        _onPortionOrUnitSelected(val, item, portions),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
