part of 'shopping_bloc.dart';

abstract class ShoppingEvent extends Equatable {
  const ShoppingEvent();
  @override
  List<Object?> get props => [];
}

class ShoppingListsRequested extends ShoppingEvent {
  final bool archived;
  const ShoppingListsRequested({this.archived = false});
  @override
  List<Object?> get props => [archived];
}

class ShoppingDetailRequested extends ShoppingEvent {
  final int listId;
  const ShoppingDetailRequested(this.listId);
  @override
  List<Object?> get props => [listId];
}

class ShoppingCreateRequested extends ShoppingEvent {
  final Map<String, dynamic> payload;
  const ShoppingCreateRequested(this.payload);
  @override
  List<Object?> get props => [payload];
}

class ShoppingDeleteRequested extends ShoppingEvent {
  final int listId;
  const ShoppingDeleteRequested(this.listId);
  @override
  List<Object?> get props => [listId];
}

class ShoppingArchiveRequested extends ShoppingEvent {
  final int listId;
  final bool archived;
  const ShoppingArchiveRequested(this.listId, this.archived);
  @override
  List<Object?> get props => [listId, archived];
}

class ShoppingAddItemRequested extends ShoppingEvent {
  final int listId;
  final String name;
  const ShoppingAddItemRequested(this.listId, this.name);
  @override
  List<Object?> get props => [listId, name];
}

class ShoppingDeleteItemRequested extends ShoppingEvent {
  final int listId;
  final int itemId;
  const ShoppingDeleteItemRequested(this.listId, this.itemId);
  @override
  List<Object?> get props => [listId, itemId];
}

class ShoppingToggleItemRequested extends ShoppingEvent {
  final int listId;
  final int itemId;
  final bool isPurchased;
  const ShoppingToggleItemRequested(this.listId, this.itemId, this.isPurchased);
  @override
  List<Object?> get props => [listId, itemId, isPurchased];
}
