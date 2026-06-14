// MG_T09: app-lifetime offline toggle queue.
//
// Holds the in-memory LWW toggle queue and the connectivity listener at the
// app root so queued offline toggles survive leaving the shopping tab (the
// ShoppingBloc is per-tab and used to drop the queue on close). Feeds the
// global PendingSyncCubit counter and notifies listeners which list was
// resynced after a flush.
import 'dart:async';

import '../api/api_client.dart';
import '../connectivity/connectivity_cubit.dart';
import 'pending_sync_cubit.dart';

class _PendingToggle {
  final int listId;
  final int itemId;
  final bool isPurchased;
  _PendingToggle(this.listId, this.itemId, this.isPurchased);
}

class OfflineToggleQueue {
  final ApiClient apiClient;
  final ConnectivityCubit connectivity;
  final PendingSyncCubit pendingSync;

  final Map<String, _PendingToggle> _queue = {}; // 'listId:itemId' -> latest
  final StreamController<int> _flushed = StreamController<int>.broadcast();
  StreamSubscription<ConnectivityStatus>? _sub;
  bool _flushing = false;

  /// Emits a listId whenever its queued toggles were just flushed to the server.
  Stream<int> get flushedListIds => _flushed.stream;

  bool get isOffline => connectivity.state == ConnectivityStatus.offline;

  OfflineToggleQueue({
    required this.apiClient,
    required this.connectivity,
    required this.pendingSync,
  }) {
    _sub = connectivity.stream.listen((s) {
      if (s == ConnectivityStatus.online) flush();
    });
  }

  /// Record the final desired state for an item (LWW per item).
  void enqueue(int listId, int itemId, bool isPurchased) {
    _queue['$listId:$itemId'] = _PendingToggle(listId, itemId, isPurchased);
    pendingSync.set(_queue.length);
  }

  /// Push queued toggles to the server; emit each touched listId on success.
  Future<void> flush() async {
    if (_flushing) return;
    if (connectivity.state == ConnectivityStatus.offline) return;
    if (_queue.isEmpty) return;
    _flushing = true;
    final touched = <int>{};
    try {
      for (final k in _queue.keys.toList()) {
        final t = _queue[k];
        if (t == null) continue;
        try {
          await apiClient.patch(
              '/shopping/lists/${t.listId}/items/${t.itemId}/toggle/',
              data: {'is_purchased': t.isPurchased});
          if (identical(_queue[k], t)) _queue.remove(k); // keep if superseded
          touched.add(t.listId);
        } catch (_) {
          break; // still offline / failed -> keep the rest for next reconnect
        }
      }
    } finally {
      pendingSync.set(_queue.length);
      _flushing = false;
      if (!_flushed.isClosed) {
        for (final id in touched) {
          _flushed.add(id);
        }
      }
    }
  }

  Future<void> dispose() async {
    await _sub?.cancel();
    await _flushed.close();
  }
}
