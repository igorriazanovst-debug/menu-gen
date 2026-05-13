part of 'menu_bloc.dart';

abstract class MenuState extends Equatable {
  const MenuState();
  @override
  List<Object?> get props => [];
}

class MenuInitial extends MenuState {
  const MenuInitial();
}

class MenuLoading extends MenuState {
  const MenuLoading();
}

class MenuGenerating extends MenuState {
  const MenuGenerating();
}

class MenuLoaded extends MenuState {
  final List<Map<String, dynamic>> menus;
  const MenuLoaded({required this.menus});
  @override
  List<Object?> get props => [menus];
}

class MenuGenerated extends MenuState {
  final Map<String, dynamic> menu;
  const MenuGenerated(this.menu);
  @override
  List<Object?> get props => [menu];
}

/// MG-606: backend denied access with 403.
class MenuPremiumLocked extends MenuState {
  final String message;
  final bool isWrite;
  const MenuPremiumLocked({required this.message, required this.isWrite});
  @override
  List<Object?> get props => [message, isWrite];
}

class MenuError extends MenuState {
  final String message;
  const MenuError(this.message);
  @override
  List<Object?> get props => [message];
}
