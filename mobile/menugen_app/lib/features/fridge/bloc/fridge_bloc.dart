import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class FridgeEvent extends Equatable {
  const FridgeEvent();
  @override List<Object?> get props => [];
}
class FridgeLoadRequested extends FridgeEvent { const FridgeLoadRequested(); }
class FridgeItemAdded extends FridgeEvent {
  final Map<String, dynamic> item;
  const FridgeItemAdded(this.item);
  @override List<Object?> get props => [item];
}
class FridgeItemDeleted extends FridgeEvent {
  final int itemId;
  const FridgeItemDeleted(this.itemId);
  @override List<Object?> get props => [itemId];
}

abstract class FridgeState extends Equatable {
  const FridgeState();
  @override List<Object?> get props => [];
}
class FridgeLoading extends FridgeState { const FridgeLoading(); }
class FridgeLoaded extends FridgeState {
  final List<Map<String, dynamic>> items;
  const FridgeLoaded({required this.items});
  @override List<Object?> get props => [items];
}
class FridgeError extends FridgeState {
  final String message;
  const FridgeError(this.message);
  @override List<Object?> get props => [message];
}

class FridgeBloc extends Bloc<FridgeEvent, FridgeState> {
  final ApiClient apiClient;
  final AppDatabase db;
  FridgeBloc({required this.apiClient, required this.db}) : super(const FridgeLoading()) {
    on<FridgeLoadRequested>(_onLoad);
    on<FridgeItemAdded>(_onAdd);
    on<FridgeItemDeleted>(_onDelete);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(FridgeLoadRequested e, Emitter<FridgeState> emit) async {
    emit(const FridgeLoading());
    try {
      final r = await apiClient.get('/fridge/');
      final d = _data(r);
      final results = d is Map
          ? (d['results'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList()
          : <Map<String, dynamic>>[];
      emit(FridgeLoaded(items: results));
    } catch (e) { emit(FridgeError(e.toString())); }
  }

  Future<void> _onAdd(FridgeItemAdded e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.post('/fridge/', data: e.item);
      add(const FridgeLoadRequested());
    } catch (e) { emit(FridgeError(e.toString())); }
  }

  Future<void> _onDelete(FridgeItemDeleted e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.delete('/fridge/${e.itemId}/');
      add(const FridgeLoadRequested());
    } catch (e) { emit(FridgeError(e.toString())); }
  }
}