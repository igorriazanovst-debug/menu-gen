import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import 'recipe_image_cache.dart';

/// Фоновый прекэш фото всех рецептов — чтобы раздел «Рецепты» работал без сети.
///
/// Проходит по всем страницам `/recipes/`, собирает `image_url` и скачивает их
/// в [RecipeImageCache], пропуская уже закэшированные. Скачивание идёт с
/// ограниченной конкуренцией и не блокирует UI; сетевые ошибки глушатся
/// (best-effort). Запуск троттлится: не чаще раза в сутки на устройство.
class MediaPrefetchService {
  MediaPrefetchService._();

  static final MediaPrefetchService instance = MediaPrefetchService._();

  static const String _kLastRunKey = 'menugen.mediaPrefetch.lastRunMs';
  static const Duration _minInterval = Duration(hours: 24);

  bool _running = false;

  /// Дёргается фоном при открытии списка рецептов. [force] игнорирует троттлинг.
  Future<void> prefetchAllRecipeImages(
    ApiClient api, {
    bool force = false,
    int maxPages = 200,
  }) async {
    if (_running) return;
    if (!force && !await _due()) return;
    _running = true;
    try {
      final urls = <String>[];
      for (var page = 1; page <= maxPages; page++) {
        final data = await _asMap(api.get('/recipes/', params: {'page': page}));
        if (data == null) break;
        for (final item in (data['results'] as List? ?? const [])) {
          if (item is Map) {
            final u = (item['image_url'] as String?)?.trim();
            if (u != null && u.isNotEmpty) urls.add(u);
          }
        }
        if (data['next'] == null) break;
      }
      await _downloadAll(urls);
      await _markRun();
    } catch (_) {
      // best-effort: не мешаем работе приложения
    } finally {
      _running = false;
    }
  }

  Future<Map<String, dynamic>?> _asMap(Future<dynamic> f) async {
    try {
      final r = await f;
      if (r is Map) return Map<String, dynamic>.from(r);
      final d = r?.data; // на случай, если клиент вернёт Response
      return d is Map ? Map<String, dynamic>.from(d) : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _downloadAll(List<String> urls, {int concurrency = 4}) async {
    var idx = 0;
    Future<void> worker() async {
      while (idx < urls.length) {
        final u = urls[idx++];
        try {
          final cached = await RecipeImageCache.instance.getFileFromCache(u);
          if (cached == null) {
            await RecipeImageCache.instance.downloadFile(u);
          }
        } catch (_) {
          // пропускаем битую/недоступную ссылку
        }
      }
    }

    await Future.wait(List.generate(concurrency, (_) => worker()));
  }

  Future<bool> _due() async {
    try {
      final p = await SharedPreferences.getInstance();
      final last = p.getInt(_kLastRunKey) ?? 0;
      final elapsed = DateTime.now().millisecondsSinceEpoch - last;
      return elapsed >= _minInterval.inMilliseconds;
    } catch (_) {
      return true;
    }
  }

  Future<void> _markRun() async {
    try {
      final p = await SharedPreferences.getInstance();
      await p.setInt(_kLastRunKey, DateTime.now().millisecondsSinceEpoch);
    } catch (_) {}
  }
}
