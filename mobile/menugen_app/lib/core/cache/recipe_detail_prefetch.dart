import 'dart:async';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// Прогрев кэша полными деталями рецептов из меню — чтобы блюда открывались
/// офлайн.
///
/// Меню-деталь (`/menu/<id>/`) содержит лишь «списочные» данные рецептов (без
/// шагов); полный рецепт тянется по `/recipes/<id>/` при открытии. Этот сервис
/// заранее (при загрузке меню, только онлайн) запрашивает `/recipes/<id>/` для
/// всех рецептов меню — [ApiClient] здесь кэширующий, поэтому ответы оседают в
/// офлайн-кэше и блюда потом открываются без сети.
///
/// ВЕЖЛИВО к rate-limit (100 запросов/мин на пользователя): запросы идут строго
/// последовательно с паузой между ними, со стартовой задержкой (пропускаем
/// вперёд запросы самого экрана), и при 429 (throttle) прогрев немедленно
/// прекращается, уступая бюджет пользователю. Недокачанное подхватится при
/// следующем заходе в меню.
class RecipeDetailPrefetch {
  RecipeDetailPrefetch._();

  static final RecipeDetailPrefetch instance = RecipeDetailPrefetch._();

  /// Задержка перед стартом — чтобы запросы самого экрана прошли первыми.
  static const Duration _startDelay = Duration(seconds: 3);

  /// Пауза между фоновыми запросами (≈30/мин — оставляет запас пользователю).
  static const Duration _gap = Duration(milliseconds: 2000);

  /// Рецепты, уже прогретые в этой сессии — чтобы не дёргать повторно.
  final Set<int> _done = {};
  bool _running = false;

  Set<int> _recipeIds(Map<String, dynamic>? menu) {
    final ids = <int>{};
    final items = menu?['items'];
    if (items is List) {
      for (final it in items) {
        if (it is Map) {
          final r = it['recipe'];
          if (r is Map && r['id'] is int) ids.add(r['id'] as int);
        }
      }
    }
    return ids;
  }

  /// Фоновый прогрев деталей рецептов активного меню. Вызывать только онлайн.
  Future<void> prefetchMenu(ApiClient api, Map<String, dynamic>? menu) async {
    if (_running) return; // один прогон за раз — не устраиваем всплеск
    final ids = _recipeIds(menu).where((id) => !_done.contains(id)).toList();
    if (ids.isEmpty) return;
    _running = true;
    try {
      await Future.delayed(_startDelay);
      for (final id in ids) {
        try {
          await api.get('/recipes/$id/');
          _done.add(id);
        } on ApiException catch (e) {
          if (e.isThrottled || e.isNetwork) break; // уступаем/офлайн — стоп
          _done.add(id); // прочие ошибки (404 и т.п.) — не повторяем
        } catch (_) {
          // неизвестная ошибка — не зацикливаемся, помечаем как обработанный
          _done.add(id);
        }
        await Future.delayed(_gap);
      }
    } finally {
      _running = false;
    }
  }
}
