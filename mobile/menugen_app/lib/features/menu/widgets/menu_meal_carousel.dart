import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/cache/recipe_image_cache.dart';
import '../../../core/theme/app_theme.dart';

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

  const MenuMealCarousel({
    super.key,
    required this.slotLabel,
    required this.items,
    required this.onRecipeTap,
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
              return _RecipeBigCard(
                recipe: recipe,
                memberName: item['member_name'] as String?,
                onTap: recipeId == null ? null : () => onRecipeTap(recipeId),
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

  const _RecipeBigCard({
    required this.recipe,
    required this.memberName,
    required this.onTap,
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
                ],
              ),
            ),
          ],
        ),
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
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: context.cs.secondary),
        const SizedBox(width: 4),
        Text(text, style: TextStyle(fontSize: 13, color: context.tokens.textSecondary)),
      ],
    );
  }
}
