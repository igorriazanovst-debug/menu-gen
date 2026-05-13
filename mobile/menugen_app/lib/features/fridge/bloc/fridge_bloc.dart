import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';

abstract class FridgeEvent extends Equatable {
  const FridgeEvent();
  @override
  List<Object?> get props => [];
}

class FridgeLoadRequested extends FridgeEvent {
  const FridgeLoadRequested();
}

/// Add a new fridge item. Name preserved from pre-patch API for screen
/// compatibility.
class FridgeItemAdded extends FridgeEvent {
  final String name;
  final double? quantity;
  final String? unit;
  final String? expiryDate;
  const FridgeItemAdded({
    required this.name,
    this.quantity,
    this.unit,
    this.expiryDate,
  });
  @override
  List<Object?> get props => [name, quantity, unit, expiryDate];
}

/// Delete a fridge item. Name preserved from pre-patch API.
class FridgeItemDeleted extends FridgeEvent {
  final int id;
  const FridgeItemDeleted(this.id);
  @override
  List<Object?> get props => [id];
}

abstract class FridgeState extends Equatable {
  const FridgeState();
  @override
  List<Object?> get props => [];
}

class FridgeLoading extends FridgeState {
  const FridgeLoading();
}

class FridgeLoaded extends FridgeState {
  final List<Map<String, dynamic>> items;
  const FridgeLoaded({required this.items});
  @override
  List<Object?> get props => [items];
}

/// MG-606: 403 from IsFamilyPremiumOrReadOnly.
class FridgePremiumLocked extends FridgeState {
  final String message;
  final bool isWrite;
  const FridgePremiumLocked({required this.message, required this.isWrite});
  @override
  List<Object?> get props => [message, isWrite];
}

class FridgeError extends FridgeState {
  final String message;
  const FridgeError(this.message);
  @override
  List<Object?> get props => [message];
}

class FridgeBloc extends Bloc<FridgeEvent, FridgeState> {
  final ApiClient apiClient;
  final AppDatabase db;
  final PremiumGateCubit? premiumGate;

  FridgeBloc({
    required this.apiClient,
    required this.db,
    this.premiumGate,
  }) : super(const FridgeLoading()) {
    on<FridgeLoadRequested>(_onLoad);
    on<FridgeItemAdded>(_onAdd);
    on<FridgeItemDeleted>(_onDelete);
  }

  FridgeState _toErrorState(Object err, {required bool isWrite}) {
    if (err is ApiException && err.isPremiumLocked) {
      premiumGate?.reportLock(
        feature: 'fridge',
        isWrite: isWrite,
        message: err.message,
      );
      return FridgePremiumLocked(message: err.message, isWrite: isWrite);
    }
    final msg = err is ApiException ? err.message : err.toString();
    return FridgeError(msg);
  }

  Future<void> _onLoad(FridgeLoadRequested e, Emitter<FridgeState> emit) async {
    emit(const FridgeLoading());
    try {
      final r = await apiClient.get('/fridge/');
      final list = (r is Map ? (r['results'] as List? ?? []) : [])
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      premiumGate?.reportReadSuccess();
      emit(FridgeLoaded(items: list));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  Future<void> _onAdd(FridgeItemAdded e, Emitter<FridgeState> emit) async {
    try {
      final body = <String, dynamic>{'name': e.name};
      if (e.quantity != null) body['quantity'] = e.quantity;
      if (e.unit != null) body['unit'] = e.unit;
      if (e.expiryDate != null) body['expiry_date'] = e.expiryDate;
      await apiClient.post('/fridge/', data: body);
      add(const FridgeLoadRequested());
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }

  Future<void> _onDelete(FridgeItemDeleted e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.delete('/fridge/${e.id}/');
      add(const FridgeLoadRequested());
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }
}
