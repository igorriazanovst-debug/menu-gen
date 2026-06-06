import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../models/shopping_models.dart';

part 'shopping_event.dart';
part 'shopping_state.dart';

/// Bloc backing the shopping lists screen.
///
///  * load lists  → GET  /shopping/lists/?archived=
///  * load detail → GET  /shopping/lists/{id}/
///  * create      → POST /shopping/lists/
///  * delete      → DELETE /shopping/lists/{id}/
///  * archive     → PATCH /shopping/lists/{id}/  {is_archived}
///  * add item    → POST /shopping/lists/{id}/items/  (rubricator payload)
///  * del item    → DELETE /shopping/lists/{id}/items/{itemId}/
///  * toggle      → PATCH /shopping/lists/{id}/items/{itemId}/toggle/
class ShoppingBloc extends Bloc<ShoppingEvent, ShoppingState> {
  final ApiClient apiClient;

  ShoppingBloc({required this.apiClient}) : super(const ShoppingInitial()) {
    on<ShoppingListsRequested>(_onLists);
    on<ShoppingDetailRequested>(_onDetail);
    on<ShoppingCreateRequested>(_onCreate);
    on<ShoppingDeleteRequested>(_onDelete);
    on<ShoppingArchiveRequested>(_onArchive);
    on<ShoppingAddItemRequested>(_onAddItem);
    on<ShoppingDeleteItemRequested>(_onDeleteItem);
    on<ShoppingToggleItemRequested>(_onToggle);
    on<ShoppingUpdateItemRequested>(_onUpdateItem); // MG_SHOPBUG_MOB
    on<ShoppingPendingRequested>(_onPending); // MG_SHAREACCEPT
    on<ShoppingRespondRequested>(_onRespond); // MG_SHAREACCEPT
  }

  Map<String, dynamic> _asMap(dynamic d) =>
      d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};

  bool _archived = false;

  Future<void> _reloadLists(Emitter<ShoppingState> emit) async {
    final raw = await apiClient.get('/shopping/lists/',
        params: _archived ? {'archived': 'true'} : null);
    final list = (raw is List ? raw : const [])
        .whereType<Map>()
        .map((e) => ShoppingListBrief.fromJson(Map<String, dynamic>.from(e)))
        .toList();
    emit(ShoppingListsLoaded(lists: list, archived: _archived));
  }

  Future<void> _onLists(
      ShoppingListsRequested e, Emitter<ShoppingState> emit) async {
    _archived = e.archived;
    emit(const ShoppingLoading());
    try {
      await _reloadLists(emit);
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onDetail(
      ShoppingDetailRequested e, Emitter<ShoppingState> emit) async {
    emit(const ShoppingLoading());
    try {
      final raw = await apiClient.get('/shopping/lists/${e.listId}/');
      emit(ShoppingDetailLoaded(ShoppingListDetail.fromJson(_asMap(raw))));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onCreate(
      ShoppingCreateRequested e, Emitter<ShoppingState> emit) async {
    try {
      final raw = await apiClient.post('/shopping/lists/', data: e.payload);
      final detail = ShoppingListDetail.fromJson(_asMap(raw));
      emit(ShoppingDetailLoaded(detail));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onDelete(
      ShoppingDeleteRequested e, Emitter<ShoppingState> emit) async {
    try {
      await apiClient.delete('/shopping/lists/${e.listId}/');
      await _reloadLists(emit);
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onArchive(
      ShoppingArchiveRequested e, Emitter<ShoppingState> emit) async {
    try {
      await apiClient.patch('/shopping/lists/${e.listId}/',
          data: {'is_archived': e.archived});
      await _reloadLists(emit);
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onAddItem(
      ShoppingAddItemRequested e, Emitter<ShoppingState> emit) async {
    try {
      // MG_SHOPMOB001: send full rubricator payload.
      await apiClient.post('/shopping/lists/${e.listId}/items/',
          data: e.payload);
      add(ShoppingDetailRequested(e.listId));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onDeleteItem(
      ShoppingDeleteItemRequested e, Emitter<ShoppingState> emit) async {
    try {
      await apiClient.delete('/shopping/lists/${e.listId}/items/${e.itemId}/');
      add(ShoppingDetailRequested(e.listId));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onToggle(
      ShoppingToggleItemRequested e, Emitter<ShoppingState> emit) async {
    try {
      await apiClient.patch(
          '/shopping/lists/${e.listId}/items/${e.itemId}/toggle/',
          data: {'is_purchased': e.isPurchased});
      add(ShoppingDetailRequested(e.listId));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  // MG_SHOPBUG_MOB: PATCH item then refresh detail.
  Future<void> _onUpdateItem(
      ShoppingUpdateItemRequested e, Emitter<ShoppingState> emit) async {
    try {
      await apiClient.patch(
          '/shopping/lists/${e.listId}/items/${e.itemId}/',
          data: e.payload);
      add(ShoppingDetailRequested(e.listId));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  // MG_SHAREACCEPT: load pending shares.
  Future<List<ShoppingPendingList>> _fetchPending() async {
    final raw = await apiClient.get('/shopping/pending/');
    return (raw is List ? raw : const [])
        .whereType<Map>()
        .map((m) => ShoppingPendingList.fromJson(Map<String, dynamic>.from(m)))
        .toList();
  }

  Future<void> _onPending(
      ShoppingPendingRequested e, Emitter<ShoppingState> emit) async {
    emit(const ShoppingLoading());
    try {
      emit(ShoppingPendingLoaded(await _fetchPending()));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  Future<void> _onRespond(
      ShoppingRespondRequested e, Emitter<ShoppingState> emit) async {
    try {
      await apiClient.post('/shopping/lists/${e.listId}/respond/',
          data: {'action': e.accept ? 'accept' : 'reject'});
      emit(ShoppingPendingLoaded(await _fetchPending()));
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  String _msg(Object err) =>
      err is ApiException ? err.message : 'Ошибка. Попробуйте позже.';
}
