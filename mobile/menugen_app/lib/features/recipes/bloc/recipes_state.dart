part of 'recipes_bloc.dart';
abstract class RecipesState extends Equatable {
  const RecipesState();
  @override List<Object?> get props => [];
}
class RecipesInitial extends RecipesState { const RecipesInitial(); }
class RecipesLoading extends RecipesState { const RecipesLoading(); }
class RecipesLoaded extends RecipesState {
  final List<Recipe> recipes;
  const RecipesLoaded({required this.recipes});
  @override List<Object?> get props => [recipes];
}
class RecipesError extends RecipesState {
  final String message;
  const RecipesError({required this.message});
  @override List<Object?> get props => [message];
}
