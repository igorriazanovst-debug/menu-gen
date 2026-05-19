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

/// MG_608_V_mobile_state:
///  - `menus`  — полный список меню (краткие — без items), для UI dropdown.
///  - `active` — детальное меню (с items), которое сейчас отображается.
class MenuLoaded extends MenuState {
  final List<Map<String, dynamic>> menus;
  final Map<String, dynamic>? active;
  const MenuLoaded({required this.menus, this.active});
  @override
  List<Object?> get props => [menus, active];
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
