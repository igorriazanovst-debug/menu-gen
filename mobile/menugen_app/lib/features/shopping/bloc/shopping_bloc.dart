import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T08
import '../../../core/sync/offline_toggle_queue.dart'; // MG_T09
import '../../../core/cache/shopping_cache.dart'; // MG_CACHE
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
  // MG_T08/MG_T09: offline toggle support. The queue + connectivity listener
  // now live in a global, app-lifetime OfflineToggleQueue so pending toggles
  // survive leaving the shopping tab; this bloc only enqueues + resyncs.
  final ConnectivityCubit? connectivity;
  final OfflineToggleQueue? offlineQueue; // MG_T09
  final ShoppingCache? cache; // MG_CACHE
  StreamSubscription<int>? _flushedSub; // MG_T09

  ShoppingBloc({
    required this.apiClient,
    this.connectivity, // MG_T08
    this.offlineQueue, // MG_T09
    this.cache, // MG_CACHE
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
    // MG_T09: resync the open list whenever the global queue flushes it.
    _flushedSub = offlineQueue?.flushedListIds.listen((listId) {
      final cur = state;
      if (cur is ShoppingDetailLoaded && cur.detail.id == listId) {
        add(ShoppingDetailRequested(listId));
      }
    });
    // MG_T09: best-effort flush on (re)entry in case connectivity is back.
    offlineQueue?.flush();
  }

  Map<String, dynamic> _asMap(dynamic d) =>
      d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};

  // MG_CACHE: offline = network ApiException or offline connectivity.
  bool _isOffline(Object err) =>
      (err is ApiException && err.isNetwork) ||
      connectivity?.state == ConnectivityStatus.offline;

  // MG_CACHE2: overlay still-queued offline toggles onto a fresh server
  // response so an un-synced toggle isn't reverted by the GET.
  void _applyPending(int listId, Map<String, dynamic> m) {
    final pending = offlineQueue?.pendingForList(listId);
    if (pending == null || pending.isEmpty) return;
    final items = m['items'];
    if (items is List) {
      for (final it in items) {
        if (it is Map && pending.containsKey(it['id'])) {
          it['is_purchased'] = pending[it['id']];
        }
      }
    }
  }

  bool _archived = false;

  Future<void> _reloadLists(Emitter<ShoppingState> emit) async {
    final raw = await apiClient.get('/shopping/lists/',
        params: _archived ? {'archived': 'true'} : null);
    final rawList = (raw is List ? raw : const []);
    await cache?.saveLists(_archived, rawList); // MG_CACHE write-through
    final list = rawList
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
      // MG_CACHE: offline -> serve cached lists if present.
      final cached = cache?.readLists(_archived);
      if (_isOffline(err) && cached != null) {
        emit(ShoppingListsLoaded(
          lists: cached.map(ShoppingListBrief.fromJson).toList(),
          archived: _archived,
        ));
      } else {
        emit(ShoppingError(_msg(err)));
      }
    }
  }

  Future<void> _onDetail(
      ShoppingDetailRequested e, Emitter<ShoppingState> emit) async {
    emit(const ShoppingLoading());
    try {
      final raw = await apiClient.get('/shopping/lists/${e.listId}/');
      final m = _asMap(raw);
      _applyPending(e.listId, m); // MG_CACHE2: keep unsynced toggles
      await cache?.saveDetail(e.listId, m); // MG_CACHE write-through
      emit(ShoppingDetailLoaded(ShoppingListDetail.fromJson(m)));
    } catch (err) {
      // MG_CACHE: offline -> serve cached detail if present.
      final cached = cache?.readDetail(e.listId);
      if (_isOffline(err) && cached != null) {
        emit(ShoppingDetailLoaded(ShoppingListDetail.fromJson(cached)));
      } else {
        emit(ShoppingError(_msg(err)));
      }
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
              // MG_SHOP2FRIDGE: removing from fridge clears the in_fridge flag.
              ? it.copyWith(
                  isPurchased: e.isPurchased,
                  inFridge: e.removeFromFridge ? false : null,
                )
              : it)
          .toList();
      emit(ShoppingDetailLoaded(cur.detail.copyWith(items: items)));
    }
    if (connectivity?.state == ConnectivityStatus.offline) {
      await cache?.patchDetailItemPurchased(
          e.listId, e.itemId, e.isPurchased); // MG_CACHE
      offlineQueue?.enqueue(e.listId, e.itemId, e.isPurchased); // MG_T09
      return;
    }
    try {
      await apiClient.patch(
          '/shopping/lists/${e.listId}/items/${e.itemId}/toggle/',
          data: {
            'is_purchased': e.isPurchased,
            if (e.removeFromFridge) 'remove_from_fridge': true, // MG_SHOP2FRIDGE
          });
      // MG_SHOP2FRIDGE: refresh so fridge state / totals reflect the removal.
      if (e.removeFromFridge) add(ShoppingDetailRequested(e.listId));
    } on ApiException catch (err) {
      if (err.isNetwork) {
        await cache?.patchDetailItemPurchased(
            e.listId, e.itemId, e.isPurchased); // MG_CACHE
        offlineQueue?.enqueue(e.listId, e.itemId, e.isPurchased); // MG_T09
      } else {
        emit(ShoppingError(err.message));
      }
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

  // MG_T09: only cancel our flushed-list subscription. The offline queue and
  // its pending counter are global and must outlive this bloc.
  @override
  Future<void> close() {
    _flushedSub?.cancel();
    return super.close();
  }
}

