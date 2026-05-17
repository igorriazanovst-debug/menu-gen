import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Список крупных карточек блюд для выбранного приёма пищи.
/// Если в slot 1 элемент — карточка во всю ширину; если несколько — Column со
/// scroll'ом. Поля item — как из MenuItemSerializer:
/// { id, meal_type, recipe: {...RecipeListSerializer}, member_name, quantity }
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
              Icon(Icons.no_meals, size: 64, color: Colors.grey.shade400),
              const SizedBox(height: 12),
              Text(
                'Нет блюд для «$slotLabel»',
                style: TextStyle(color: Colors.grey.shade600, fontSize: 15),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
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
    final n = recipe['nutrition'];
    if (n is Map) {
      final cal = n['calories'];
      if (cal is Map && cal['value'] != null) {
        return '${cal['value']} ккал';
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(20);
    return Material(
      color: AppColors.surface,
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
                        color: AppColors.background,
                        child: Icon(Icons.restaurant,
                            size: 64, color: Colors.grey.shade400),
                      )
                    : CachedNetworkImage(
                        imageUrl: _imageUrl!,
                        fit: BoxFit.cover,
                        placeholder: (_, __) => Container(
                          color: AppColors.background,
                          child: const Center(
                              child: CircularProgressIndicator(strokeWidth: 2)),
                        ),
                        errorWidget: (_, __, ___) => Container(
                          color: AppColors.background,
                          child: Icon(Icons.restaurant,
                              size: 64, color: Colors.grey.shade400),
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
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
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
        Icon(icon, size: 16, color: AppColors.secondary),
        const SizedBox(width: 4),
        Text(text, style: TextStyle(fontSize: 13, color: Colors.grey.shade700)),
      ],
    );
  }
}
