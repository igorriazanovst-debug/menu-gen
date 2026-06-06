part of 'shopping_bloc.dart';

abstract class ShoppingState extends Equatable {
  const ShoppingState();
  @override
  List<Object?> get props => [];
}

class ShoppingInitial extends ShoppingState {
  const ShoppingInitial();
}

class ShoppingLoading extends ShoppingState {
  const ShoppingLoading();
}

class ShoppingListsLoaded extends ShoppingState {
  final List<ShoppingListBrief> lists;
  final bool archived;
  const ShoppingListsLoaded({required this.lists, required this.archived});
  @override
  List<Object?> get props => [lists, archived];
}

class ShoppingDetailLoaded extends ShoppingState {
  final ShoppingListDetail detail;
  const ShoppingDetailLoaded(this.detail);
  @override
  List<Object?> get props => [detail];
}

class ShoppingError extends ShoppingState {
  final String message;
  const ShoppingError(this.message);
  @override
  List<Object?> get props => [message];
}

// MG_SHAREACCEPT
class ShoppingPendingLoaded extends ShoppingState {
  final List<ShoppingPendingList> pending;
  const ShoppingPendingLoaded(this.pending);
  @override
  List<Object?> get props => [pending];
}
