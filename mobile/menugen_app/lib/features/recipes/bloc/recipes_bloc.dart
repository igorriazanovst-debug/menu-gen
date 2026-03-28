import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class RecipesEvent extends Equatable {
  const RecipesEvent();
  @override List<Object?> get props => [];
}
class RecipesLoadRequested extends RecipesEvent { const RecipesLoadRequested(); }
class RecipesSearchRequested extends RecipesEvent {
  final String query;
  const RecipesSearchRequested(this.query);
  @override List<Object?> get props => [query];
}

abstract class RecipesState extends Equatable {
  const RecipesState();
  @override List<Object?> get props => [];
}
class RecipesLoading extends RecipesState { const RecipesLoading(); }
class RecipesLoaded extends RecipesState {
  final List<Map<String, dynamic>> recipes;
  const RecipesLoaded({required this.recipes});
  @override List<Object?> get props => [recipes];
}
class RecipesError extends RecipesState {
  final String message;
  const RecipesError(this.message);
  @override List<Object?> get props => [message];
}

class RecipesBloc extends Bloc<RecipesEvent, RecipesState> {
  final ApiClient apiClient;
  final AppDatabase db;
  RecipesBloc({required this.apiClient, required this.db}) : super(const RecipesLoading()) {
    on<RecipesLoadRequested>(_onLoad);
    on<RecipesSearchRequested>(_onSearch);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }
  List<Map<String, dynamic>> _results(dynamic d) => d is Map
      ? (d['results'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList()
      : [];

  Future<void> _onLoad(RecipesLoadRequested e, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final r = await apiClient.get('/recipes/');
      emit(RecipesLoaded(recipes: _results(_data(r))));
    } catch (e) { emit(RecipesError(e.toString())); }
  }

  Future<void> _onSearch(RecipesSearchRequested e, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final r = await apiClient.get('/recipes/', params: {'search': e.query});
      emit(RecipesLoaded(recipes: _results(_data(r))));
    } catch (e) { emit(RecipesError(e.toString())); }
  }
}