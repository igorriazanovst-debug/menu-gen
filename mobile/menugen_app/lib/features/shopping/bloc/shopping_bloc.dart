import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T08
import '../../../core/sync/pending_sync_cubit.dart'; // MG_T08
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
  // MG_T08: offline toggle support (connectivity + in-memory LWW queue + counter).
  final ConnectivityCubit? connectivity;
  final PendingSyncCubit? pendingSync;
  final Map<String, _PendingToggle> _queue = {}; // 'listId:itemId' -> latest
  StreamSubscription<ConnectivityStatus>? _connSub;
  bool _flushing = false;

  ShoppingBloc({
    required this.apiClient,
    this.connectivity, // MG_T08
    this.pendingSync, // MG_T08
  }) : super(const ShoppingInitial()) {
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
    // MG_T08: push queued toggles when connectivity returns.
    _connSub = connectivity?.stream.listen((s) {
      if (s == ConnectivityStatus.online) _flushQueue();
    });
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
    // MG_B10: after create, reload the active lists so the new list appears
    // immediately. Previously emitted ShoppingDetailLoaded, which left the
    // list screen blank until the user switched tabs.
    try {
      await apiClient.post('/shopping/lists/', data: e.payload);
      _archived = false;
      await _reloadLists(emit);
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

  // MG_B11 + MG_T08: optimistic in-place flip first (instant UI, offline-first);
  // online -> PATCH; offline or network failure -> queue (LWW, last action wins).
  Future<void> _onToggle(
      ShoppingToggleItemRequested e, Emitter<ShoppingState> emit) async {
    final cur = state;
    if (cur is ShoppingDetailLoaded && cur.detail.id == e.listId) {
      final items = cur.detail.items
          .map((it) => it.id == e.itemId
              ? it.copyWith(isPurchased: e.isPurchased)
              : it)
          .toList();
      emit(ShoppingDetailLoaded(cur.detail.copyWith(items: items)));
    }
    if (connectivity?.state == ConnectivityStatus.offline) {
      _enqueueToggle(e.listId, e.itemId, e.isPurchased);
      return;
    }
    try {
      await apiClient.patch(
          '/shopping/lists/${e.listId}/items/${e.itemId}/toggle/',
          data: {'is_purchased': e.isPurchased});
    } on ApiException catch (err) {
      if (err.isNetwork) {
        _enqueueToggle(e.listId, e.itemId, e.isPurchased);
      } else {
        emit(ShoppingError(err.message));
      }
    } catch (err) {
      emit(ShoppingError(_msg(err)));
    }
  }

  // MG_T08: record the final desired state for an item (LWW per item).
  void _enqueueToggle(int listId, int itemId, bool isPurchased) {
    _queue['$listId:$itemId'] = _PendingToggle(
        listId: listId, itemId: itemId, isPurchased: isPurchased);
    pendingSync?.set(_queue.length);
  }

  // MG_T08: flush queued toggles to the server; resync the open list after.
  Future<void> _flushQueue() async {
    if (_flushing) return;
    if (connectivity?.state == ConnectivityStatus.offline) return;
    _flushing = true;
    try {
      int? lastListId;
      for (final k in _queue.keys.toList()) {
        final t = _queue[k];
        if (t == null) continue;
        try {
          await apiClient.patch(
              '/shopping/lists/${t.listId}/items/${t.itemId}/toggle/',
              data: {'is_purchased': t.isPurchased});
          if (identical(_queue[k], t)) _queue.remove(k); // keep if superseded
          lastListId = t.listId;
        } catch (_) {
          break; // still offline / failed -> keep the rest for next reconnect
        }
      }
      pendingSync?.set(_queue.length);
      final cur = state;
      if (lastListId != null &&
          cur is ShoppingDetailLoaded &&
          cur.detail.id == lastListId) {
        add(ShoppingDetailRequested(lastListId));
      }
    } finally {
      _flushing = false;
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

  // MG_T08: cancel connectivity sub; clear this bloc's pending contribution
  // (in-memory queue is discarded by design when leaving the shopping tab).
  @override
  Future<void> close() {
    _connSub?.cancel();
    pendingSync?.set(0);
    return super.close();
  }
}

// MG_T08: a queued offline toggle — the final desired state per item (LWW).
class _PendingToggle {
  final int listId;
  final int itemId;
  final bool isPurchased;
  _PendingToggle(
      {required this.listId, required this.itemId, required this.isPurchased});
}
