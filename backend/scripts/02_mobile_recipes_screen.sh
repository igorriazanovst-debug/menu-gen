#!/usr/bin/env bash
# Mobile patch: RecipesScreen redesign with filters + favorite + grid
set -eu

ROOT="/opt/menugen"
cd "$ROOT"

TS=$(date +%Y%m%d_%H%M%S)
BAK="$ROOT/backups/recipes_mobile_${TS}"
mkdir -p "$BAK"
APP="$ROOT/mobile/menugen_app"

echo "=== [1/6] backup mobile recipes files ==="
mkdir -p "$BAK/recipes/screens" "$BAK/recipes/bloc"
cp "$APP/lib/features/recipes/screens/recipes_screen.dart"        "$BAK/recipes/screens/"
cp "$APP/lib/features/recipes/screens/recipe_detail_screen.dart"  "$BAK/recipes/screens/"
cp "$APP/lib/features/recipes/bloc/recipes_bloc.dart"             "$BAK/recipes/bloc/"
echo "backup → $BAK"

echo
echo "=== [2/6] write models: recipe_filters.dart ==="
mkdir -p "$APP/lib/features/recipes/models"
cat > "$APP/lib/features/recipes/models/recipe_filters.dart" <<'DARTEOF'
import 'package:equatable/equatable.dart';

/// Aggregated filter state for the Recipes screen.
/// All fields default to "no filter". Combine any subset.
class RecipeFilters extends Equatable {
  /// breakfast / lunch / dinner / snack — uses backend ?meal_type=.
  final String? mealType;

  /// «Суп» / «Салат» / «Выпечка» / «Десерт» / «Напиток» — uses ?dish_type=.
  final String? dishType;

  /// food_group: grain / protein / vegetable / fruit / dairy / oil / other.
  final String? foodGroup;

  /// Country (icontains).
  final String? country;

  /// Set of ingredient names entered by the user manually.
  final List<String> manualIngredients;

  /// AND/OR mode for [manualIngredients] (uses ingredients_all vs ingredients_any).
  final bool manualIngredientsAll;

  /// If true, send ?fridge_ingredients=<csv of fridge item names>
  /// (server ranks by match count).
  final bool useFridge;

  /// favorite=true/false; null = no filter.
  final bool? favorite;

  /// If true, send ?exclude_allergens=true.
  final bool excludeAllergens;

  const RecipeFilters({
    this.mealType,
    this.dishType,
    this.foodGroup,
    this.country,
    this.manualIngredients = const [],
    this.manualIngredientsAll = true,
    this.useFridge = false,
    this.favorite,
    this.excludeAllergens = false,
  });

  bool get isEmpty =>
      mealType == null &&
      dishType == null &&
      foodGroup == null &&
      (country == null || country!.isEmpty) &&
      manualIngredients.isEmpty &&
      !useFridge &&
      favorite == null &&
      !excludeAllergens;

  int get activeCount {
    var n = 0;
    if (mealType != null) n++;
    if (dishType != null) n++;
    if (foodGroup != null) n++;
    if (country != null && country!.isNotEmpty) n++;
    if (manualIngredients.isNotEmpty) n++;
    if (useFridge) n++;
    if (favorite != null) n++;
    if (excludeAllergens) n++;
    return n;
  }

  RecipeFilters copyWith({
    Object? mealType = _sentinel,
    Object? dishType = _sentinel,
    Object? foodGroup = _sentinel,
    Object? country = _sentinel,
    List<String>? manualIngredients,
    bool? manualIngredientsAll,
    bool? useFridge,
    Object? favorite = _sentinel,
    bool? excludeAllergens,
  }) {
    return RecipeFilters(
      mealType: identical(mealType, _sentinel) ? this.mealType : mealType as String?,
      dishType: identical(dishType, _sentinel) ? this.dishType : dishType as String?,
      foodGroup: identical(foodGroup, _sentinel) ? this.foodGroup : foodGroup as String?,
      country: identical(country, _sentinel) ? this.country : country as String?,
      manualIngredients: manualIngredients ?? this.manualIngredients,
      manualIngredientsAll: manualIngredientsAll ?? this.manualIngredientsAll,
      useFridge: useFridge ?? this.useFridge,
      favorite: identical(favorite, _sentinel) ? this.favorite : favorite as bool?,
      excludeAllergens: excludeAllergens ?? this.excludeAllergens,
    );
  }

  /// Convert filters to the query params for the backend /recipes/ list.
  /// [fridgeNames] is the list of fridge item names; required if [useFridge].
  Map<String, dynamic> toQueryParams({
    String? search,
    int page = 1,
    List<String>? fridgeNames,
  }) {
    final p = <String, dynamic>{'page': page};
    if (search != null && search.isNotEmpty) p['search'] = search;
    if (mealType != null) p['meal_type'] = mealType;
    if (dishType != null) p['dish_type'] = dishType;
    if (foodGroup != null) p['food_group'] = foodGroup;
    if (country != null && country!.isNotEmpty) p['country'] = country;
    if (manualIngredients.isNotEmpty) {
      final csv = manualIngredients.join(',');
      p[manualIngredientsAll ? 'ingredients_all' : 'ingredients_any'] = csv;
    }
    if (useFridge && fridgeNames != null && fridgeNames.isNotEmpty) {
      p['fridge_ingredients'] = fridgeNames.join(',');
    }
    if (favorite != null) p['favorite'] = favorite! ? 'true' : 'false';
    if (excludeAllergens) p['exclude_allergens'] = 'true';
    return p;
  }

  @override
  List<Object?> get props => [
        mealType,
        dishType,
        foodGroup,
        country,
        manualIngredients,
        manualIngredientsAll,
        useFridge,
        favorite,
        excludeAllergens,
      ];

  static const _sentinel = Object();
}
DARTEOF

echo
echo "=== [3/6] rewrite recipes_bloc.dart (filters + favorite events) ==="
cat > "$APP/lib/features/recipes/bloc/recipes_bloc.dart" <<'DARTEOF'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../models/recipe_filters.dart';

// ─── Events ────────────────────────────────────────────────────────────────

abstract class RecipesEvent extends Equatable {
  const RecipesEvent();
  @override
  List<Object?> get props => [];
}

class RecipesLoadRequested extends RecipesEvent {
  const RecipesLoadRequested();
}

class RecipesSearchRequested extends RecipesEvent {
  final String query;
  const RecipesSearchRequested(this.query);
  @override
  List<Object?> get props => [query];
}

class RecipesPageRequested extends RecipesEvent {
  final Map<String, dynamic> params;
  const RecipesPageRequested({required this.params});
  @override
  List<Object?> get props => [params];
}

/// MG-recipes-screen: load page using a [RecipeFilters] object.
class RecipesFilterChanged extends RecipesEvent {
  final RecipeFilters filters;
  final String search;
  final int page;
  final List<String> fridgeNames;
  const RecipesFilterChanged({
    required this.filters,
    this.search = '',
    this.page = 1,
    this.fridgeNames = const [],
  });
  @override
  List<Object?> get props => [filters, search, page, fridgeNames];
}

class RecipesFavoriteToggled extends RecipesEvent {
  final int recipeId;

  /// `true`  → mark as favorite (POST favorite=true)
  /// `false` → mark as disliked (POST favorite=false)
  /// `null`  → clear (DELETE)
  final bool? isFavorite;
  const RecipesFavoriteToggled({required this.recipeId, required this.isFavorite});
  @override
  List<Object?> get props => [recipeId, isFavorite];
}

// ─── States ────────────────────────────────────────────────────────────────

abstract class RecipesState extends Equatable {
  const RecipesState();
  @override
  List<Object?> get props => [];
}

class RecipesLoading extends RecipesState {
  const RecipesLoading();
}

class RecipesLoaded extends RecipesState {
  final List<Map<String, dynamic>> recipes;
  const RecipesLoaded({required this.recipes});
  @override
  List<Object?> get props => [recipes];
}

class RecipesPageLoaded extends RecipesState {
  final List<Map<String, dynamic>> recipes;
  final bool hasMore;
  const RecipesPageLoaded({required this.recipes, required this.hasMore});
  @override
  List<Object?> get props => [recipes, hasMore];
}

class RecipesError extends RecipesState {
  final String message;
  const RecipesError(this.message);
  @override
  List<Object?> get props => [message];
}

// ─── Bloc ──────────────────────────────────────────────────────────────────

class RecipesBloc extends Bloc<RecipesEvent, RecipesState> {
  final ApiClient apiClient;
  final AppDatabase db;

  RecipesBloc({required this.apiClient, required this.db}) : super(const RecipesLoading()) {
    on<RecipesLoadRequested>(_onLoad);
    on<RecipesSearchRequested>(_onSearch);
    on<RecipesPageRequested>(_onPage);
    on<RecipesFilterChanged>(_onFilter);
    on<RecipesFavoriteToggled>(_onFavorite);
  }

  dynamic _data(dynamic r) {
    try {
      return r.data;
    } catch (_) {
      return r;
    }
  }

  List<Map<String, dynamic>> _results(dynamic d) => d is Map
      ? (d['results'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList()
      : <Map<String, dynamic>>[];

  bool _hasMore(dynamic d) => d is Map ? d['next'] != null : false;

  Future<void> _onLoad(RecipesLoadRequested e, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final r = await apiClient.get('/recipes/');
      emit(RecipesLoaded(recipes: _results(_data(r))));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }

  Future<void> _onSearch(RecipesSearchRequested e, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final r = await apiClient.get('/recipes/', params: {'search': e.query});
      emit(RecipesLoaded(recipes: _results(_data(r))));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }

  Future<void> _onPage(RecipesPageRequested e, Emitter<RecipesState> emit) async {
    try {
      final r = await apiClient.get('/recipes/', params: e.params);
      final d = _data(r);
      emit(RecipesPageLoaded(recipes: _results(d), hasMore: _hasMore(d)));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }

  Future<void> _onFilter(RecipesFilterChanged e, Emitter<RecipesState> emit) async {
    try {
      final params = e.filters.toQueryParams(
        search: e.search,
        page: e.page,
        fridgeNames: e.fridgeNames,
      );
      final r = await apiClient.get('/recipes/', params: params);
      final d = _data(r);
      emit(RecipesPageLoaded(recipes: _results(d), hasMore: _hasMore(d)));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }

  Future<void> _onFavorite(RecipesFavoriteToggled e, Emitter<RecipesState> emit) async {
    try {
      if (e.isFavorite == null) {
        await apiClient.delete('/recipes/${e.recipeId}/favorite/');
      } else {
        await apiClient.post(
          '/recipes/${e.recipeId}/favorite/',
          data: {'is_favorite': e.isFavorite},
        );
      }
    } catch (_) {
      // best-effort; UI uses optimistic update
    }
  }

  String _msg(Object err) => err is ApiException ? err.message : err.toString();
}
DARTEOF

echo
echo "=== [4/6] write filter_sheet.dart ==="
mkdir -p "$APP/lib/features/recipes/widgets"
cat > "$APP/lib/features/recipes/widgets/filter_sheet.dart" <<'DARTEOF'
import 'package:flutter/material.dart';

import '../models/recipe_filters.dart';

/// Bottom sheet that lets the user toggle and configure recipe filters.
/// All filter blocks are independent; any combination is allowed.
class FilterSheet extends StatefulWidget {
  final RecipeFilters initial;
  final List<String> availableCountries;
  final bool hasFridge;

  const FilterSheet({
    super.key,
    required this.initial,
    this.availableCountries = const [],
    this.hasFridge = false,
  });

  static Future<RecipeFilters?> show(
    BuildContext context, {
    required RecipeFilters initial,
    List<String> countries = const [],
    bool hasFridge = false,
  }) {
    return showModalBottomSheet<RecipeFilters>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => FilterSheet(
        initial: initial,
        availableCountries: countries,
        hasFridge: hasFridge,
      ),
    );
  }

  @override
  State<FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends State<FilterSheet> {
  late RecipeFilters _f;

  // local controllers
  final _ingCtrl = TextEditingController();

  // labels
  static const _mealTypes = <String, String>{
    'breakfast': 'Завтрак',
    'lunch': 'Обед',
    'dinner': 'Ужин',
    'snack': 'Перекус',
  };
  static const _dishTypes = <String>[
    'Суп', 'Салат', 'Выпечка', 'Десерт', 'Напиток', 'Закуска', 'Соус', 'Гарнир',
  ];
  static const _foodGroups = <String, String>{
    'grain': 'Зерновые',
    'protein': 'Белки',
    'vegetable': 'Овощи',
    'fruit': 'Фрукты',
    'dairy': 'Молочные',
    'oil': 'Масла/жиры',
    'other': 'Прочее',
  };

  @override
  void initState() {
    super.initState();
    _f = widget.initial;
  }

  @override
  void dispose() {
    _ingCtrl.dispose();
    super.dispose();
  }

  void _addIngredient() {
    final t = _ingCtrl.text.trim();
    if (t.isEmpty) return;
    final next = List<String>.from(_f.manualIngredients);
    if (!next.any((s) => s.toLowerCase() == t.toLowerCase())) {
      next.add(t);
    }
    setState(() {
      _f = _f.copyWith(manualIngredients: next);
      _ingCtrl.clear();
    });
  }

  void _removeIngredient(String name) {
    final next = List<String>.from(_f.manualIngredients)..remove(name);
    setState(() => _f = _f.copyWith(manualIngredients: next));
  }

  @override
  Widget build(BuildContext context) {
    final viewInsets = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: viewInsets),
      child: SafeArea(
        top: false,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.92,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _handle(),
              _topBar(context),
              const Divider(height: 1),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                  children: [
                    _section(
                      title: '1. Приём пищи',
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _mealTypes.entries.map((e) {
                          final selected = _f.mealType == e.key;
                          return ChoiceChip(
                            label: Text(e.value),
                            selected: selected,
                            onSelected: (_) => setState(
                              () => _f = _f.copyWith(mealType: selected ? null : e.key),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    _section(
                      title: '2. Вид блюда',
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _dishTypes.map((d) {
                          final selected = _f.dishType == d;
                          return ChoiceChip(
                            label: Text(d),
                            selected: selected,
                            onSelected: (_) => setState(
                              () => _f = _f.copyWith(dishType: selected ? null : d),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    _section(
                      title: '3. Основной продукт',
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _foodGroups.entries.map((e) {
                          final selected = _f.foodGroup == e.key;
                          return ChoiceChip(
                            label: Text(e.value),
                            selected: selected,
                            onSelected: (_) => setState(
                              () => _f = _f.copyWith(foodGroup: selected ? null : e.key),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    _section(
                      title: '4. Набор ингредиентов',
                      subtitle:
                          'Введите ингредиенты, которые должны быть в рецепте.',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _ingCtrl,
                                  textInputAction: TextInputAction.done,
                                  onSubmitted: (_) => _addIngredient(),
                                  decoration: const InputDecoration(
                                    hintText: 'Например, курица',
                                    isDense: true,
                                    border: OutlineInputBorder(),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              IconButton.filled(
                                onPressed: _addIngredient,
                                icon: const Icon(Icons.add),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          if (_f.manualIngredients.isNotEmpty)
                            Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: _f.manualIngredients
                                  .map(
                                    (n) => InputChip(
                                      label: Text(n),
                                      onDeleted: () => _removeIngredient(n),
                                    ),
                                  )
                                  .toList(),
                            ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              const Text('Совпадение: '),
                              const SizedBox(width: 8),
                              SegmentedButton<bool>(
                                segments: const [
                                  ButtonSegment(value: true, label: Text('Все')),
                                  ButtonSegment(value: false, label: Text('Любой')),
                                ],
                                selected: {_f.manualIngredientsAll},
                                onSelectionChanged: (s) => setState(
                                  () => _f = _f.copyWith(manualIngredientsAll: s.first),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    _section(
                      title: '5. Из холодильника',
                      subtitle: widget.hasFridge
                          ? 'Сортировать рецепты по числу совпадений с содержимым холодильника.'
                          : 'Холодильник пуст или недоступен.',
                      child: SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Использовать содержимое холодильника'),
                        value: _f.useFridge,
                        onChanged: widget.hasFridge
                            ? (v) => setState(() => _f = _f.copyWith(useFridge: v))
                            : null,
                      ),
                    ),
                    _section(
                      title: '6. Любимое / Нелюбимое',
                      child: SegmentedButton<int>(
                        segments: const [
                          ButtonSegment(value: 0, label: Text('Все')),
                          ButtonSegment(value: 1, label: Text('Любимые')),
                          ButtonSegment(value: 2, label: Text('Нелюбимые')),
                        ],
                        selected: {
                          _f.favorite == null ? 0 : (_f.favorite! ? 1 : 2),
                        },
                        onSelectionChanged: (s) {
                          final v = s.first;
                          setState(() {
                            _f = _f.copyWith(
                              favorite: v == 0 ? null : (v == 1 ? true : false),
                            );
                          });
                        },
                      ),
                    ),
                    _section(
                      title: '7. Страна',
                      child: widget.availableCountries.isEmpty
                          ? TextField(
                              controller: TextEditingController(text: _f.country ?? ''),
                              decoration: const InputDecoration(
                                hintText: 'Например, Италия',
                                isDense: true,
                                border: OutlineInputBorder(),
                              ),
                              onChanged: (v) => _f = _f.copyWith(country: v),
                            )
                          : Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: widget.availableCountries.map((c) {
                                final selected = _f.country == c;
                                return ChoiceChip(
                                  label: Text(c),
                                  selected: selected,
                                  onSelected: (_) => setState(
                                    () => _f = _f.copyWith(country: selected ? null : c),
                                  ),
                                );
                              }).toList(),
                            ),
                    ),
                    _section(
                      title: '8. Аллергены',
                      child: SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Исключить мои аллергены'),
                        value: _f.excludeAllergens,
                        onChanged: (v) => setState(
                          () => _f = _f.copyWith(excludeAllergens: v),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
              const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () =>
                            setState(() => _f = const RecipeFilters()),
                        child: const Text('Сбросить'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.of(context).pop(_f),
                        child: Text(
                          _f.isEmpty
                              ? 'Применить'
                              : 'Применить (${_f.activeCount})',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _handle() => Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.only(top: 10, bottom: 10),
        decoration: BoxDecoration(
          color: Colors.grey.shade300,
          borderRadius: BorderRadius.circular(2),
        ),
      );

  Widget _topBar(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 8, 8),
        child: Row(
          children: [
            const Text(
              'Фильтры',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const Spacer(),
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      );

  Widget _section({required String title, String? subtitle, required Widget child}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}
DARTEOF

echo
echo "=== [5/6] write recipe_card.dart (2-column grid card) ==="
cat > "$APP/lib/features/recipes/widgets/recipe_card.dart" <<'DARTEOF'
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

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
    return Material(
      color: Colors.white,
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
                          fit: BoxFit.cover,
                          placeholder: (_, __) => Container(color: AppColors.background),
                          errorWidget: (_, __, ___) => _placeholder(),
                        )
                      : _placeholder(),
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
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary,
                          height: 1.2,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          if (_cookTime != null && _cookTime!.isNotEmpty)
                            _meta(Icons.access_time, _cookTime!),
                          if (_kcal != null) _meta(Icons.local_fire_department, _kcal!),
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
                          ? AppColors.primary
                          : (_isDisliked ? Colors.grey : Colors.grey.shade500),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _placeholder() => Container(
        color: AppColors.background,
        child: Center(
          child: Icon(Icons.restaurant_menu,
              size: 48, color: Colors.grey.shade400),
        ),
      );

  Widget _meta(IconData icon, String text) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: Colors.grey.shade600),
          const SizedBox(width: 3),
          Text(
            text,
            style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
          ),
        ],
      );

  Widget _badge(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: AppColors.secondary.withOpacity(0.15),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          text,
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        ),
      );
}
DARTEOF

echo
echo "=== [6/6] rewrite recipes_screen.dart (grid + filter sheet + favorite) ==="
cat > "$APP/lib/features/recipes/screens/recipes_screen.dart" <<'DARTEOF'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
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

  RecipeFilters _filters = const RecipeFilters();
  int _page = 1;
  bool _hasMore = true;
  bool _loadingMore = false;
  final List<Map<String, dynamic>> _recipes = [];

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
      _hasMore = true;
      _recipes.clear();
    });
    _dispatch();
  }

  void _loadNextPage() {
    setState(() {
      _loadingMore = true;
      _page += 1;
    });
    _dispatch();
  }

  void _dispatch() {
    context.read<RecipesBloc>().add(
          RecipesFilterChanged(
            filters: _filters,
            search: _searchCtrl.text.trim(),
            page: _page,
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
              _loadingMore = false;
            });
          } else if (state is RecipesError) {
            setState(() => _loadingMore = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message)),
            );
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
            Expanded(
              child: BlocBuilder<RecipesBloc, RecipesState>(
                builder: (context, state) {
                  if (_recipes.isEmpty && state is RecipesLoading) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (_recipes.isEmpty) {
                    return Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.menu_book,
                              size: 56, color: Colors.grey.shade400),
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
DARTEOF

echo
echo "=== [7/?] patch app_router.dart to pass apiClient to RecipesScreen ==="
python3 - <<'PYEOF'
from pathlib import Path
p = Path("mobile/menugen_app/lib/core/router/app_router.dart")
s = p.read_text()
old = "GoRoute(path: '/recipes', builder: (_, __) => const RecipesScreen()),"
new = "GoRoute(path: '/recipes', builder: (_, __) => RecipesScreen(apiClient: apiClient)),"
if old not in s:
    print("WARN: marker not found in app_router.dart — please patch manually:")
    print(old)
else:
    p.write_text(s.replace(old, new))
    print("app_router.dart updated.")
PYEOF

echo
echo "=== [8/?] patch recipe_detail_screen.dart to add favorite button ==="
cat > "$APP/lib/features/recipes/screens/recipe_detail_screen.dart" <<'DARTEOF'
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';

/// Полноэкранный экран рецепта. Грузит /recipes/:id/ напрямую через ApiClient.
class RecipeDetailScreen extends StatefulWidget {
  final ApiClient apiClient;
  final int recipeId;

  const RecipeDetailScreen({
    super.key,
    required this.apiClient,
    required this.recipeId,
  });

  @override
  State<RecipeDetailScreen> createState() => _RecipeDetailScreenState();
}

class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  Map<String, dynamic>? _recipe;
  String? _error;
  bool _loading = true;
  bool _favBusy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.get('/recipes/${widget.recipeId}/');
      if (!mounted) return;
      setState(() {
        _recipe = r is Map ? Map<String, dynamic>.from(r) : <String, dynamic>{};
        _loading = false;
      });
    } catch (err) {
      if (!mounted) return;
      setState(() {
        _error = err is ApiException ? err.message : err.toString();
        _loading = false;
      });
    }
  }

  Future<void> _toggleFavorite() async {
    final r = _recipe;
    if (r == null || _favBusy) return;
    final isFav = (r['is_favorite'] as bool?) ?? false;
    final isDis = (r['is_disliked'] as bool?) ?? false;

    bool? next;
    bool newFav, newDis;
    if (!isFav && !isDis) {
      next = true; newFav = true; newDis = false;
    } else if (isFav) {
      next = false; newFav = false; newDis = true;
    } else {
      next = null; newFav = false; newDis = false;
    }

    setState(() {
      _favBusy = true;
      r['is_favorite'] = newFav;
      r['is_disliked'] = newDis;
    });

    try {
      if (next == null) {
        await widget.apiClient.delete('/recipes/${widget.recipeId}/favorite/');
      } else {
        await widget.apiClient.post(
          '/recipes/${widget.recipeId}/favorite/',
          data: {'is_favorite': next},
        );
      }
    } catch (err) {
      // revert
      setState(() {
        r['is_favorite'] = isFav;
        r['is_disliked'] = isDis;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(err is ApiException ? err.message : err.toString())),
        );
      }
    } finally {
      if (mounted) setState(() => _favBusy = false);
    }
  }

  Widget _favIcon() {
    final r = _recipe;
    if (r == null) return const SizedBox.shrink();
    final isFav = (r['is_favorite'] as bool?) ?? false;
    final isDis = (r['is_disliked'] as bool?) ?? false;
    return IconButton(
      onPressed: _favBusy ? null : _toggleFavorite,
      icon: Icon(
        isFav
            ? Icons.favorite
            : (isDis ? Icons.heart_broken : Icons.favorite_border),
        color: isFav
            ? AppColors.primary
            : (isDis ? Colors.grey.shade400 : null),
      ),
      tooltip: isFav
          ? 'Любимое'
          : (isDis ? 'Нелюбимое' : 'Добавить в любимые'),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_recipe?['title'] as String? ?? 'Рецепт'),
        actions: [_favIcon()],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorView(message: _error!, onRetry: _load)
              : _DetailBody(recipe: _recipe!),
    );
  }
}

class _DetailBody extends StatelessWidget {
  final Map<String, dynamic> recipe;
  const _DetailBody({required this.recipe});

  String get _title => (recipe['title'] as String?) ?? '';
  String? get _imageUrl => recipe['image_url'] as String?;
  String? get _videoUrl => recipe['video_url'] as String?;
  String? get _cookTime => recipe['cook_time'] as String?;
  int? get _servings => recipe['servings'] as int?;
  String? get _country => recipe['country'] as String?;

  List<Map<String, dynamic>> get _ingredients =>
      (recipe['ingredients'] as List?)
              ?.whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList() ??
          const [];

  List<Map<String, dynamic>> get _steps =>
      (recipe['steps'] as List?)
              ?.whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList() ??
          const [];

  Map<String, dynamic> get _nutrition =>
      recipe['nutrition'] is Map
          ? Map<String, dynamic>.from(recipe['nutrition'] as Map)
          : <String, dynamic>{};

  List<String> get _categories =>
      (recipe['categories'] as List?)?.whereType<String>().toList() ?? const [];

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        if (_imageUrl != null && _imageUrl!.isNotEmpty)
          AspectRatio(
            aspectRatio: 16 / 9,
            child: CachedNetworkImage(
              imageUrl: _imageUrl!,
              fit: BoxFit.cover,
              placeholder: (_, __) => Container(color: AppColors.background),
              errorWidget: (_, __, ___) => Container(
                color: AppColors.background,
                child:
                    Icon(Icons.restaurant, size: 64, color: Colors.grey.shade400),
              ),
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _title,
                style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  if (_cookTime != null && _cookTime!.isNotEmpty)
                    _MetaItem(icon: Icons.access_time, text: _cookTime!),
                  if (_servings != null)
                    _MetaItem(
                        icon: Icons.people_outline,
                        text: '$_servings порц.'),
                  if (_country != null && _country!.isNotEmpty)
                    _MetaItem(icon: Icons.public, text: _country!),
                ],
              ),
              if (_categories.isNotEmpty) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: _categories
                      .map((c) => Chip(
                            label: Text(c, style: const TextStyle(fontSize: 12)),
                            visualDensity: VisualDensity.compact,
                          ))
                      .toList(),
                ),
              ],
              if (_videoUrl != null && _videoUrl!.isNotEmpty) ...[
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Видео: $_videoUrl')),
                    );
                  },
                  icon: const Icon(Icons.play_circle_outline),
                  label: const Text('Смотреть видео'),
                ),
              ],
              if (_nutrition.isNotEmpty) ...[
                const SizedBox(height: 20),
                _NutritionGrid(nutrition: _nutrition),
              ],
              const SizedBox(height: 20),
              if (_ingredients.isNotEmpty) ...[
                const _SectionTitle('Ингредиенты'),
                const SizedBox(height: 8),
                ..._ingredients.map(_buildIngredientRow),
                const SizedBox(height: 20),
              ],
              if (_steps.isNotEmpty) ...[
                const _SectionTitle('Приготовление'),
                const SizedBox(height: 8),
                ...List.generate(_steps.length, (i) {
                  final s = _steps[i];
                  return _StepRow(index: i + 1, text: (s['text'] as String?) ?? '');
                }),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildIngredientRow(Map<String, dynamic> ing) {
    final name = (ing['name'] as String?) ?? '';
    final qty = ing['quantity']?.toString() ?? '';
    final unit = (ing['unit'] as String?) ?? '';
    final amount = [qty, unit].where((s) => s.isNotEmpty).join(' ');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 7),
            child: Icon(Icons.circle, size: 6, color: AppColors.secondary),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(name,
                style: const TextStyle(fontSize: 15, color: AppColors.textPrimary)),
          ),
          if (amount.isNotEmpty)
            Text(amount,
                style: TextStyle(fontSize: 14, color: Colors.grey.shade700)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
          fontSize: 17, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
    );
  }
}

class _MetaItem extends StatelessWidget {
  final IconData icon;
  final String text;
  const _MetaItem({required this.icon, required this.text});
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: AppColors.secondary),
        const SizedBox(width: 6),
        Text(text, style: const TextStyle(fontSize: 14)),
      ],
    );
  }
}

class _NutritionGrid extends StatelessWidget {
  final Map<String, dynamic> nutrition;
  const _NutritionGrid({required this.nutrition});

  String? _val(String key) {
    final v = nutrition[key];
    if (v is Map) {
      final value = v['value'];
      final unit = v['unit'];
      if (value == null) return null;
      return unit == null ? '$value' : '$value $unit';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final entries = <(String, String?)>[
      ('Калории', _val('calories')),
      ('Белки', _val('proteins')),
      ('Жиры', _val('fats')),
      ('Углеводы', _val('carbs')),
    ].where((e) => e.$2 != null).toList();
    if (entries.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: entries.map((e) {
          return Expanded(
            child: Column(
              children: [
                Text(e.$2!,
                    style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary)),
                const SizedBox(height: 2),
                Text(e.$1,
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  final int index;
  final String text;
  const _StepRow({required this.index, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 14,
            backgroundColor: AppColors.primary,
            child: Text('$index',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w700)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text,
                style:
                    const TextStyle(fontSize: 15, color: AppColors.textPrimary)),
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 56, color: Colors.red),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            TextButton(onPressed: onRetry, child: const Text('Повторить')),
          ],
        ),
      ),
    );
  }
}
DARTEOF

echo
echo "=== DONE mobile patch ==="
echo "Backups: $BAK"
echo
echo "Next steps (manually):"
echo "  1. cd $APP && flutter analyze 2>&1 | tail -40"
echo "  2. flutter test test/recipes_bloc_test.dart 2>&1 | tail -20"
