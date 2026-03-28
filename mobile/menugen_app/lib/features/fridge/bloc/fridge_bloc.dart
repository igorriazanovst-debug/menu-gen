import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/models/fridge_item.dart';

part 'fridge_event.dart';
part 'fridge_state.dart';

class FridgeBloc extends Bloc<FridgeEvent, FridgeState> {
  final ApiClient apiClient;
  final AppDatabase db;

  FridgeBloc({required this.apiClient, required this.db}) : super(const FridgeInitial()) {
    on<FridgeLoadRequested>(_onLoad);
    on<FridgeItemAdded>(_onAdd);
    on<FridgeItemDeleted>(_onDelete);
  }

  Future<void> _onLoad(FridgeLoadRequested event, Emitter<FridgeState> emit) async {
    emit(const FridgeLoading());
    try {
      final resp = await apiClient.get('/fridge/');
      final items = (resp.data['results'] as List)
          .map((j) => FridgeItem.fromJson(j as Map<String, dynamic>)).toList();
      emit(FridgeLoaded(items: items));
    } catch (e) {
      emit(FridgeError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onAdd(FridgeItemAdded event, Emitter<FridgeState> emit) async {
    try {
      await apiClient.post('/fridge/', data: event.data);
      add(FridgeLoadRequested());
    } catch (e) {
      emit(FridgeError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onDelete(FridgeItemDeleted event, Emitter<FridgeState> emit) async {
    try {
      await apiClient.delete('/fridge/\${event.id}/');
      add(FridgeLoadRequested());
    } catch (e) {
      emit(FridgeError(message: ApiException.fromDio(e).message));
    }
  }
}
