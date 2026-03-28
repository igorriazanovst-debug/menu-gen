part of 'menu_bloc.dart';

abstract class MenuState extends Equatable {
  const MenuState();
  @override List<Object?> get props => [];
}
class MenuInitial    extends MenuState { const MenuInitial(); }
class MenuLoading    extends MenuState { const MenuLoading(); }
class MenuGenerating extends MenuState { const MenuGenerating(); }
class MenuLoaded extends MenuState {
  final List<Menu> menus;
  const MenuLoaded({required this.menus});
  @override List<Object?> get props => [menus];
}
class MenuGenerated extends MenuState {
  final Menu menu;
  const MenuGenerated({required this.menu});
  @override List<Object?> get props => [menu];
}
class MenuError extends MenuState {
  final String message;
  const MenuError({required this.message});
  @override List<Object?> get props => [message];
}
