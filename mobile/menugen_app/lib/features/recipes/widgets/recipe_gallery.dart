// MG_GALLERY: галерея фото рецепта с листанием тапом по краям изображения.
//
// Раскладка тапов повторяет веб: левая треть — предыдущее фото, правая треть —
// следующее, середина — открыть во весь экран. Свайп тоже работает: под
// капотом PageView.
//
// При одном фото зоны листания не создаются — тап по всей площади открывает
// просмотр, как было до галереи.
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/cache/recipe_image_cache.dart';
import '../../../core/theme/app_theme.dart';

/// Одно фото галереи: адрес и необязательная подпись.
class RecipePhoto {
  final String url;
  final String? caption;

  const RecipePhoto(this.url, {this.caption});
}

/// Собирает фото рецепта: обложка первой, затем галерея из админки.
///
/// Дубли отбрасываем — обложку иногда дублируют и в галерее.
List<RecipePhoto> collectRecipePhotos(Map<String, dynamic>? recipe) {
  if (recipe == null) return const [];

  final photos = <RecipePhoto>[];
  final seen = <String>{};

  void add(Object? rawUrl, [Object? rawCaption]) {
    final url = (rawUrl is String ? rawUrl : '').trim();
    if (url.isEmpty || !seen.add(url)) return;
    final caption = (rawCaption is String ? rawCaption : '').trim();
    photos.add(RecipePhoto(url, caption: caption.isEmpty ? null : caption));
  }

  add(recipe['image_url']);
  for (final item in (recipe['gallery'] as List?) ?? const []) {
    if (item is Map) add(item['url'], item['caption']);
  }
  return photos;
}

class RecipeGallery extends StatefulWidget {
  final List<RecipePhoto> photos;

  /// Открыть фото во весь экран (тап по середине).
  final void Function(RecipePhoto photo)? onZoom;

  const RecipeGallery({super.key, required this.photos, this.onZoom});

  @override
  State<RecipeGallery> createState() => _RecipeGalleryState();
}

class _RecipeGalleryState extends State<RecipeGallery> {
  late final PageController _controller = PageController();
  int _index = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _go(int delta) {
    final next = (_index + delta + widget.photos.length) % widget.photos.length;
    _controller.animateToPage(
      next,
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final photos = widget.photos;
    if (photos.isEmpty) {
      return Container(
        color: tokens.surfaceAlt,
        child: Icon(Icons.restaurant, size: 64, color: tokens.textSecondary),
      );
    }

    final many = photos.length > 1;
    final current = photos[_index.clamp(0, photos.length - 1)];

    return Stack(
      fit: StackFit.expand,
      children: [
        PageView.builder(
          controller: _controller,
          itemCount: photos.length,
          onPageChanged: (i) => setState(() => _index = i),
          itemBuilder: (_, i) => CachedNetworkImage(
            imageUrl: photos[i].url,
            cacheManager: RecipeImageCache.instance,
            fit: BoxFit.cover,
            placeholder: (_, __) => Container(color: tokens.surfaceAlt),
            errorWidget: (_, __, ___) => Container(
              color: tokens.surfaceAlt,
              child: Icon(Icons.restaurant, size: 64, color: tokens.textSecondary),
            ),
          ),
        ),

        // Зоны тапа поверх картинки. Середина шире краёв: попасть в неё проще,
        // а зум — самое частое действие.
        Row(
          children: [
            if (many)
              Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.translucent,
                  onTap: () => _go(-1),
                  child: const SizedBox.expand(),
                ),
              ),
            Expanded(
              flex: many ? 2 : 4,
              child: GestureDetector(
                behavior: HitTestBehavior.translucent,
                onTap: () => widget.onZoom?.call(current),
                child: const SizedBox.expand(),
              ),
            ),
            if (many)
              Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.translucent,
                  onTap: () => _go(1),
                  child: const SizedBox.expand(),
                ),
              ),
          ],
        ),

        if (many) ...[
          Positioned(
            top: 8,
            right: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '${_index + 1} / ${photos.length}',
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: current.caption == null ? 8 : 34,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < photos.length; i++)
                  Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: i == _index ? Colors.white : Colors.white.withValues(alpha: 0.5),
                    ),
                  ),
              ],
            ),
          ),
        ],

        if (current.caption != null)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              color: Colors.black.withValues(alpha: 0.45),
              child: Text(
                current.caption!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          ),
      ],
    );
  }
}
