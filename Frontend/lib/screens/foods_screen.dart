import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../theme.dart';
import '../main.dart' show TabActivatedNotifier;
import 'custom_food_screen.dart';
import 'recipe_builder_screen.dart';

// ─────────────────────────────────────────
// FOODS SCREEN — local library + USDA search
// ─────────────────────────────────────────

class FoodsScreen extends StatefulWidget {
  final TabActivatedNotifier? tabNotifier;
  const FoodsScreen({super.key, this.tabNotifier});

  @override
  State<FoodsScreen> createState() => _FoodsScreenState();
}

class _FoodsScreenState extends State<FoodsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Foods'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [Tab(text: 'My Library'), Tab(text: 'USDA Search')],
        ),
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          _LocalFoodsTab(tabNotifier: widget.tabNotifier),
          const _UsdaSearchTab(),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────
// LOCAL FOODS TAB
// ─────────────────────────────────────────

class _LocalFoodsTab extends StatefulWidget {
  final TabActivatedNotifier? tabNotifier;
  const _LocalFoodsTab({this.tabNotifier});
  @override
  State<_LocalFoodsTab> createState() => _LocalFoodsTabState();
}

class _LocalFoodsTabState extends State<_LocalFoodsTab> {
  final _searchCtrl = TextEditingController();
  late Future<List<FoodItem>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.getFoods();
    ApiClient.addDataListener(_onDataChanged, {DataScope.foods});
    widget.tabNotifier?.addListener(_onTabActivated);
  }

  @override
  void dispose() {
    ApiClient.removeDataListener(_onDataChanged);
    widget.tabNotifier?.removeListener(_onTabActivated);
    _searchCtrl.dispose();
    super.dispose();
  }

  void _onDataChanged() {
    if (mounted) {
      final q = _searchCtrl.text.trim();
      setState(() {
        _future = q.isEmpty ? ApiClient.getFoods() : ApiClient.getFoods(q);
      });
    }
  }

  void _onTabActivated() {
    if (mounted) {
      final q = _searchCtrl.text.trim();
      setState(() {
        _future = q.isEmpty ? ApiClient.getFoods() : ApiClient.getFoods(q);
      });
    }
  }

  void _search(String query) {
    setState(() {
      if (query.trim().isEmpty) {
        _future = ApiClient.getFoods();
      } else {
        _future = ApiClient.getFoods(query.trim());
      }
    });
  }

  Future<void> _handleRefresh() async {
    _search(_searchCtrl.text);
    await _future;
  }

  Future<void> _openNewFood() async {
    final created = await Navigator.push<FoodItem>(
      context,
      MaterialPageRoute(builder: (_) => const CustomFoodScreen()),
    );
    if (created != null && mounted) {
      _search(_searchCtrl.text);
    }
  }

  Future<void> _openNewRecipe() async {
    final created = await Navigator.push<FoodItem>(
      context,
      MaterialPageRoute(builder: (_) => const RecipeBuilderScreen()),
    );
    if (created != null && mounted) {
      _search(_searchCtrl.text);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: 'Search local foods...',
                    prefixIcon: const Icon(Icons.search, size: 20),
                    suffixIcon: _searchCtrl.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            onPressed: () {
                              _searchCtrl.clear();
                              _search('');
                            })
                        : null,
                  ),
                  onChanged: _search,
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: _openNewFood,
                icon: const Icon(Icons.add, size: 16),
                label: const Text('New food'),
              ),
              const SizedBox(width: 6),
              OutlinedButton.icon(
                onPressed: _openNewRecipe,
                icon: const Icon(Icons.soup_kitchen_outlined, size: 16),
                label: const Text('New recipe'),
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<FoodItem>>(
            future: _future,
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const LoadingView();
              }
              if (snap.hasError) {
                return ErrorView(
                    message: snap.error.toString(),
                    onRetry: () => _search(_searchCtrl.text));
              }
              final foods = snap.data ?? [];
              if (foods.isEmpty) {
                return RefreshIndicator(
                  onRefresh: _handleRefresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: const [
                      SizedBox(height: 80),
                      EmptyView(
                          message: 'No foods found. Import some from USDA tab.',
                          icon: Icons.no_food_outlined),
                    ],
                  ),
                );
              }
              return RefreshIndicator(
                onRefresh: _handleRefresh,
                child: ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  itemCount: foods.length,
                  itemBuilder: (_, i) => _FoodListTile(food: foods[i]),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _FoodListTile extends StatelessWidget {
  final FoodItem food;
  const _FoodListTile({required this.food});

  @override
  Widget build(BuildContext context) {
    final badgeLabel = food.kind == 'custom'
        ? 'Custom'
        : food.kind == 'recipe'
            ? 'Recipe'
            : null;
    return ListTile(
      title: Row(
        children: [
          Expanded(
            child: Text(
              food.name,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 14),
            ),
          ),
          if (food.avoided) ...[
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Text(
                'Avoid',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFFDC2626),
                ),
              ),
            ),
          ],
          if (badgeLabel != null) ...[
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0xFFEEF2FF),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                badgeLabel,
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF4F46E5),
                ),
              ),
            ),
          ],
        ],
      ),
      subtitle: Text(
          '${food.caloriesPer100g.toStringAsFixed(0)} kcal / 100g',
          style: const TextStyle(fontSize: 12)),
      trailing: const Icon(Icons.chevron_right, size: 18),
      onTap: () => _showFoodDetail(context, food),
    );
  }

  void _showFoodDetail(
      BuildContext context, FoodItem food) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) => _FoodDetailSheet(food: food),
    );
  }
}

class _FoodDetailSheet extends StatelessWidget {
  final FoodItem food;
  const _FoodDetailSheet({required this.food});

  Future<void> _edit(BuildContext context) async {
    Navigator.pop(context);
    if (food.kind == 'recipe') {
      await Navigator.push<FoodItem>(
        context,
        MaterialPageRoute(
          builder: (_) => RecipeBuilderScreen(existingFoodId: food.id),
        ),
      );
    } else {
      await Navigator.push<FoodItem>(
        context,
        MaterialPageRoute(
          builder: (_) => CustomFoodScreen(existingFood: food),
        ),
      );
    }
  }

  Future<void> _delete(BuildContext context) async {
    try {
      await ApiClient.deleteCustomFood(food.id);
      if (context.mounted) Navigator.pop(context);
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
  }

  @override
  Widget build(BuildContext context) {
    final portions = food.portions;
    final badgeLabel = food.kind == 'custom'
        ? 'Custom'
        : food.kind == 'recipe'
            ? 'Recipe'
            : null;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.55,
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
              Expanded(
                child: Text(food.name,
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w600)),
              ),
              if (badgeLabel != null)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEEF2FF),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    badgeLabel,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF4F46E5),
                    ),
                  ),
                ),
              if (food.kind == 'custom' || food.kind == 'recipe') ...[
                IconButton(
                  icon: const Icon(Icons.edit_outlined, size: 18),
                  tooltip: 'Edit',
                  onPressed: () => _edit(context),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline,
                      size: 18, color: Color(0xFFEF4444)),
                  tooltip: 'Delete',
                  onPressed: () => _delete(context),
                ),
              ],
            ],
          ),
          if (food.usdaDataType != null) ...[
            const SizedBox(height: 4),
            Text(food.usdaDataType!,
                style: const TextStyle(
                    fontSize: 12, color: Color(0xFF9CA3AF))),
          ],
          const SizedBox(height: 16),
          const Text('Per 100g',
              style: TextStyle(
                  fontSize: 12,
                  color: Color(0xFF9CA3AF),
                  fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          NutrientRow(
            calories: food.caloriesPer100g,
            protein: food.proteinPer100g,
            carbs: food.carbsPer100g,
            fat: food.fatPer100g,
          ),
          if (portions.isNotEmpty) ...[
            const SizedBox(height: 20),
            const Text('Serving sizes',
                style: TextStyle(
                    fontSize: 12,
                    color: Color(0xFF9CA3AF),
                    fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            ...portions.map((p) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: InfoTile(
                    label: p.name,
                    value:
                        '${p.gramWeight > 0 ? p.gramWeight.toStringAsFixed(0) : '?'}g',
                  ),
                )),
          ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────
// USDA SEARCH TAB
// ─────────────────────────────────────────

class _UsdaSearchTab extends StatefulWidget {
  const _UsdaSearchTab();
  @override
  State<_UsdaSearchTab> createState() => _UsdaSearchTabState();
}

class _UsdaSearchTabState extends State<_UsdaSearchTab> {
  final _ctrl = TextEditingController();
  List<dynamic>? _results;
  bool _loading = false;
  String? _error;
  final Set<int> _importing = {};

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final q = _ctrl.text.trim();
    if (q.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Enter at least 2 characters')));
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await ApiClient.searchUsda(q);
      setState(() {
        _results = r;
        _loading = false;
      });
    } on ApiException catch (e) {
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _import(Map<String, dynamic> item) async {
    final fdcId = item['fdc_id'] as int;
    setState(() => _importing.add(fdcId));
    try {
      await ApiClient.importUsda(fdcId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Imported "${item['name']}"'),
            backgroundColor: Colors.green.shade700));
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(e.message),
            backgroundColor: Colors.red.shade700));
      }
    } finally {
      if (mounted) setState(() => _importing.remove(fdcId));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  decoration: const InputDecoration(
                    hintText: 'Search USDA database...',
                    prefixIcon: Icon(Icons.search, size: 20),
                  ),
                  onSubmitted: (_) => _search(),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _loading ? null : _search,
                style: FilledButton.styleFrom(
                    minimumSize: const Size(64, 44)),
                child: _loading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Text('Go'),
              ),
            ],
          ),
        ),
        if (_error != null)
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Text(_error!,
                style: const TextStyle(color: Colors.red, fontSize: 13)),
          ),
        Expanded(
          child: _results == null
              ? const Center(
                  child: Text('Search USDA FoodData Central above.',
                      style: TextStyle(color: Color(0xFF9CA3AF))))
              : _results!.isEmpty
                  ? const EmptyView(message: 'No results found.')
                  : ListView.builder(
                      itemCount: _results!.length,
                      itemBuilder: (_, i) {
                        final item =
                            _results![i] as Map<String, dynamic>;
                        final fdcId = item['fdc_id'] as int;
                        final isImporting = _importing.contains(fdcId);
                        return ListTile(
                          title: Text(item['name'] as String? ?? '',
                              style: const TextStyle(fontSize: 14)),
                          subtitle: Text(
                              'FDC: $fdcId · ${item['data_type'] ?? ''}',
                              style: const TextStyle(fontSize: 12)),
                          trailing: isImporting
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2))
                              : TextButton(
                                  onPressed: () => _import(item),
                                  child: const Text('Import',
                                      style:
                                          TextStyle(fontSize: 13))),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
