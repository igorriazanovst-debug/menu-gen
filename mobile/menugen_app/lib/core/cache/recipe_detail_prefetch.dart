import '../api/api_client.dart';

/// Прогрев кэша полными деталями рецептов из меню — чтобы блюда открывались
/// офлайн.
///
/// Меню-деталь (`/menu/<id>/`) содержит лишь «списочные» данные рецептов (без
/// шагов); полный рецепт тянется по `/recipes/<id>/` при открытии. Этот сервис
/// заранее (при загрузке меню, только онлайн) запрашивает `/recipes/<id>/` для
/// всех рецептов меню — [ApiClient] здесь кэширующий, поэтому ответы оседают в
/// офлайн-кэше и блюда потом открываются без сети.
class RecipeDetailPrefetch {
  RecipeDetailPrefetch._();

  static final RecipeDetailPrefetch instance = RecipeDetailPrefetch._();

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
    final ids = _recipeIds(menu).where((id) => !_done.contains(id)).toList();
    if (ids.isEmpty) return;
    // помечаем сразу, чтобы параллельные вызовы не дублировали работу
    _done.addAll(ids);
    if (_running) {
      // уже идёт прогон — новые id подхватит текущий воркер-цикл
    }
    _running = true;
    try {
      await _downloadAll(api, ids);
    } finally {
      _running = false;
    }
  }

  Future<void> _downloadAll(ApiClient api, List<int> ids, {int concurrency = 3}) async {
    var idx = 0;
    Future<void> worker() async {
      while (idx < ids.length) {
        final id = ids[idx++];
        try {
          await api.get('/recipes/$id/');
        } catch (_) {
          // офлайн/ошибка — снимаем метку, попробуем при следующем заходе
          _done.remove(id);
        }
      }
    }

    await Future.wait(List.generate(concurrency, (_) => worker()));
  }
}
