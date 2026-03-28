part of 'menu_bloc.dart';

abstract class MenuEvent extends Equatable {
  const MenuEvent();
  @override List<Object?> get props => [];
}
class MenuLoadRequested extends MenuEvent {}
class MenuGenerateRequested extends MenuEvent {
  final int periodDays;
  final String startDate;
  final String? country;
  const MenuGenerateRequested({this.periodDays = 7, required this.startDate, this.country});
  @override List<Object?> get props => [periodDays, startDate, country];
}
class MenuItemSwapRequested extends MenuEvent {
  final int menuId;
  final int itemId;
  final int recipeId;
  const MenuItemSwapRequested({required this.menuId, required this.itemId, required this.recipeId});
  @override List<Object?> get props => [menuId, itemId, recipeId];
}
