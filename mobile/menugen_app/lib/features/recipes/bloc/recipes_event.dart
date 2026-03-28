part of 'recipes_bloc.dart';
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
