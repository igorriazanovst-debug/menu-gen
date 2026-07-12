import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/cache/recipe_image_cache.dart';
import '../../../core/theme/app_theme.dart';

class RecipeCard extends StatelessWidget {
  final Map<String, dynamic> recipe;
  final VoidCallback onTap;
  final VoidCallback? onFavoriteToggle;
  const RecipeCard({
    super.key,
    required this.recipe,
    required this.onTap,
    this.onFavoriteToggle,
  });

  String get _title => (recipe['title'] as String?) ?? '';
  String? get _imageUrl => recipe['image_url'] as String?;
  String? get _cookTime => recipe['cook_time'] as String?;
  bool get _isFavorite => (recipe['is_favorite'] as bool?) ?? false;
  bool get _isDisliked => (recipe['is_disliked'] as bool?) ?? false;
  int? get _fridgeMatch {
    final v = recipe['fridge_match_count'];
    if (v is int) return v;
    if (v is num) return v.toInt();
    return null;
  }

  String? get _kcal {
    final n = recipe['nutrition'];
    if (n is Map) {
      final c = n['calories'];
      if (c is Map) {
        final v = c['value'];
        if (v != null) return '${v} ккал';
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    return Material(
      color: cs.surface,
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                AspectRatio(
                  aspectRatio: 16 / 11,
                  child: _imageUrl != null && _imageUrl!.isNotEmpty
                      ? CachedNetworkImage(
                          imageUrl: _imageUrl!,
                          cacheManager: RecipeImageCache.instance,
                          fit: BoxFit.cover,
                          placeholder: (_, __) => Container(color: tokens.surfaceAlt),
                          errorWidget: (_, __, ___) => _placeholder(context),
                        )
                      : _placeholder(context),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: cs.onSurface,
                          height: 1.2,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          if (_cookTime != null && _cookTime!.isNotEmpty)
                            _meta(context, Icons.access_time, _cookTime!),
                          if (_kcal != null) _meta(context, Icons.local_fire_department, _kcal!),
                          if (_fridgeMatch != null && _fridgeMatch! > 0)
                            _badge('🧺 $_fridgeMatch'),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            // Favorite indicator (corner)
            if (_isFavorite || _isDisliked || onFavoriteToggle != null)
              Positioned(
                top: 6,
                right: 6,
                child: GestureDetector(
                  onTap: onFavoriteToggle,
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.9),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      _isFavorite
                          ? Icons.favorite
                          : (_isDisliked
                              ? Icons.heart_broken
                              : Icons.favorite_border),
                      size: 18,
                      color: _isFavorite
                          ? cs.primary
                          : tokens.textSecondary,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _placeholder(BuildContext context) => Container(
        color: context.tokens.surfaceAlt,
        child: Center(
          child: Icon(Icons.restaurant_menu,
              size: 48, color: context.tokens.textSecondary),
        ),
      );

  Widget _meta(BuildContext context, IconData icon, String text) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: context.tokens.textSecondary),
          const SizedBox(width: 3),
          Text(
            text,
            style: TextStyle(fontSize: 11, color: context.tokens.textSecondary),
          ),
        ],
      );

  Widget _badge(String text) => Builder(
        builder: (context) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: context.cs.secondary.withOpacity(0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            text,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
          ),
        ),
      );
}
