import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';
import '../models/diary_entry.dart';
import '../models/diary_stats.dart';

part 'diary_event.dart';
part 'diary_state.dart';

/// Bloc backing the diary screen.
///
/// MG-605.B/C/D + MG-606 mapping:
///  * load        → GET  /diary/?date=&member_id=
///  * stats       → GET  /diary/stats/?from=&to=&member_id=
///  * add planned → not directly exposed; created by import-from-menu
///  * mark eaten  → PATCH /diary/{id}/  body: {is_eaten: true}
///  * unmark      → PATCH /diary/{id}/  body: {is_eaten: false}
///  * add manual  → POST /diary/  body: {date, meal_type, ...}
///  * delete      → DELETE /diary/{id}/
///  * import menu → POST /diary/import-from-menu/?menu_id=&date=&member_id=
///
/// 403 from any of the above maps to [DiaryPremiumLocked] and reports to
/// [PremiumGateCubit] with feature='diary'.
class DiaryBloc extends Bloc<DiaryEvent, DiaryState> {
  final ApiClient apiClient;
  final AppDatabase db;
  final PremiumGateCubit? premiumGate;

  DiaryBloc({
    required this.apiClient,
    required this.db,
    this.premiumGate,
  }) : super(const DiaryInitial()) {
    on<DiaryLoadRequested>(_onLoad);
    on<DiaryMarkEatenRequested>(_onMarkEaten);
    on<DiaryAddManualRequested>(_onAddManual);
    on<DiaryDeleteRequested>(_onDelete);
    on<DiaryImportFromMenuRequested>(_onImportFromMenu);
  }

  // ── helpers ───────────────────────────────────────────────────────────────

  Map<String, dynamic>? _currentMember(DiaryState s) {
    if (s is DiaryLoaded) return null; // member_id is on state, not payload
    return null;
  }

  Map<String, dynamic> _asMap(dynamic d) =>
      d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};

  List<DiaryEntry> _parseEntries(dynamic raw) {
    // GET /diary/ returns paginated {count, next, previous, results}
    // POST /import-from-menu/ returns {created, skipped, entries: [...]}
    final root = _asMap(raw);
    final list = (root['results'] ?? root['entries'] ?? const []) as List;
    return list
        .whereType<Map>()
        .map((e) => DiaryEntry.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  List<DiaryDayStats> _parseStats(dynamic raw) {
    // Stats endpoint returns a plain array.
    if (raw is List) {
      return raw
          .whereType<Map>()
          .map((e) => DiaryDayStats.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }
    return const [];
  }

  /// Centralised error → state mapping. Reports to PremiumGateCubit.
  DiaryState _toErrorState(Object err, {required bool isWrite}) {
    if (err is ApiException && err.isPremiumLocked) {
      premiumGate?.reportLock(
        feature: 'diary',
        isWrite: isWrite,
        message: err.message,
      );
      return DiaryPremiumLocked(
        message: err.message,
        isWrite: isWrite,
      );
    }
    final msg = err is ApiException ? err.message : err.toString();
    return DiaryError(message: msg);
  }

  // ── handlers ──────────────────────────────────────────────────────────────

  Future<void> _onLoad(
    DiaryLoadRequested e,
    Emitter<DiaryState> emit,
  ) async {
    emit(const DiaryLoading());
    try {
      final params = <String, dynamic>{'date': e.date};
      if (e.memberId != null) params['member_id'] = e.memberId;
      final listResp = await apiClient.get('/diary/', params: params);
      final entries = _parseEntries(listResp);

      // Stats for the same day (single-day range).
      final statsParams = <String, dynamic>{'from': e.date, 'to': e.date};
      if (e.memberId != null) statsParams['member_id'] = e.memberId;
      List<DiaryDayStats> stats = const [];
      try {
        final statsResp = await apiClient.get('/diary/stats/', params: statsParams);
        stats = _parseStats(statsResp);
      } catch (_) {
        // Stats failure shouldn't break the screen — best-effort.
      }

      final dayStats = stats.isNotEmpty
          ? stats.first
          : DiaryDayStats(
              date: e.date,
              planned: const NutritionBucket.zero(),
              actual: const NutritionBucket.zero(),
              total: const NutritionBucket.zero(),
            );

      premiumGate?.reportReadSuccess();
      emit(DiaryLoaded(
        date: e.date,
        memberId: e.memberId,
        entries: entries,
        stats: dayStats,
      ));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  Future<void> _onMarkEaten(
    DiaryMarkEatenRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    if (prev is! DiaryLoaded) return;
    // Optimistic UI flip; revert on failure.
    final optimistic = prev.entries
        .map((x) => x.id == e.entryId
            ? DiaryEntry(
                id: x.id,
                date: x.date,
                mealType: x.mealType,
                recipeId: x.recipeId,
                recipeTitle: x.recipeTitle,
                customName: x.customName,
                nutrition: x.nutrition,
                quantity: x.quantity,
                plannedMenuItemId: x.plannedMenuItemId,
                isEaten: e.isEaten,
              )
            : x)
        .toList();
    emit(prev.copyWith(entries: optimistic));
    try {
      await apiClient.patch('/diary/${e.entryId}/', data: {'is_eaten': e.isEaten});
      // Refresh to pull fresh stats; cheap because day-scoped.
      add(DiaryLoadRequested(date: prev.date, memberId: prev.memberId));
    } catch (err) {
      // Revert.
      emit(prev);
      emit(_toErrorState(err, isWrite: true));
    }
  }

  Future<void> _onAddManual(
    DiaryAddManualRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    try {
      final body = <String, dynamic>{
        'date': e.date,
        'meal_type': e.mealType.value,
        'quantity': e.quantity,
        'is_eaten': true, // manual entries are facts by definition
      };
      if (e.recipeId != null) body['recipe'] = e.recipeId;
      if (e.customName.isNotEmpty) body['custom_name'] = e.customName;
      if (e.nutrition.isNotEmpty) body['nutrition'] = e.nutrition;
      await apiClient.post('/diary/', data: body);
      add(DiaryLoadRequested(
        date: e.date,
        memberId: prev is DiaryLoaded ? prev.memberId : null,
      ));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }

  Future<void> _onDelete(
    DiaryDeleteRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    if (prev is! DiaryLoaded) return;
    final filtered = prev.entries.where((x) => x.id != e.entryId).toList();
    emit(prev.copyWith(entries: filtered));
    try {
      await apiClient.delete('/diary/${e.entryId}/');
      add(DiaryLoadRequested(date: prev.date, memberId: prev.memberId));
    } catch (err) {
      emit(prev); // revert
      emit(_toErrorState(err, isWrite: true));
    }
  }

  Future<void> _onImportFromMenu(
    DiaryImportFromMenuRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    try {
      // Backend reads params from query-string; pass via params, not body.
      final params = <String, dynamic>{
        'menu_id': e.menuId,
        'date': e.date,
      };
      if (e.memberId != null) params['member_id'] = e.memberId;
      // Dio doesn't have a post-with-query-only helper, but our ApiClient.post
      // sends body; we encode params into the path manually.
      final qs = params.entries
          .map((kv) => '${kv.key}=${Uri.encodeQueryComponent('${kv.value}')}')
          .join('&');
      await apiClient.post('/diary/import-from-menu/?$qs');
      add(DiaryLoadRequested(
        date: e.date,
        memberId: prev is DiaryLoaded ? prev.memberId : null,
      ));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }
}
