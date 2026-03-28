part of 'fridge_bloc.dart';
abstract class FridgeEvent extends Equatable {
  const FridgeEvent();
  @override List<Object?> get props => [];
}
class FridgeLoadRequested extends FridgeEvent { const FridgeLoadRequested(); }
class FridgeItemAdded extends FridgeEvent {
  final Map<String, dynamic> data;
  const FridgeItemAdded(this.data);
  @override List<Object?> get props => [data];
}
class FridgeItemDeleted extends FridgeEvent {
  final int id;
  const FridgeItemDeleted(this.id);
  @override List<Object?> get props => [id];
}
