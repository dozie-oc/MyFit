import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../screens/custom_food_screen.dart';
import '../screens/recipe_builder_screen.dart';

class PickedFoodItem {
  final FoodItem food;
  final double quantity;
  final int? portionId;
  final String? portionName;
  final String? unit;
  final double gramWeight;

  const PickedFoodItem({
    required this.food,
    required this.quantity,
    this.portionId,
    this.portionName,
    this.unit,
    required this.gramWeight,
  });
}

class FoodPickerSheet extends StatefulWidget {
  final String? initialQuery;
  final bool excludeRecipes;
  final bool allowCreateRecipe;
  final String confirmLabel;

  const FoodPickerSheet({
    super.key,
    this.initialQuery,
    this.excludeRecipes = false,
    this.allowCreateRecipe = true,
    this.confirmLabel = 'Add to Meal',
  });

  @override
  State<FoodPickerSheet> createState() => _FoodPickerSheetState();
}

class _FoodPickerSheetState extends State<FoodPickerSheet> {
  late final TextEditingController _searchCtrl;
  final _qtyCtrl = TextEditingController(text: '100');
  final _unitCtrl = TextEditingController(text: 'g');

  List<FoodItem>? _foods;
  FoodItem? _selected;
  FoodPortion? _selectedPortion;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    final q = (widget.initialQuery ?? '').trim();
    _searchCtrl = TextEditingController(text: q);
    _fetchFoods(q);
  }

  Future<void> _fetchFoods(String query) async {
    setState(() => _loading = true);
    try {
      final raw = query.isEmpty
          ? await ApiClient.getFoods()
          : await ApiClient.getFoods(query);
      final filtered = widget.excludeRecipes
          ? raw.where((f) => f.kind != 'recipe').toList()
          : raw;
      if (mounted) {
        setState(() {
          _foods = filtered;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _qtyCtrl.dispose();
    _unitCtrl.dispose();
    super.dispose();
  }

  void _selectFood(FoodItem f) {
    setState(() {
      _selected = f;
      _selectedPortion = f.portions.isNotEmpty ? f.portions.first : null;
      _qtyCtrl.text = _selectedPortion != null ? '1' : '100';
    });
  }

  Future<void> _openCreateCustomFood() async {
    final created = await Navigator.push<FoodItem>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            CustomFoodScreen(initialName: _searchCtrl.text.trim()),
      ),
    );
    if (created != null && mounted) {
      setState(() {
        _foods = [created, ...(_foods ?? const [])];
      });
      _selectFood(created);
    }
  }

  Future<void> _openCreateRecipe() async {
    final created = await Navigator.push<FoodItem>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            RecipeBuilderScreen(initialName: _searchCtrl.text.trim()),
      ),
    );
    if (created != null && mounted) {
      setState(() {
        _foods = [created, ...(_foods ?? const [])];
      });
      _selectFood(created);
    }
  }

  Future<void> _addPersonalPortion() async {
    if (_selected == null) return;
    final nameCtrl = TextEditingController();
    final gramsCtrl = TextEditingController();

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('My portion'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Portion name',
                hintText: 'e.g. my plate of rice',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: gramsCtrl,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Weight in grams (g)',
                hintText: 'e.g. 240',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (ok != true) return;
    final name = nameCtrl.text.trim();
    final grams = double.tryParse(gramsCtrl.text.trim()) ?? 0;
    if (name.isEmpty || grams <= 0) return;

    try {
      final createdPortion =
          await ApiClient.addPortion(_selected!.id, name, grams);
      final refreshed = await ApiClient.getFood(_selected!.id);
      if (!mounted) return;
      setState(() {
        _selected = refreshed;
        _foods = _foods
            ?.map((f) => f.id == refreshed.id ? refreshed : f)
            .toList();
        _selectedPortion = refreshed.portions.firstWhere(
          (p) => p.id == createdPortion.id,
          orElse: () => createdPortion,
        );
        _qtyCtrl.text = '1';
      });
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.message),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    }
  }

  void _confirm() {
    if (_selected == null) return;
    final qty = double.tryParse(_qtyCtrl.text.trim()) ?? 0;
    if (qty <= 0) return;

    final portion = _selectedPortion;
    final double gramWeight;
    if (portion != null) {
      final baseQty = portion.quantity > 0 ? portion.quantity : 1.0;
      gramWeight = (qty / baseQty) * portion.gramWeight;
    } else {
      gramWeight = qty;
    }

    final item = PickedFoodItem(
      food: _selected!,
      quantity: qty,
      portionId: portion?.id,
      portionName: portion?.name,
      unit: portion == null ? _unitCtrl.text.trim().toLowerCase() : null,
      gramWeight: gramWeight,
    );

    Navigator.pop(context, item);
  }

  @override
  Widget build(BuildContext context) {
    final portions = _selected?.portions ?? const <FoodPortion>[];
    final showCreateRecipe = widget.allowCreateRecipe && !widget.excludeRecipes;
    final extraRows = showCreateRecipe ? 2 : 1;

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
                Future.delayed(const Duration(milliseconds: 300), () {
                  if (mounted && _searchCtrl.text == q) {
                    _fetchFoods(q.trim());
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
                  itemCount: _foods!.length + extraRows,
                  itemBuilder: (_, i) {
                    if (i == _foods!.length) {
                      return ListTile(
                        dense: true,
                        leading: const Icon(Icons.add_circle_outline,
                            size: 18, color: Color(0xFF2563EB)),
                        title: const Text(
                          "Can't find it? Create a custom food",
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF2563EB),
                          ),
                        ),
                        onTap: _openCreateCustomFood,
                      );
                    }
                    if (showCreateRecipe && i == _foods!.length + 1) {
                      return ListTile(
                        dense: true,
                        leading: const Icon(Icons.soup_kitchen_outlined,
                            size: 18, color: Color(0xFF4F46E5)),
                        title: const Text(
                          "Can't find it? Create a recipe",
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF4F46E5),
                          ),
                        ),
                        onTap: _openCreateRecipe,
                      );
                    }
                    final f = _foods![i];
                    final isSelected = _selected?.id == f.id;
                    return ListTile(
                      dense: true,
                      selected: isSelected,
                      title: Text(f.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 13)),
                      onTap: () => _selectFood(f),
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
              const Text('Choose a serving size',
                  style: TextStyle(
                      fontSize: 12, color: Color(0xFF9CA3AF))),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  ChoiceChip(
                    label: const Text('Custom grams'),
                    selected: _selectedPortion == null,
                    onSelected: (_) => setState(() {
                      _selectedPortion = null;
                      _qtyCtrl.text = '100';
                    }),
                  ),
                  ...portions.map((p) {
                    final isSelected = _selectedPortion?.id == p.id;
                    return ChoiceChip(
                      label: Text(
                          '${p.name} (${p.gramWeight.toStringAsFixed(0)}g)'),
                      selected: isSelected,
                      onSelected: (_) => setState(() {
                        if (_selectedPortion == null) _qtyCtrl.text = '1';
                        _selectedPortion = p;
                      }),
                    );
                  }),
                  ActionChip(
                    avatar: const Icon(Icons.add, size: 14),
                    label: const Text('My portion...'),
                    onPressed: _addPersonalPortion,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _qtyCtrl,
                      decoration: InputDecoration(
                          labelText: _selectedPortion != null
                              ? 'Number of Servings'
                              : 'Grams'),
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
                      ],
                    ),
                  ),
                  if (_selectedPortion == null) ...[
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: _unitCtrl,
                        decoration:
                            const InputDecoration(labelText: 'Unit'),
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _confirm,
                child: Text(widget.confirmLabel),
              ),
            ],
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
