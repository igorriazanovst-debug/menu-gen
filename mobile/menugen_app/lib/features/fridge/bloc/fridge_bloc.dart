import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';

// ── Events ─────────────────────────────────────────────────────────────────
abstract class FridgeEvent extends Equatable {
  const FridgeEvent();
  @override
  List<Object?> get props => [];
}

class FridgeLoadRequested extends FridgeEvent {
  const FridgeLoadRequested();
}

class FridgeItemAdded extends FridgeEvent {
  final String name;
  final double quantity;
  final String unit;
  final String expiryDate;
  final int? productId;
  const FridgeItemAdded({
    required this.name,
    required this.quantity,
    required this.unit,
    required this.expiryDate,
    this.productId,
  });
  @override
  List<Object?> get props => [name, quantity, unit, expiryDate, productId];
}

class FridgeItemDeleted extends FridgeEvent {
  final int id;
  const FridgeItemDeleted(this.id);
  @override
  List<Object?> get props => [id];
}

// ── States ─────────────────────────────────────────────────────────────────
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
  final List<Map<String, dynamic>> categories;
  const FridgeLoaded({
    required this.items,
    this.categories = const [],
  });
  FridgeLoaded copyWith({
    List<Map<String, dynamic>>? items,
    List<Map<String, dynamic>>? categories,
  }) =>
      FridgeLoaded(
        items: items ?? this.items,
        categories: categories ?? this.categories,
      );
  @override
  List<Object?> get props => [items, categories];
}

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

// ── Bloc ───────────────────────────────────────────────────────────────────
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

  Future<List<Map<String, dynamic>>> _fetchCategories() async {
    try {
      final r = await apiClient.get('/fridge/categories/');
      if (r is List) {
        return r.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
      }
    } catch (_) {/* non-fatal — UI degrades to "no categories" */}
    return const [];
  }

  Future<void> _onLoad(FridgeLoadRequested e, Emitter<FridgeState> emit) async {
    emit(const FridgeLoading());
    try {
      final results = await Future.wait([
        apiClient.get('/fridge/'),
        _fetchCategories(),
      ]);
      final r = results[0];
      final cats = results[1] as List<Map<String, dynamic>>;
      final list = (r is Map ? (r['results'] as List? ?? []) : [])
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      premiumGate?.reportReadSuccess();
      emit(FridgeLoaded(items: list, categories: cats));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  Future<void> _onAdd(FridgeItemAdded e, Emitter<FridgeState> emit) async {
    try {
      final body = <String, dynamic>{
        'name': e.name,
        'quantity': e.quantity,
        'unit': e.unit,
        'expiry_date': e.expiryDate,
      };
      if (e.productId != null) body['product'] = e.productId;
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
