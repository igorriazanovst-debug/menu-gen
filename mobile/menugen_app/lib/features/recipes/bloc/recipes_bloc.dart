import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/models/recipe.dart';

part 'recipes_event.dart';
part 'recipes_state.dart';

class RecipesBloc extends Bloc<RecipesEvent, RecipesState> {
  final ApiClient apiClient;
  final AppDatabase db;

  RecipesBloc({required this.apiClient, required this.db}) : super(const RecipesInitial()) {
    on<RecipesLoadRequested>(_onLoad);
    on<RecipesSearchRequested>(_onSearch);
  }

  Future<void> _onLoad(RecipesLoadRequested event, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final resp = await apiClient.get('/recipes/', params: {'page_size': '20'});
      final recipes = (resp.data['results'] as List)
          .map((j) => Recipe.fromJson(j as Map<String, dynamic>)).toList();
      emit(RecipesLoaded(recipes: recipes));
    } catch (e) {
      emit(RecipesError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onSearch(RecipesSearchRequested event, Emitter<RecipesState> emit) async {
    emit(const RecipesLoading());
    try {
      final resp = await apiClient.get('/recipes/', params: {'search': event.query});
      final recipes = (resp.data['results'] as List)
          .map((j) => Recipe.fromJson(j as Map<String, dynamic>)).toList();
      emit(RecipesLoaded(recipes: recipes));
    } catch (e) {
      emit(RecipesError(message: ApiException.fromDio(e).message));
    }
  }
}
