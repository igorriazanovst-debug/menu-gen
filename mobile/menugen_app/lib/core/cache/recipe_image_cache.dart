import 'package:flutter_cache_manager/flutter_cache_manager.dart';

/// Персистентный кэш фото рецептов с увеличенными лимитами.
///
/// Стандартный `DefaultCacheManager` хранит лишь ~200 объектов и 30 дней —
/// этого мало, чтобы весь каталог рецептов (сотни фото) оставался доступным
/// офлайн. Здесь до 5000 объектов и 90 дней, отдельный ключ хранилища.
///
/// Тем же менеджером пользуются все `CachedNetworkImage` рецептов и фоновый
/// [MediaPrefetchService], поэтому предзагруженные и просмотренные фото
/// попадают в одно хранилище и находятся при работе без сети.
class RecipeImageCache {
  RecipeImageCache._();

  static const String key = 'recipeImageCache';

  static final CacheManager instance = CacheManager(
    Config(
      key,
      stalePeriod: const Duration(days: 90),
      maxNrOfCacheObjects: 5000,
    ),
  );
}
