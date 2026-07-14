import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/cache/media_prefetch_service.dart'; // офлайн-прекэш фото
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T10
import '../../../core/theme/app_theme.dart'; // MG_SKIN
import '../bloc/recipes_bloc.dart';
import '../models/recipe_filters.dart';
import '../widgets/filter_sheet.dart';
import '../widgets/recipe_card.dart';

class RecipesScreen extends StatefulWidget {
  final ApiClient apiClient;
  const RecipesScreen({super.key, required this.apiClient});

  @override
  State<RecipesScreen> createState() => _RecipesScreenState();
}

class _RecipesScreenState extends State<RecipesScreen> {
  final _searchCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  static const int _pageSize = 20;

  RecipeFilters _filters = const RecipeFilters();
  int _page = 1; // текущая (базовая) страница пагинатора
  int _loadedThrough = 1; // до какой страницы догружено скроллом
  int _total = 0; // всего рецептов (count) — для нумерации
  bool _hasMore = true;
  bool _loadingMore = false;
  bool _paging = false; // грузится новая базовая страница (reload/jump)
  final List<Map<String, dynamic>> _recipes = [];

  int get _totalPages => _total <= 0 ? 1 : ((_total + _pageSize - 1) ~/ _pageSize);

  /// Cached fridge item names (lowercased).
  List<String> _fridgeNames = const [];

  /// Cached countries list from /recipes/countries/.
  List<String> _countries = const [];

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
    _fetchSidecars();
    _reload();
    _prefetchMediaForOffline();
  }

  /// Фоновый прекэш фото всех рецептов — чтобы раздел работал без сети.
  /// Запускаем только онлайн; сервис сам троттлит (не чаще раза в сутки).
  void _prefetchMediaForOffline() {
    if (context.read<ConnectivityCubit>().state == ConnectivityStatus.offline) {
      return;
    }
    // fire-and-forget: не блокирует UI, ошибки глушатся внутри сервиса.
    MediaPrefetchService.instance.prefetchAllRecipeImages(widget.apiClient);
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _fetchSidecars() async {
    // Fridge names — optional (may 403 if no premium).
    try {
      final r = await widget.apiClient.get('/fridge/');
      final results = (r is Map ? (r['results'] as List? ?? []) : [])
          .whereType<Map>()
          .map((m) => (m['name'] as String? ?? '').trim())
          .where((s) => s.isNotEmpty)
          .toList();
      if (mounted) setState(() => _fridgeNames = results);
    } catch (_) {/* no premium / no fridge — silently ignore */}

    try {
      final r = await widget.apiClient.get('/recipes/countries/');
      if (r is List) {
        final list = r.whereType<String>().toList();
        if (mounted) setState(() => _countries = list);
      }
    } catch (_) {}
  }

  void _onScroll() {
    if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 240 &&
        !_loadingMore &&
        _hasMore) {
      _loadNextPage();
    }
  }

  void _reload() {
    setState(() {
      _page = 1;
      _loadedThrough = 1;
      _hasMore = true;
      _paging = true;
      _recipes.clear();
    });
    _dispatch(1);
  }

  void _loadNextPage() {
    setState(() {
      _loadingMore = true;
      _loadedThrough += 1;
    });
    _dispatch(_loadedThrough);
  }

  /// Переход на конкретную страницу (зеркало веба): сбрасывает список к странице
  /// n, дальше скролл догружает n+1, n+2… как обычно.
  void _jumpToPage(int n) {
    final np = n.clamp(1, _totalPages).toInt();
    if (np == _page && _recipes.isNotEmpty) return;
    setState(() {
      _page = np;
      _loadedThrough = np;
      _hasMore = true;
      _paging = true;
      _recipes.clear();
    });
    if (_scrollCtrl.hasClients) _scrollCtrl.jumpTo(0);
    _dispatch(np);
  }

  void _dispatch(int page) {
    context.read<RecipesBloc>().add(
          RecipesFilterChanged(
            filters: _filters,
            search: _searchCtrl.text.trim(),
            page: page,
            fridgeNames: _fridgeNames,
          ),
        );
  }

  Future<void> _openFilters() async {
    final result = await FilterSheet.show(
      context,
      initial: _filters,
      countries: _countries,
      hasFridge: _fridgeNames.isNotEmpty,
    );
    if (result != null) {
      setState(() => _filters = result);
      _reload();
    }
  }

  void _onFavorite(Map<String, dynamic> r) async {
    final id = r['id'] as int?;
    if (id == null) return;
    final isFav = (r['is_favorite'] as bool?) ?? false;
    final isDis = (r['is_disliked'] as bool?) ?? false;

    // 3-state cycle: none → favorite → disliked → none
    bool? next;
    bool newFav, newDis;
    if (!isFav && !isDis) {
      next = true;
      newFav = true;
      newDis = false;
    } else if (isFav) {
      next = false;
      newFav = false;
      newDis = true;
    } else {
      next = null;
      newFav = false;
      newDis = false;
    }

    // optimistic UI update
    setState(() {
      r['is_favorite'] = newFav;
      r['is_disliked'] = newDis;
    });

    context.read<RecipesBloc>().add(
          RecipesFavoriteToggled(recipeId: id, isFavorite: next),
        );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Рецепты'),
        actions: [
          Stack(
            alignment: Alignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.tune),
                tooltip: 'Фильтры',
                onPressed: _openFilters,
              ),
              if (_filters.activeCount > 0)
                Positioned(
                  right: 6,
                  top: 6,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: const BoxDecoration(
                      color: Colors.red,
                      shape: BoxShape.circle,
                    ),
                    child: Text(
                      '${_filters.activeCount}',
                      style: const TextStyle(color: Colors.white, fontSize: 10),
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
      body: BlocListener<RecipesBloc, RecipesState>(
        listener: (context, state) {
          if (state is RecipesPageLoaded) {
            setState(() {
              _recipes.addAll(state.recipes);
              _hasMore = state.hasMore;
              _total = state.total;
              _loadingMore = false;
              _paging = false;
            });
          } else if (state is RecipesError) {
            setState(() {
              _loadingMore = false;
              _paging = false;
            });
            // MG_T10: offline -> only the global banner, no error snackbar.
            if (context.read<ConnectivityCubit>().state !=
                ConnectivityStatus.offline) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(state.message)),
              );
            }
          }
        },
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
              child: TextField(
                controller: _searchCtrl,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  hintText: 'Поиск рецептов...',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: _searchCtrl.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _searchCtrl.clear();
                            _reload();
                          },
                        )
                      : null,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  contentPadding: const EdgeInsets.symmetric(vertical: 0),
                ),
                onChanged: (_) => setState(() {}),
                onSubmitted: (_) => _reload(),
              ),
            ),
            if (_filters.activeCount > 0)
              SizedBox(
                height: 36,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  children: _activeChips(),
                ),
              ),
            if (_totalPages > 1) _buildPaginationBar(),
            Expanded(
              child: BlocBuilder<RecipesBloc, RecipesState>(
                builder: (context, state) {
                  if (_recipes.isEmpty && (state is RecipesLoading || _paging)) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (_recipes.isEmpty) {
                    return Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.menu_book,
                              size: 56, color: context.tokens.textSecondary),
                          const SizedBox(height: 12),
                          const Text('Рецептов не найдено'),
                          if (_filters.activeCount > 0) ...[
                            const SizedBox(height: 8),
                            TextButton(
                              onPressed: () {
                                setState(() => _filters = const RecipeFilters());
                                _reload();
                              },
                              child: const Text('Сбросить фильтры'),
                            ),
                          ],
                        ],
                      ),
                    );
                  }
                  return RefreshIndicator(
                    onRefresh: () async => _reload(),
                    child: GridView.builder(
                      controller: _scrollCtrl,
                      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        crossAxisSpacing: 10,
                        mainAxisSpacing: 10,
                        childAspectRatio: 0.78,
                      ),
                      itemCount: _recipes.length + (_hasMore ? 1 : 0),
                      itemBuilder: (_, i) {
                        if (i == _recipes.length) {
                          return const Center(child: CircularProgressIndicator());
                        }
                        final r = _recipes[i];
                        return RecipeCard(
                          recipe: r,
                          onTap: () => context.push('/recipes/${r['id']}'),
                          onFavoriteToggle: () => _onFavorite(r),
                        );
                      },
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Нумерованная пагинация (зеркало веба) ──────────────────────────────────
  // Список страниц: первая/последняя всегда, окно вокруг текущей, «…» на
  // разрывах: 1 … 4 5 [6] 7 8 … 20.
  List<Object> _pageWindow(int current, int totalPages) {
    if (totalPages <= 7) {
      return [for (var i = 1; i <= totalPages; i++) i];
    }
    final out = <Object>[1];
    final from = (current - 1) < 2 ? 2 : current - 1;
    final to = (current + 1) > totalPages - 1 ? totalPages - 1 : current + 1;
    if (from > 2) out.add('…');
    for (var p = from; p <= to; p++) out.add(p);
    if (to < totalPages - 1) out.add('…');
    out.add(totalPages);
    return out;
  }

  Widget _buildPaginationBar() {
    final cs = context.cs;
    final tp = _totalPages;
    final cur = _page;

    Widget numBtn(int p) {
      final active = p == cur;
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 3),
        child: SizedBox(
          height: 34,
          child: active
              ? FilledButton(
                  onPressed: () {},
                  style: FilledButton.styleFrom(
                    backgroundColor: cs.primary,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    minimumSize: const Size(40, 34),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text('$p'),
                )
              : OutlinedButton(
                  onPressed: () => _jumpToPage(p),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    minimumSize: const Size(40, 34),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text('$p'),
                ),
        ),
      );
    }

    return Container(
      height: 50,
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left),
            tooltip: 'Назад',
            onPressed: cur > 1 ? () => _jumpToPage(cur - 1) : null,
          ),
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final w in _pageWindow(cur, tp))
                    w is int
                        ? numBtn(w)
                        : Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 4),
                            child: Text('…',
                                style: TextStyle(color: context.tokens.textSecondary)),
                          ),
                ],
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.chevron_right),
            tooltip: 'Вперёд',
            onPressed: cur < tp ? () => _jumpToPage(cur + 1) : null,
          ),
          IconButton(
            icon: const Icon(Icons.more_horiz),
            tooltip: 'Перейти на страницу',
            onPressed: () => _promptJump(tp),
          ),
        ],
      ),
    );
  }

  Future<void> _promptJump(int totalPages) async {
    final ctrl = TextEditingController();
    final n = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Перейти на страницу'),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(hintText: '1–$totalPages'),
          onSubmitted: (v) => Navigator.of(ctx).pop(int.tryParse(v.trim())),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Отмена'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(int.tryParse(ctrl.text.trim())),
            child: const Text('Перейти'),
          ),
        ],
      ),
    );
    if (n != null) _jumpToPage(n);
  }

  List<Widget> _activeChips() {
    final out = <Widget>[];
    void add(String label, VoidCallback onClear) {
      out.add(Padding(
        padding: const EdgeInsets.only(right: 6),
        child: InputChip(
          label: Text(label),
          onDeleted: () {
            onClear();
            _reload();
          },
        ),
      ));
    }

    if (_filters.mealType != null) {
      add(_mealLabel(_filters.mealType!),
          () => setState(() => _filters = _filters.copyWith(mealType: null)));
    }
    if (_filters.dishType != null) {
      add(_filters.dishType!,
          () => setState(() => _filters = _filters.copyWith(dishType: null)));
    }
    if (_filters.foodGroup != null) {
      add(_foodLabel(_filters.foodGroup!),
          () => setState(() => _filters = _filters.copyWith(foodGroup: null)));
    }
    if (_filters.manualIngredients.isNotEmpty) {
      add('Ингр.: ${_filters.manualIngredients.length}',
          () => setState(() => _filters = _filters.copyWith(manualIngredients: const [])));
    }
    if (_filters.useFridge) {
      add('🧺 Холодильник',
          () => setState(() => _filters = _filters.copyWith(useFridge: false)));
    }
    if (_filters.favorite == true) {
      add('❤ Любимые',
          () => setState(() => _filters = _filters.copyWith(favorite: null)));
    } else if (_filters.favorite == false) {
      add('💔 Нелюбимые',
          () => setState(() => _filters = _filters.copyWith(favorite: null)));
    }
    if (_filters.country != null && _filters.country!.isNotEmpty) {
      add(_filters.country!,
          () => setState(() => _filters = _filters.copyWith(country: null)));
    }
    if (_filters.excludeAllergens) {
      add('Без аллергенов',
          () => setState(() => _filters = _filters.copyWith(excludeAllergens: false)));
    }
    return out;
  }

  String _mealLabel(String t) {
    switch (t) {
      case 'breakfast': return 'Завтрак';
      case 'lunch':     return 'Обед';
      case 'dinner':    return 'Ужин';
      case 'snack':     return 'Перекус';
      default:          return t;
    }
  }

  String _foodLabel(String t) {
    switch (t) {
      case 'grain':     return 'Зерновые';
      case 'protein':   return 'Белки';
      case 'vegetable': return 'Овощи';
      case 'fruit':     return 'Фрукты';
      case 'dairy':     return 'Молочные';
      case 'oil':       return 'Масла/жиры';
      case 'other':     return 'Прочее';
      default:          return t;
    }
  }
}
