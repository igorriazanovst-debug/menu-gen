import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/cache/recipe_image_cache.dart';
import '../../../core/constants/food_groups.dart'; // MG_SWAPFREE
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/icon_label.dart'; // MG_NOOVERFLOW

/// Список крупных карточек блюд для выбранного приёма пищи.
/// Если в slot 1 элемент — карточка во всю ширину; если несколько — Column со
/// scroll'ом. Поля item — как из MenuItemSerializer:
/// { id, meal_type, recipe: {...RecipeListSerializer}, member_name, quantity }
// KBJU_DISPLAY: универсальное чтение nutrition (число ИЛИ {value,unit}) -> double?
double? nutritionValue(dynamic nutrition, String key) {
  if (nutrition is! Map) return null;
  final raw = nutrition[key];
  if (raw == null) return null;
  if (raw is num) return raw.toDouble();
  if (raw is Map) {
    final v = raw['value'];
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v.replaceAll(',', '.'));
  }
  if (raw is String) return double.tryParse(raw.replaceAll(',', '.'));
  return null;
}

String _fmtNum(double v) =>
    v == v.roundToDouble() ? v.round().toString() : v.toStringAsFixed(1);

/// KBJU_DISPLAY: сумма КБЖУ по списку MenuItem (учёт quantity).
class MealNutritionTotals {
  final double calories;
  final double proteins;
  final double fats;
  final double carbs;
  const MealNutritionTotals(this.calories, this.proteins, this.fats, this.carbs);

  bool get isEmpty => calories == 0 && proteins == 0 && fats == 0 && carbs == 0;

  static MealNutritionTotals fromItems(List<Map<String, dynamic>> items) {
    double cal = 0, pro = 0, fat = 0, carb = 0;
    for (final it in items) {
      final recipe = it['recipe'] is Map
          ? Map<String, dynamic>.from(it['recipe'] as Map)
          : const <String, dynamic>{};
      final n = recipe['nutrition'];
      final q = (it['quantity'] is num) ? (it['quantity'] as num).toDouble() : 1.0;
      cal += (nutritionValue(n, 'calories') ?? 0) * q;
      pro += (nutritionValue(n, 'proteins') ?? 0) * q;
      fat += (nutritionValue(n, 'fats') ?? 0) * q;
      carb += (nutritionValue(n, 'carbs') ?? 0) * q;
    }
    return MealNutritionTotals(cal, pro, fat, carb);
  }
}

/// KBJU_DISPLAY: компактная строка-итог КБЖУ (для приёма и для дня).
class NutritionTotalsBar extends StatelessWidget {
  final String title;
  final MealNutritionTotals totals;
  const NutritionTotalsBar({super.key, required this.title, required this.totals});

  @override
  Widget build(BuildContext context) {
    if (totals.isEmpty) return const SizedBox.shrink();
    final cs = context.cs;
    final tokens = context.tokens;
    Widget cell(String label, double v, String unit) => Expanded(
          child: Column(
            children: [
              Text('${_fmtNum(v)}$unit',
                  style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: cs.onSurface)),
              const SizedBox(height: 2),
              Text(label,
                  style: TextStyle(fontSize: 11, color: tokens.textSecondary)),
            ],
          ),
        );
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: tokens.surfaceAlt,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: tokens.textSecondary)),
          const SizedBox(height: 8),
          Row(
            children: [
              cell('ккал', totals.calories, ''),
              cell('Б', totals.proteins, ' г'),
              cell('Ж', totals.fats, ' г'),
              cell('У', totals.carbs, ' г'),
            ],
          ),
        ],
      ),
    );
  }
}

class MenuMealCarousel extends StatelessWidget {
  final String slotLabel;
  final List<Map<String, dynamic>> items;
  final ValueChanged<int> onRecipeTap;
  // Замена блюда (MG-402): нужны id меню, клиент и колбэк рефреша. Если не
  // переданы — кнопка «Заменить» не показывается.
  final int? menuId;
  final ApiClient? apiClient;
  final VoidCallback? onSwapped;

  const MenuMealCarousel({
    super.key,
    required this.slotLabel,
    required this.items,
    required this.onRecipeTap,
    this.menuId,
    this.apiClient,
    this.onSwapped,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.no_meals, size: 64, color: context.tokens.textSecondary),
              const SizedBox(height: 12),
              Text(
                'Нет блюд для «$slotLabel»',
                style: TextStyle(color: context.tokens.textSecondary, fontSize: 15),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    final totals = MealNutritionTotals.fromItems(items);  // KBJU_DISPLAY
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NutritionTotalsBar(title: 'Итог за приём', totals: totals),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 16),
            itemBuilder: (context, i) {
              final item = items[i];
              final recipe = item['recipe'] is Map
                  ? Map<String, dynamic>.from(item['recipe'] as Map)
                  : <String, dynamic>{};
              final recipeId = recipe['id'] as int?;
              final itemId = item['id'] as int?;
              final canSwap = menuId != null &&
                  apiClient != null &&
                  itemId != null &&
                  recipeId != null;
              return _RecipeBigCard(
                recipe: recipe,
                memberName: item['member_name'] as String?,
                onTap: recipeId == null ? null : () => onRecipeTap(recipeId),
                onReplace: !canSwap
                    ? null
                    : () => showSwapPicker(
                          context,
                          apiClient: apiClient!,
                          menuId: menuId!,
                          itemId: itemId!,
                          currentRecipeId: recipeId!,
                          foodGroup: recipe['food_group'] as String?,
                          onSwapped: onSwapped,
                        ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _RecipeBigCard extends StatelessWidget {
  final Map<String, dynamic> recipe;
  final String? memberName;
  final VoidCallback? onTap;
  final VoidCallback? onReplace;

  const _RecipeBigCard({
    required this.recipe,
    required this.memberName,
    required this.onTap,
    this.onReplace,
  });

  String? get _imageUrl => recipe['image_url'] as String?;
  String get _title => (recipe['title'] as String?) ?? '';
  String? get _cookTime => recipe['cook_time'] as String?;

  String? get _calories {
    // KBJU_DISPLAY: nutrition['calories'] может быть числом или {value,unit}.
    final v = nutritionValue(recipe['nutrition'], 'calories');
    if (v == null) return null;
    return '${_fmtNum(v)} ккал';
  }

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final radius = BorderRadius.circular(20);
    return Material(
      color: cs.surface,
      borderRadius: radius,
      elevation: 2,
      child: InkWell(
        onTap: onTap,
        borderRadius: radius,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AspectRatio(
              aspectRatio: 16 / 10,
              child: ClipRRect(
                borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
                child: _imageUrl == null || _imageUrl!.isEmpty
                    ? Container(
                        color: context.tokens.surfaceAlt,
                        child: Icon(Icons.restaurant,
                            size: 64, color: context.tokens.textSecondary),
                      )
                    : CachedNetworkImage(
                        imageUrl: _imageUrl!,
                        cacheManager: RecipeImageCache.instance,
                        fit: BoxFit.cover,
                        placeholder: (_, __) => Container(
                          color: context.tokens.surfaceAlt,
                          child: const Center(
                              child: CircularProgressIndicator(strokeWidth: 2)),
                        ),
                        errorWidget: (_, __, ___) => Container(
                          color: context.tokens.surfaceAlt,
                          child: Icon(Icons.restaurant,
                              size: 64, color: context.tokens.textSecondary),
                        ),
                      ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _title,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: cs.onSurface,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 12,
                    runSpacing: 4,
                    children: [
                      if (_cookTime != null && _cookTime!.isNotEmpty)
                        _MetaChip(icon: Icons.access_time, text: _cookTime!),
                      if (_calories != null)
                        _MetaChip(icon: Icons.local_fire_department, text: _calories!),
                      if (memberName != null && memberName!.isNotEmpty)
                        _MetaChip(icon: Icons.person_outline, text: memberName!),
                    ],
                  ),
                  if (onReplace != null) ...[
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        onPressed: onReplace,
                        icon: const Icon(Icons.swap_horiz, size: 18),
                        label: const Text('Заменить'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: cs.primary,
                          side: BorderSide(color: cs.primary.withOpacity(0.5)),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// MG-402 / MG_SWAPFREE: лист-пикер замены блюда. Тянет кандидатов из
/// `/recipes/` (по умолчанию — той же food_group, исключая текущий), при выборе
/// PATCH-ит `/menu/<m>/items/<i>/` {recipe_id}. Фильтр по группе снимается
/// галочкой: раньше он был жёстким и рецепт, найденный в разделе «Рецепты»,
/// в замене «пропадал». Бэкенд теперь такую замену разрешает и лишь
/// предупреждает (food_group_warning) — его и показываем. После успеха
/// закрывает лист и дёргает [onSwapped] для обновления меню.
void showSwapPicker(
  BuildContext context, {
  required ApiClient apiClient,
  required int menuId,
  required int itemId,
  required int currentRecipeId,
  required String? foodGroup,
  VoidCallback? onSwapped,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _SwapPicker(
      apiClient: apiClient,
      menuId: menuId,
      itemId: itemId,
      currentRecipeId: currentRecipeId,
      foodGroup: foodGroup,
      onSwapped: onSwapped,
    ),
  );
}

class _SwapPicker extends StatefulWidget {
  final ApiClient apiClient;
  final int menuId;
  final int itemId;
  final int currentRecipeId;
  final String? foodGroup;
  final VoidCallback? onSwapped;

  const _SwapPicker({
    required this.apiClient,
    required this.menuId,
    required this.itemId,
    required this.currentRecipeId,
    required this.foodGroup,
    required this.onSwapped,
  });

  @override
  State<_SwapPicker> createState() => _SwapPickerState();
}

class _SwapPickerState extends State<_SwapPicker> {
  final _searchCtrl = TextEditingController();
  List<Map<String, dynamic>> _items = const [];
  bool _loading = false;
  bool _swapping = false;
  String? _error;
  int _reqSeq = 0;
  /// MG_SWAPFREE: показывать только блюда той же пищевой группы. Включено по
  /// умолчанию — так меню остаётся сбалансированным, но фильтр можно снять.
  bool _sameGroupOnly = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final seq = ++_reqSeq;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final params = <String, dynamic>{'page_size': 25};
      final q = _searchCtrl.text.trim();
      if (q.isNotEmpty) params['search'] = q;
      if (_sameGroupOnly && widget.foodGroup != null && widget.foodGroup!.isNotEmpty) {
        params['food_group'] = widget.foodGroup;
      }
      final r = await widget.apiClient.get('/recipes/', params: params);
      if (seq != _reqSeq || !mounted) return;
      final results = (r is Map ? (r['results'] as List? ?? const []) : const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .where((m) => m['id'] != widget.currentRecipeId)
          .toList();
      setState(() {
        _items = results;
        _loading = false;
      });
    } catch (e) {
      if (seq != _reqSeq || !mounted) return;
      setState(() {
        _loading = false;
        _error = e is ApiException ? e.message : 'Не удалось загрузить рецепты';
      });
    }
  }

  Future<void> _pick(int recipeId) async {
    if (_swapping) return;
    setState(() {
      _swapping = true;
      _error = null;
    });
    try {
      final resp = await widget.apiClient.patch(
        '/menu/${widget.menuId}/items/${widget.itemId}/',
        data: {'recipe_id': recipeId},
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      // MG_SWAPFREE: замена состоялась, но баланс меню сместился — сообщаем.
      final data = resp is Map ? Map<String, dynamic>.from(resp) : const {};
      if (data['food_group_warning'] == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Блюдо заменено на другую пищевую группу — баланс меню изменится.'),
          ),
        );
      }
      widget.onSwapped?.call();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _swapping = false;
        _error = e is ApiException ? e.message : 'Ошибка замены';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final h = MediaQuery.of(context).size.height * 0.75;
    return Container(
      height: h,
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 10),
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: context.tokens.border,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 8, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Заменить блюдо',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      color: cs.onSurface,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: TextField(
              controller: _searchCtrl,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _load(),
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: 'Поиск рецепта…',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchCtrl.clear();
                          _load();
                        },
                      )
                    : null,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                contentPadding: const EdgeInsets.symmetric(vertical: 0),
              ),
            ),
          ),
          if (widget.foodGroup != null && widget.foodGroup!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: CheckboxListTile(
                dense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                controlAffinity: ListTileControlAffinity.leading,
                value: _sameGroupOnly,
                onChanged: (v) {
                  setState(() => _sameGroupOnly = v ?? true);
                  _load();
                },
                title: Text(
                  'Только группа «${foodGroupLabel(widget.foodGroup)}»',
                  style: const TextStyle(fontSize: 13),
                ),
              ),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              child: Text(_error!,
                  style: const TextStyle(color: Colors.red, fontSize: 13)),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _items.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 32),
                          child: Text(
                            _sameGroupOnly && (widget.foodGroup ?? '').isNotEmpty
                                ? 'Ничего не найдено. Снимите галочку выше, чтобы искать среди всех рецептов.'
                                : 'Ничего не найдено',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: context.tokens.textSecondary),
                          ),
                        ),
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
                        itemCount: _items.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final r = _items[i];
                          final id = r['id'] as int?;
                          final img = r['image_url'] as String?;
                          return ListTile(
                            leading: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: SizedBox(
                                width: 48,
                                height: 48,
                                child: (img == null || img.isEmpty)
                                    ? Container(
                                        color: context.tokens.surfaceAlt,
                                        child: Icon(Icons.restaurant,
                                            color: context.tokens.textSecondary),
                                      )
                                    : CachedNetworkImage(
                                        imageUrl: img,
                                        cacheManager: RecipeImageCache.instance,
                                        fit: BoxFit.cover,
                                        errorWidget: (_, __, ___) => Container(
                                          color: context.tokens.surfaceAlt,
                                          child: Icon(Icons.restaurant,
                                              color: context.tokens.textSecondary),
                                        ),
                                      ),
                              ),
                            ),
                            title: Text(
                              (r['title'] as String?) ?? '',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            trailing: _swapping
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.chevron_right),
                            onTap: (id == null || _swapping) ? null : () => _pick(id),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String text;
  const _MetaChip({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    // MG_NOOVERFLOW: подпись сжимается, а не выдавливает строку наружу.
    return IconLabel(
      icon: icon,
      text: text,
      iconColor: context.cs.secondary,
      style: TextStyle(fontSize: 13, color: context.tokens.textSecondary),
    );
  }
}
