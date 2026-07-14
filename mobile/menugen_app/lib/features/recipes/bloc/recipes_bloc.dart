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
  final int total; // всего рецептов (count) — для нумерованной пагинации
  const RecipesPageLoaded({required this.recipes, required this.hasMore, this.total = 0});
  @override
  List<Object?> get props => [recipes, hasMore, total];
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

  int _total(dynamic d) => d is Map && d['count'] is int ? d['count'] as int : 0;

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
      emit(RecipesPageLoaded(recipes: _results(d), hasMore: _hasMore(d), total: _total(d)));
    } catch (err) {
      emit(RecipesError(_msg(err)));
    }
  }

  Future<void> _onFilter(RecipesFilterChanged e, Emitter<RecipesState> emit) async {
    // Emit Loading for fresh page (so BlocListener fires even if the next
    // RecipesPageLoaded happens to equal the previous one — Equatable dedupes).
    if (e.page <= 1) {
      emit(const RecipesLoading());
    }
    try {
      final params = e.filters.toQueryParams(
        search: e.search,
        page: e.page,
        fridgeNames: e.fridgeNames,
      );
      final r = await apiClient.get('/recipes/', params: params);
      final d = _data(r);
      emit(RecipesPageLoaded(recipes: _results(d), hasMore: _hasMore(d), total: _total(d)));
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
