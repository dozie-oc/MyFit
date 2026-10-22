import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'recommendation_sheet.dart';
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
                MaterialPageRoute(builder: (_) => const _AddMealScreen()),
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
        final name = it.foodName;
        final gram = it.gramWeight > 0 ? it.gramWeight.toStringAsFixed(0) : '';
        return name.isNotEmpty ? (gram.isNotEmpty ? '$name (${gram}g)' : name) : 'Food #${it.foodId}';
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
            final foodName = item.foodName.isNotEmpty ? item.foodName : 'Food #${item.foodId}';
            final portionName = item.portionName;
            final gramWeight = item.gramWeight > 0 ? item.gramWeight.toStringAsFixed(0) : '?';
            
            final labelText = portionName != null && portionName.isNotEmpty
                ? '$foodName ($portionName · ${gramWeight}g)'
                : '$foodName (${gramWeight}g)';

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: InfoTile(
                label: labelText,
                value: '${cal.toStringAsFixed(0)} kcal',
                valueColor: const Color(0xFF2563EB),
              ),
            );
          }),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────
// ADD MEAL SCREEN
// ─────────────────────────────────────────

class _AddMealScreen extends StatefulWidget {
  const _AddMealScreen();

  @override
  State<_AddMealScreen> createState() => _AddMealScreenState();
}

class _AddMealScreenState extends State<_AddMealScreen> {
  DateTime _date = DateTime.now();
  String _mealType = 'breakfast';
  final List<_DraftMealItem> _items = [];
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final hour = DateTime.now().hour;
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

  Future<void> _addItem() async {
    final item = await showModalBottomSheet<_DraftMealItem>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) => const _AddMealItemSheet(),
    );
    if (item != null) setState(() => _items.add(item));
  }

  Future<void> _save() async {
    if (_items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Add at least one food item.')));
      return;
    }
    setState(() => _saving = true);
    try {
      final payloadItems = _items.map((it) {
        return <String, dynamic>{
          'food_id': it.foodId,
          'quantity': it.quantity,
          if (it.portionId != null) 'portion_id': it.portionId,
          if (it.unit != null) 'unit': it.unit,
        };
      }).toList();

      await ApiClient.createMeal({
        'date': _dateStr,
        'meal_type': _mealType,
        'items': payloadItems,
      });
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('New Meal'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child:
                        CircularProgressIndicator(strokeWidth: 2))
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
          const SizedBox(height: 20),
          Row(
            children: [
              const Text('Items',
                  style: TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 15)),
              const Spacer(),
              TextButton.icon(
                onPressed: _addItem,
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add food'),
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
              final name = item.foodName;
              final portionName = item.portionName;
              final subtitle = portionName != null
                  ? '${item.quantity}× $portionName'
                  : '${item.quantity}${item.unit ?? 'g'}';
              return Card(
                margin: const EdgeInsets.symmetric(vertical: 4),
                child: ListTile(
                  dense: true,
                  title: Text(name,
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                  subtitle: Text(subtitle,
                      style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                  trailing: IconButton(
                    icon: const Icon(Icons.close,
                        size: 18, color: Color(0xFF9CA3AF)),
                    onPressed: () =>
                        setState(() => _items.removeAt(i)),
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────
// ADD MEAL ITEM SHEET
// ─────────────────────────────────────────

/// A food line the user has added to a meal that hasn't been saved yet.
class _DraftMealItem {
  final int foodId;
  final String foodName;
  final double quantity;
  final int? portionId;
  final String? portionName;
  final String? unit;

  const _DraftMealItem({
    required this.foodId,
    required this.foodName,
    required this.quantity,
    this.portionId,
    this.portionName,
    this.unit,
  });
}

class _AddMealItemSheet extends StatefulWidget {
  const _AddMealItemSheet();

  @override
  State<_AddMealItemSheet> createState() => _AddMealItemSheetState();
}

class _AddMealItemSheetState extends State<_AddMealItemSheet> {
  final _searchCtrl = TextEditingController();
  final _qtyCtrl = TextEditingController(text: '100');
  final _unitCtrl = TextEditingController(text: 'g');

  List<FoodItem>? _foods;
  FoodItem? _selected;
  FoodPortion? _selectedPortion;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    ApiClient.getFoods().then((f) {
      if (mounted) setState(() => _foods = f);
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _qtyCtrl.dispose();
    _unitCtrl.dispose();
    super.dispose();
  }

  void _confirm() {
    if (_selected == null) return;
    final qty = double.tryParse(_qtyCtrl.text) ?? 0;
    if (qty <= 0) return;

    final portion = _selectedPortion;
    final item = _DraftMealItem(
      foodId: _selected!.id,
      foodName: _selected!.name,
      quantity: qty,
      portionId: portion?.id,
      portionName: portion?.name,
      unit: portion == null ? _unitCtrl.text.trim().toLowerCase() : null,
    );

    Navigator.pop(context, item);
  }

  @override
  Widget build(BuildContext context) {
    final portions = _selected?.portions ?? const <FoodPortion>[];

    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.8,
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
            const Text('Select Food',
                style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            TextField(
              controller: _searchCtrl,
              decoration: const InputDecoration(
                hintText: 'Search food library...',
                prefixIcon: Icon(Icons.search, size: 20),
              ),
              onChanged: (q) {
                setState(() => _loading = true);
                Future.delayed(const Duration(milliseconds: 300), () async {
                  final f = q.trim().isEmpty
                      ? await ApiClient.getFoods()
                      : await ApiClient.getFoods(q.trim());
                  if (mounted) {
                    setState(() {
                      _foods = f;
                      _loading = false;
                    });
                  }
                });
              },
            ),
            const SizedBox(height: 8),
            if (_loading)
              const LinearProgressIndicator()
            else if (_foods != null)
              Container(
                constraints: const BoxConstraints(maxHeight: 180),
                decoration: BoxDecoration(
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _foods!.length,
                  itemBuilder: (_, i) {
                    final f = _foods![i];
                    final isSelected =
                        _selected?.id == f.id;
                    return ListTile(
                      dense: true,
                      selected: isSelected,
                      title: Text(f.name,
                          style: const TextStyle(fontSize: 13)),
                      onTap: () => setState(() {
                        _selected = f;
                        _selectedPortion = null;
                      }),
                      trailing: isSelected
                          ? const Icon(Icons.check,
                              size: 16, color: Color(0xFF2563EB))
                          : null,
                    );
                  },
                ),
              ),
            if (_selected != null) ...[
              const SizedBox(height: 16),
              const Divider(),
              const SizedBox(height: 8),
              Text('Selected: ${_selected!.name}',
                  style: const TextStyle(
                       fontWeight: FontWeight.w600, fontSize: 13)),
              const SizedBox(height: 12),
              if (portions.isNotEmpty) ...[
                const Text('Choose a serving size',
                    style: TextStyle(
                        fontSize: 12, color: Color(0xFF9CA3AF))),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  children: [
                    ChoiceChip(
                      label: const Text('Custom grams'),
                      selected: _selectedPortion == null,
                      onSelected: (_) =>
                          setState(() => _selectedPortion = null),
                    ),
                    ...portions.map((p) {
                      final isSelected =
                          _selectedPortion?.id == p.id;
                      return ChoiceChip(
                        label: Text('${p.name} (${p.gramWeight.toStringAsFixed(0)}g)'),
                        selected: isSelected,
                        onSelected: (_) =>
                            setState(() => _selectedPortion = p),
                      );
                    }),
                  ],
                ),
                const SizedBox(height: 12),
              ],
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _qtyCtrl,
                      decoration: InputDecoration(
                          labelText: _selectedPortion != null
                              ? 'Number of Servings'
                              : 'Grams'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(
                            RegExp(r'[\d.]'))
                      ],
                    ),
                  ),
                  if (_selectedPortion == null) ...[
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: _unitCtrl,
                        decoration: const InputDecoration(
                            labelText: 'Unit'),
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _confirm,
                child: const Text('Add to Meal'),
              ),
            ],
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
