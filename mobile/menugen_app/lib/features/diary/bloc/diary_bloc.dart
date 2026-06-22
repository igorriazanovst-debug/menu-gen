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
    on<DiaryMarkManyEatenRequested>(_onMarkMany);
    on<DiaryAddManualRequested>(_onAddManual);
    on<DiaryDeleteRequested>(_onDelete);
    on<DiaryImportFromMenuRequested>(_onImportFromMenu);
    on<DiaryWaterSetRequested>(_onWaterSet); // DIARY_V2
    on<DiaryCopyRequested>(_onCopy); // DIARY_COPY_V3
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

      // DIARY_V2: water for the day (best-effort).
      int waterMl = 0;
      try {
        final wParams = <String, dynamic>{'date': e.date};
        if (e.memberId != null) wParams['member_id'] = e.memberId;
        final wResp = await apiClient.get('/diary/water/', params: wParams);
        if (wResp is Map && wResp['water_ml'] != null) {
          waterMl = (wResp['water_ml'] as num).toInt();
        }
      } catch (_) {/* non-fatal */}

      premiumGate?.reportReadSuccess();
      emit(DiaryLoaded(
        date: e.date,
        memberId: e.memberId,
        entries: entries,
        stats: dayStats,
        waterMl: waterMl,
      ));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  // MG_SKIN: best-effort day stats fetch (no Loading emit).
  Future<DiaryDayStats?> _fetchStats(String date, int? memberId) async {
    try {
      final p = <String, dynamic>{'from': date, 'to': date};
      if (memberId != null) p['member_id'] = memberId;
      final resp = await apiClient.get('/diary/stats/', params: p);
      final s = _parseStats(resp);
      return s.isNotEmpty ? s.first : null;
    } catch (_) {
      return null;
    }
  }

  // MG_SKIN: PATCH is_eaten tolerant to DRF rate-limit (429). The backend
  // user throttle is modest, and a branch/all toggle fires several writes at
  // once, so we back off and retry instead of failing the whole action.
  Future<void> _patchEaten(int id, bool eaten) async {
    const maxAttempts = 4;
    for (var attempt = 1;; attempt++) {
      try {
        await apiClient.patch('/diary/$id/', data: {'is_eaten': eaten});
        return;
      } catch (err) {
        final throttled = err is ApiException && err.isThrottled;
        if (throttled && attempt < maxAttempts) {
          await Future<void>.delayed(const Duration(milliseconds: 1200));
          continue;
        }
        rethrow;
      }
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
        .map((x) => x.id == e.entryId ? x.copyWith(isEaten: e.isEaten) : x)
        .toList();
    emit(prev.copyWith(entries: optimistic));
    try {
      await _patchEaten(e.entryId, e.isEaten);
      // MG_SKIN: refresh stats in place — NO DiaryLoading, so the list keeps
      // its scroll position on check/uncheck.
      final fresh = await _fetchStats(prev.date, prev.memberId);
      final cur = state;
      if (cur is DiaryLoaded && fresh != null) emit(cur.copyWith(stats: fresh));
    } catch (err) {
      // Revert.
      emit(prev);
      emit(_toErrorState(err, isWrite: true));
    }
  }

  // MG_SKIN: toggle a whole branch / the whole plan at once.
  Future<void> _onMarkMany(
    DiaryMarkManyEatenRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    if (prev is! DiaryLoaded || e.entryIds.isEmpty) return;
    final ids = e.entryIds.toSet();
    final optimistic = prev.entries
        .map((x) => ids.contains(x.id) ? x.copyWith(isEaten: e.isEaten) : x)
        .toList();
    emit(prev.copyWith(entries: optimistic));
    try {
      for (var i = 0; i < e.entryIds.length; i++) {
        await _patchEaten(e.entryIds[i], e.isEaten);
        // Light spacing between writes to avoid bursting the throttle.
        if (i < e.entryIds.length - 1) {
          await Future<void>.delayed(const Duration(milliseconds: 150));
        }
      }
      final fresh = await _fetchStats(prev.date, prev.memberId);
      final cur = state;
      if (cur is DiaryLoaded && fresh != null) emit(cur.copyWith(stats: fresh));
    } catch (err) {
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

  // DIARY_V2: optimistic water set, persist via POST /diary/water/.
  Future<void> _onWaterSet(
    DiaryWaterSetRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    if (prev is DiaryLoaded) {
      emit(prev.copyWith(waterMl: e.waterMl < 0 ? 0 : e.waterMl));
    }
    try {
      await apiClient.post('/diary/water/', data: {
        'date': e.date,
        'water_ml': e.waterMl < 0 ? 0 : e.waterMl,
      });
    } catch (err) {
      if (prev is DiaryLoaded) emit(prev); // revert
      emit(_toErrorState(err, isWrite: true));
    }
  }

  // DIARY_COPY_V3: copy selected entries into target day as plan.
  Future<void> _onCopy(
    DiaryCopyRequested e,
    Emitter<DiaryState> emit,
  ) async {
    final prev = state;
    try {
      final params = <String, dynamic>{};
      if (e.memberId != null) params['member_id'] = e.memberId;
      final qs = params.entries
          .map((kv) => '${kv.key}=${Uri.encodeQueryComponent('${kv.value}')}')
          .join('&');
      final path = qs.isEmpty ? '/diary/copy/' : '/diary/copy/?$qs';
      await apiClient.post(path, data: {
        'entry_ids': e.entryIds,
        'target_date': e.targetDate,
      });
      add(DiaryLoadRequested(
        date: e.targetDate,
        memberId: prev is DiaryLoaded ? prev.memberId : null,
      ));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }

}
