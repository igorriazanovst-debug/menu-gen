part of 'fridge_bloc.dart';
abstract class FridgeState extends Equatable {
  const FridgeState();
  @override List<Object?> get props => [];
}
class FridgeInitial extends FridgeState { const FridgeInitial(); }
class FridgeLoading extends FridgeState { const FridgeLoading(); }
class FridgeLoaded extends FridgeState {
  final List<FridgeItem> items;
  const FridgeLoaded({required this.items});
  @override List<Object?> get props => [items];
}
class FridgeError extends FridgeState {
  final String message;
  const FridgeError({required this.message});
  @override List<Object?> get props => [message];
}
