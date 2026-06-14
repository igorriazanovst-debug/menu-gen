import 'package:flutter_bloc/flutter_bloc.dart';

/// MG_T08: global count of locally-queued, not-yet-synced changes.
///
/// Surfaced by [SyncIndicator]. In phase 1 only the shopping toggle queue
/// (held in-memory inside ShoppingBloc) feeds this counter; the owning bloc
/// resets its contribution to 0 on close.
class PendingSyncCubit extends Cubit<int> {
  PendingSyncCubit() : super(0);
  void set(int n) => emit(n < 0 ? 0 : n);
}
