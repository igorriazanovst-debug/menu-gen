// Кэширующий декоратор поверх ApiClient (DioApiClient).
//
// GET: сначала сеть; при успехе кладём ответ в HttpCacheStore и возвращаем.
//      При офлайне (ApiException.isNetwork) отдаём последний сохранённый ответ,
//      если он есть (раздел работает без сети). Нет кэша — пробрасываем ошибку.
//
// POST/PUT/PATCH/DELETE: при офлайне и если путь — «пользовательская активность»
//      (см. OfflineMutationQueue.queueable), кладём операцию в персистентную
//      очередь и возвращаем оптимистичный эхо-ответ (блоки активности не читают
//      тело ответа — делают reload/оптимистичный UI). Иначе пробрасываем ошибку.
import 'api_client.dart';
import 'api_exception.dart';
import '../cache/http_cache_store.dart';
import '../sync/offline_mutation_queue.dart';

class CachingApiClient implements ApiClient {
  final ApiClient inner;
  final HttpCacheStore cache;
  final OfflineMutationQueue queue;

  CachingApiClient({
    required this.inner,
    required this.cache,
    required this.queue,
  });

  bool _isOffline(Object e) => e is ApiException && e.isNetwork;

  /// Когда для GET допустимо отдать кэш: офлайн ИЛИ rate-limit (429) — в обоих
  /// случаях показать сохранённое лучше, чем ошибку.
  bool _canServeCache(Object e) =>
      e is ApiException && (e.isNetwork || e.isThrottled);

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? params}) async {
    final key = cache.keyFor(path, params);
    try {
      final data = await inner.get(path, params: params);
      await cache.save(key, data);
      return data;
    } catch (e) {
      if (_canServeCache(e)) {
        final cached = cache.read(key);
        if (cached != null) return cached.data;
      }
      rethrow;
    }
  }

  Future<dynamic> _write(
    String method,
    String path,
    dynamic data,
    Future<dynamic> Function() call,
  ) async {
    try {
      return await call();
    } catch (e) {
      if (_isOffline(e) && OfflineMutationQueue.queueable(path)) {
        await queue.enqueue(method, path, data);
        // Оптимистичный ответ: эхо тела (блоки активности его не используют).
        return data ?? <String, dynamic>{};
      }
      rethrow;
    }
  }

  @override
  Future<dynamic> post(String path, {Map<String, dynamic>? data}) =>
      _write('POST', path, data, () => inner.post(path, data: data));

  @override
  Future<dynamic> put(String path, {Map<String, dynamic>? data}) =>
      _write('PUT', path, data, () => inner.put(path, data: data));

  @override
  Future<dynamic> patch(String path, {Map<String, dynamic>? data}) =>
      _write('PATCH', path, data, () => inner.patch(path, data: data));

  @override
  Future<dynamic> delete(String path) =>
      _write('DELETE', path, null, () => inner.delete(path));
}
