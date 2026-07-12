import 'dart:async';

import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'recipe_image_cache.dart';

/// Фоновый прекэш фото всех рецептов — чтобы раздел «Рецепты» работал без сети.
///
/// Проходит по всем страницам `/recipes/`, собирает `image_url` и скачивает их
/// в [RecipeImageCache], пропуская уже закэшированные. Скачивание идёт с
/// ограниченной конкуренцией и не блокирует UI; сетевые ошибки глушатся
/// (best-effort). Запуск троттлится: не чаще раза в сутки на устройство.
///
/// ВЕЖЛИВО к rate-limit (100 запросов/мин на пользователя): обход страниц идёт
/// с паузой между запросами и стартовой задержкой; при 429 (throttle) обход
/// прекращается и день НЕ засчитывается — повторим при следующем заходе.
class MediaPrefetchService {
  MediaPrefetchService._();

  static final MediaPrefetchService instance = MediaPrefetchService._();

  static const String _kLastRunKey = 'menugen.mediaPrefetch.lastRunMs';
  static const Duration _minInterval = Duration(hours: 24);

  /// Стартовая задержка — пропускаем вперёд запросы самого экрана.
  static const Duration _startDelay = Duration(seconds: 4);

  /// Пауза между обходами страниц (API), чтобы не выесть бюджет запросов.
  static const Duration _gap = Duration(milliseconds: 2000);

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
      await Future.delayed(_startDelay);
      final urls = <String>[];
      var throttled = false;
      for (var page = 1; page <= maxPages; page++) {
        Map<String, dynamic>? data;
        try {
          final r = await api.get('/recipes/', params: {'page': page});
          data = r is Map ? Map<String, dynamic>.from(r) : null;
        } on ApiException catch (e) {
          if (e.isThrottled || e.isNetwork) throttled = true;
          break; // уступаем бюджет пользователю / офлайн / прочее
        } catch (_) {
          break;
        }
        if (data == null) break;
        for (final item in (data['results'] as List? ?? const [])) {
          if (item is Map) {
            final u = (item['image_url'] as String?)?.trim();
            if (u != null && u.isNotEmpty) urls.add(u);
          }
        }
        if (data['next'] == null) break;
        await Future.delayed(_gap);
      }
      await _downloadAll(urls);
      if (!throttled) await _markRun(); // при throttle не помечаем — повторим
    } catch (_) {
      // best-effort: не мешаем работе приложения
    } finally {
      _running = false;
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
