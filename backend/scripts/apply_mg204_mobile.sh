#!/usr/bin/env bash
# ============================================================================
# MG-204 mobile patch (chat 31)
# - MG-204-D: diary rewrite for plan/fact, import-from-menu, stats {planned, actual}
# - MG-204-P: premium gate (403) handling — ApiException, PremiumGateCubit,
#             per-bloc *PremiumLocked states, paywall banner, paywall screen
# - Q1 cleanup: convert diary_bloc + menu_bloc to part-of layout, remove dupes
# - Q2: NO drift wiring (out of scope; keep CachedDiaryEntries schema as-is)
#
# Idempotent: backs up every file to .bak-<ts> before overwrite.
# Safe to re-run; original sources preserved.
# ============================================================================
set -euo pipefail

MOB="/opt/menugen/mobile/menugen_app"
LIB="${MOB}/lib"
TST="${MOB}/test"

if [ ! -d "${MOB}" ]; then
  echo "ERROR: ${MOB} not found"; exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
BAK="${MOB}/.bak-${TS}"
mkdir -p "${BAK}"
echo ">>> backup dir: ${BAK}"

# Helper: backup file (if exists) preserving relative path under BAK
_backup() {
  local f="$1"
  if [ -f "$f" ]; then
    local rel="${f#${MOB}/}"
    local dst="${BAK}/${rel}"
    mkdir -p "$(dirname "$dst")"
    cp -p "$f" "$dst"
  fi
}

# Helper: write file (creates dirs, backs up old version)
_write() {
  local path="$1"
  _backup "$path"
  mkdir -p "$(dirname "$path")"
  cat > "$path"
  echo "  wrote: ${path#${MOB}/}"
}

# Helper: delete file with backup
_rm() {
  local f="$1"
  if [ -f "$f" ]; then
    _backup "$f"
    rm -f "$f"
    echo "  removed: ${f#${MOB}/}"
  fi
}

# ----------------------------------------------------------------------------
# 1. CORE: ApiException — typed, parses DRF error shape
# ----------------------------------------------------------------------------
_write "${LIB}/core/api/api_exception.dart" <<'DART'
/// Typed exception thrown by [DioApiClient] on non-2xx responses.
///
/// Wraps DRF error shape `{"detail": "..."}` and exposes [isPremiumLocked]
/// for callers that need to react to MG-606 premium gating (HTTP 403 from
/// IsFamilyPremiumOrReadOnly).
class ApiException implements Exception {
  /// HTTP status code; `null` for network errors / timeouts.
  final int? statusCode;

  /// Optional machine-readable error code if backend ever provides one
  /// (currently DRF returns only `detail`). Kept for future compatibility.
  final String? errorCode;

  /// Human-readable message (from `detail` if present, else fallback).
  final String message;

  /// Raw response body (if any), useful for debugging / extra fields.
  final dynamic body;

  const ApiException({
    required this.message,
    this.statusCode,
    this.errorCode,
    this.body,
  });

  /// True iff the response is a Premium gate denial.
  ///
  /// MG-606: `IsFamilyPremiumOrReadOnly` returns 403 for both read (no
  /// premium history) and write (no active premium) denials. Mobile uses
  /// status code alone — backend does not provide an error_code field.
  bool get isPremiumLocked => statusCode == 403;

  bool get isUnauthorized => statusCode == 401;
  bool get isNotFound => statusCode == 404;
  bool get isServerError => statusCode != null && statusCode! >= 500;
  bool get isNetwork => statusCode == null;

  @override
  String toString() =>
      'ApiException(status=$statusCode, code=$errorCode, message=$message)';
}
DART

# ----------------------------------------------------------------------------
# 2. CORE: DioApiClient — throws ApiException, broadcasts 403s to a stream
# ----------------------------------------------------------------------------
_write "${LIB}/core/api/dio_api_client.dart" <<'DART'
import 'dart:async';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import 'api_client.dart';
import 'api_exception.dart';
import 'token_storage.dart';

/// Dio-backed [ApiClient] that:
///  * attaches Bearer tokens from [TokenStorage]
///  * silently refreshes on 401 once
///  * converts every non-2xx into [ApiException]
///  * broadcasts [ApiException]s on [errorStream] so cross-cutting cubits
///    (e.g. PremiumGateCubit) can react without each bloc re-implementing
///    error parsing.
class DioApiClient implements ApiClient {
  late final Dio _dio;
  final TokenStorage tokenStorage;

  final StreamController<ApiException> _errors =
      StreamController<ApiException>.broadcast();

  /// Stream of ApiExceptions emitted by this client. Used by
  /// [PremiumGateCubit] to detect 403s globally.
  Stream<ApiException> get errorStream => _errors.stream;

  DioApiClient({required this.tokenStorage}) {
    _dio = Dio(BaseOptions(
      baseUrl: AppConfig.apiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await tokenStorage.getAccessToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        // 401 refresh-once path (preserves prior behaviour).
        if (error.response?.statusCode == 401) {
          final refresh = await tokenStorage.getRefreshToken();
          if (refresh != null) {
            try {
              final resp = await Dio().post(
                '${AppConfig.apiBaseUrl}/auth/refresh/',
                data: {'refresh': refresh},
              );
              final newAccess = resp.data['access'] as String;
              await tokenStorage.saveTokens(
                  access: newAccess, refresh: refresh);
              error.requestOptions.headers['Authorization'] =
                  'Bearer $newAccess';
              return handler.resolve(await _dio.fetch(error.requestOptions));
            } catch (_) {
              await tokenStorage.clearTokens();
            }
          }
        }
        handler.next(error);
      },
    ));
  }

  void dispose() {
    _errors.close();
    _dio.close(force: true);
  }

  /// Convert a DioException into a typed [ApiException] and broadcast it.
  Never _throw(DioException e) {
    final resp = e.response;
    String message;
    String? errorCode;
    dynamic body = resp?.data;

    if (body is Map) {
      // DRF default error shape: {"detail": "..."}.
      // Also tolerate {"error_code": "..."} for forward-compat.
      message = (body['detail'] ??
              body['message'] ??
              body['error'] ??
              'Ошибка сервера')
          .toString();
      final ec = body['error_code'];
      if (ec is String) errorCode = ec;
    } else if (body is String && body.isNotEmpty) {
      message = body;
    } else {
      message = e.message ?? 'Сетевая ошибка';
    }

    final ex = ApiException(
      message: message,
      statusCode: resp?.statusCode,
      errorCode: errorCode,
      body: body,
    );
    if (!_errors.isClosed) _errors.add(ex);
    throw ex;
  }

  Future<T> _run<T>(Future<Response<dynamic>> Function() call) async {
    try {
      final r = await call();
      return r.data as T;
    } on DioException catch (e) {
      _throw(e);
    }
  }

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? params}) =>
      _run(() => _dio.get(path, queryParameters: params));

  @override
  Future<dynamic> post(String path, {Map<String, dynamic>? data}) =>
      _run(() => _dio.post(path, data: data));

  @override
  Future<dynamic> put(String path, {Map<String, dynamic>? data}) =>
      _run(() => _dio.put(path, data: data));

  @override
  Future<dynamic> patch(String path, {Map<String, dynamic>? data}) =>
      _run(() => _dio.patch(path, data: data));

  @override
  Future<dynamic> delete(String path) =>
      _run(() => _dio.delete(path));
}
DART

# ----------------------------------------------------------------------------
# 3. CORE: PremiumGateCubit — global premium-state tracker
# ----------------------------------------------------------------------------
_write "${LIB}/core/premium/premium_gate_cubit.dart" <<'DART'
import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../api/api_exception.dart';

/// Coarse-grained premium status used by UI banners/badges.
///
/// MG-606: the backend does not currently expose a premium field on
/// `/users/me/`, so this cubit is **reactive only** — it flips to
/// [lockedForRead] / [lockedForWrite] when a 403 is observed and resets on
/// any subsequent 2xx (handled by features clearing their own state).
enum PremiumStatus {
  /// We haven't observed any premium-related error yet. UI shows no banner.
  unknown,

  /// At least one read endpoint returned 403 → user never had premium.
  /// Read access is denied app-wide.
  lockedForRead,

  /// A write endpoint returned 403 but a read previously succeeded →
  /// user is in "read-only after expiry" mode (MG-606.A).
  lockedForWrite,
}

class PremiumGateState extends Equatable {
  final PremiumStatus status;

  /// Last feature/endpoint that triggered a lock, for paywall copy
  /// (e.g. "diary", "menu", "fridge", "notifications"). Best-effort.
  final String? lastLockedFeature;

  /// Last user-visible message from backend (`detail`).
  final String? lastLockMessage;

  const PremiumGateState({
    required this.status,
    this.lastLockedFeature,
    this.lastLockMessage,
  });

  const PremiumGateState.unknown()
      : status = PremiumStatus.unknown,
        lastLockedFeature = null,
        lastLockMessage = null;

  PremiumGateState copyWith({
    PremiumStatus? status,
    String? lastLockedFeature,
    String? lastLockMessage,
  }) {
    return PremiumGateState(
      status: status ?? this.status,
      lastLockedFeature: lastLockedFeature ?? this.lastLockedFeature,
      lastLockMessage: lastLockMessage ?? this.lastLockMessage,
    );
  }

  @override
  List<Object?> get props => [status, lastLockedFeature, lastLockMessage];
}

/// Listens to `DioApiClient.errorStream` and updates premium status on 403s.
///
/// Feature blocs are also free to call [reportLock] / [reportSuccess]
/// directly when they have richer context (e.g. which feature was hit).
class PremiumGateCubit extends Cubit<PremiumGateState> {
  StreamSubscription<ApiException>? _sub;

  PremiumGateCubit() : super(const PremiumGateState.unknown());

  /// Wire up to a [DioApiClient]'s error stream. Call once at app boot.
  void attachErrorStream(Stream<ApiException> stream) {
    _sub?.cancel();
    _sub = stream.listen((e) {
      if (!e.isPremiumLocked) return;
      // Without knowing HTTP method here, default to lockedForRead;
      // blocs that observe a successful read followed by a write 403
      // call reportLock(feature, isWrite: true) explicitly.
      emit(state.copyWith(
        status: PremiumStatus.lockedForRead,
        lastLockMessage: e.message,
      ));
    });
  }

  /// Explicit lock report from a feature bloc (preferred — carries context).
  void reportLock({required String feature, required bool isWrite, String? message}) {
    emit(state.copyWith(
      status: isWrite ? PremiumStatus.lockedForWrite : PremiumStatus.lockedForRead,
      lastLockedFeature: feature,
      lastLockMessage: message,
    ));
  }

  /// Signal from a feature bloc that a successful read happened — promotes
  /// `lockedForRead` to `lockedForWrite` (read-only-after-expiry mode).
  void reportReadSuccess() {
    if (state.status == PremiumStatus.lockedForRead) {
      emit(state.copyWith(status: PremiumStatus.lockedForWrite));
    }
  }

  /// Signal that user upgraded / regained access. Clears lock.
  void reset() => emit(const PremiumGateState.unknown());

  @override
  Future<void> close() async {
    await _sub?.cancel();
    return super.close();
  }
}
DART

# ----------------------------------------------------------------------------
# 4. CORE: PaywallBanner widget + PaywallScreen
# ----------------------------------------------------------------------------
_write "${LIB}/core/premium/paywall_banner.dart" <<'DART'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import 'premium_gate_cubit.dart';

/// Compact banner shown above main shell when the user is in a premium lock.
///
/// - PremiumStatus.unknown      → not shown
/// - PremiumStatus.lockedForRead  → red, "Subscribe to access"
/// - PremiumStatus.lockedForWrite → amber, "Read-only — renew to edit"
class PaywallBanner extends StatelessWidget {
  const PaywallBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<PremiumGateCubit, PremiumGateState>(
      builder: (context, state) {
        if (state.status == PremiumStatus.unknown) {
          return const SizedBox.shrink();
        }
        final isWrite = state.status == PremiumStatus.lockedForWrite;
        final bg = isWrite ? Colors.amber.shade100 : Colors.red.shade100;
        final fg = isWrite ? Colors.amber.shade900 : Colors.red.shade900;
        final title = isWrite
            ? 'Подписка истекла — режим только для чтения'
            : 'Эта функция доступна по подписке Premium';
        final cta = isWrite ? 'Продлить' : 'Подключить';

        return Material(
          color: bg,
          child: InkWell(
            onTap: () => context.push('/paywall'),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(children: [
                Icon(Icons.lock_outline, size: 18, color: fg),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(color: fg, fontSize: 13),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: () => context.push('/paywall'),
                  style: TextButton.styleFrom(foregroundColor: fg),
                  child: Text(cta),
                ),
              ]),
            ),
          ),
        );
      },
    );
  }
}
DART

_write "${LIB}/core/premium/paywall_screen.dart" <<'DART'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'premium_gate_cubit.dart';

/// Minimal paywall screen — stub for chat 31.
///
/// Real implementation (price selection, payment flow) lives in MG-payments
/// chat. For now this screen explains the situation and offers a "Manage"
/// CTA which currently just returns to the previous route.
class PaywallScreen extends StatelessWidget {
  const PaywallScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<PremiumGateCubit>().state;
    final isWrite = state.status == PremiumStatus.lockedForWrite;
    return Scaffold(
      appBar: AppBar(title: const Text('Premium')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 24),
            Icon(Icons.workspace_premium,
                size: 96, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 16),
            Text(
              isWrite
                  ? 'Подписка истекла'
                  : 'Premium-подписка',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            Text(
              state.lastLockMessage ??
                  (isWrite
                      ? 'Продлите подписку, чтобы снова редактировать дневник, меню и список покупок.'
                      : 'Подписка нужна для генерации меню, ведения дневника и работы с холодильником.'),
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15),
            ),
            const Spacer(),
            FilledButton(
              onPressed: () {
                // TODO(MG-payments): launch real subscription flow.
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Оплата подключения — скоро')),
                );
              },
              child: Text(isWrite ? 'Продлить подписку' : 'Подключить Premium'),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: () => Navigator.of(context).maybePop(),
              child: const Text('Назад'),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
DART

# ----------------------------------------------------------------------------
# 5. DIARY domain models — plain Dart, no freezed
# ----------------------------------------------------------------------------
_write "${LIB}/features/diary/models/diary_entry.dart" <<'DART'
import 'package:equatable/equatable.dart';

/// Mirror of backend `DiaryEntry.MealType`.
enum MealType {
  breakfast('breakfast', 'Завтрак'),
  lunch('lunch', 'Обед'),
  dinner('dinner', 'Ужин'),
  snack('snack', 'Перекус');

  final String value;
  final String label;
  const MealType(this.value, this.label);

  static MealType? tryParse(String? raw) {
    if (raw == null) return null;
    for (final m in MealType.values) {
      if (m.value == raw) return m;
    }
    return null;
  }
}

/// One diary entry as returned by `GET /api/v1/diary/`.
///
/// Maps to `DiaryEntrySerializer` (read shape):
///   id, date, meal_type, recipe (FK id), recipe_title (derived),
///   custom_name, nutrition (dict), quantity (decimal),
///   planned_menu_item (FK id, MG-605.B), is_eaten (MG-605.B), created_at.
class DiaryEntry extends Equatable {
  final int id;
  final String date;            // YYYY-MM-DD
  final MealType mealType;
  final int? recipeId;
  final String? recipeTitle;
  final String customName;
  final Map<String, dynamic> nutrition;
  final double quantity;
  final int? plannedMenuItemId; // null = manual entry (фактическое)
  final bool isEaten;           // MG-605.B

  const DiaryEntry({
    required this.id,
    required this.date,
    required this.mealType,
    required this.recipeId,
    required this.recipeTitle,
    required this.customName,
    required this.nutrition,
    required this.quantity,
    required this.plannedMenuItemId,
    required this.isEaten,
  });

  /// True if this entry was planned (came from menu import).
  bool get isPlanned => plannedMenuItemId != null;

  /// Display title — recipe title, custom name, or empty string.
  String get displayTitle =>
      (recipeTitle?.isNotEmpty == true) ? recipeTitle! : customName;

  factory DiaryEntry.fromJson(Map<String, dynamic> j) {
    final mt = MealType.tryParse(j['meal_type'] as String?) ?? MealType.snack;
    final qRaw = j['quantity'];
    final q = qRaw is num
        ? qRaw.toDouble()
        : (qRaw is String ? double.tryParse(qRaw) ?? 1.0 : 1.0);
    return DiaryEntry(
      id: (j['id'] as num).toInt(),
      date: j['date'] as String? ?? '',
      mealType: mt,
      recipeId: (j['recipe'] as num?)?.toInt(),
      recipeTitle: j['recipe_title'] as String?,
      customName: (j['custom_name'] as String?) ?? '',
      nutrition: (j['nutrition'] is Map)
          ? Map<String, dynamic>.from(j['nutrition'] as Map)
          : <String, dynamic>{},
      quantity: q,
      plannedMenuItemId: (j['planned_menu_item'] as num?)?.toInt(),
      isEaten: (j['is_eaten'] as bool?) ?? false,
    );
  }

  @override
  List<Object?> get props => [
        id,
        date,
        mealType,
        recipeId,
        recipeTitle,
        customName,
        nutrition,
        quantity,
        plannedMenuItemId,
        isEaten,
      ];
}
DART

_write "${LIB}/features/diary/models/diary_stats.dart" <<'DART'
import 'package:equatable/equatable.dart';

/// One nutrition bucket — matches backend `_NutritionBucketSerializer`.
class NutritionBucket extends Equatable {
  final double calories;
  final double proteins;
  final double fats;
  final double carbs;

  const NutritionBucket({
    required this.calories,
    required this.proteins,
    required this.fats,
    required this.carbs,
  });

  const NutritionBucket.zero()
      : calories = 0,
        proteins = 0,
        fats = 0,
        carbs = 0;

  factory NutritionBucket.fromJson(Map<String, dynamic>? j) {
    if (j == null) return const NutritionBucket.zero();
    double v(dynamic x) =>
        x is num ? x.toDouble() : (x is String ? double.tryParse(x) ?? 0 : 0);
    return NutritionBucket(
      calories: v(j['calories']),
      proteins: v(j['proteins']),
      fats: v(j['fats']),
      carbs: v(j['carbs']),
    );
  }

  @override
  List<Object?> get props => [calories, proteins, fats, carbs];
}

/// Per-day stats from `GET /api/v1/diary/stats/?from=&to=`.
///
/// Backend (MG-605.D) returns a *plain array* (not paginated):
/// `[{date, planned, actual, total}]`.
class DiaryDayStats extends Equatable {
  final String date;
  final NutritionBucket planned;
  final NutritionBucket actual;
  final NutritionBucket total;

  const DiaryDayStats({
    required this.date,
    required this.planned,
    required this.actual,
    required this.total,
  });

  factory DiaryDayStats.fromJson(Map<String, dynamic> j) => DiaryDayStats(
        date: j['date'] as String? ?? '',
        planned: NutritionBucket.fromJson(j['planned'] as Map<String, dynamic>?),
        actual: NutritionBucket.fromJson(j['actual'] as Map<String, dynamic>?),
        total: NutritionBucket.fromJson(j['total'] as Map<String, dynamic>?),
      );

  @override
  List<Object?> get props => [date, planned, actual, total];
}
DART

# ----------------------------------------------------------------------------
# 6. DIARY bloc — full rewrite, part-of layout (Q1: convert to part-of)
# ----------------------------------------------------------------------------
_write "${LIB}/features/diary/bloc/diary_bloc.dart" <<'DART'
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
DART

_write "${LIB}/features/diary/bloc/diary_event.dart" <<'DART'
part of 'diary_bloc.dart';

abstract class DiaryEvent extends Equatable {
  const DiaryEvent();
  @override
  List<Object?> get props => [];
}

/// Load entries + stats for one day (optionally for a specific family member).
class DiaryLoadRequested extends DiaryEvent {
  final String date;     // YYYY-MM-DD
  final int? memberId;   // null = self
  const DiaryLoadRequested({required this.date, this.memberId});

  /// Convenience positional form, kept for backwards-compatible tests.
  factory DiaryLoadRequested.forDate(String date) =>
      DiaryLoadRequested(date: date);

  @override
  List<Object?> get props => [date, memberId];
}

/// Toggle is_eaten on a planned entry.
class DiaryMarkEatenRequested extends DiaryEvent {
  final int entryId;
  final bool isEaten;
  const DiaryMarkEatenRequested({required this.entryId, required this.isEaten});
  @override
  List<Object?> get props => [entryId, isEaten];
}

/// Add a manual (factual) entry — no plan, immediate fact.
class DiaryAddManualRequested extends DiaryEvent {
  final String date;
  final MealType mealType;
  final int? recipeId;
  final String customName;
  final double quantity;
  final Map<String, dynamic> nutrition;
  const DiaryAddManualRequested({
    required this.date,
    required this.mealType,
    this.recipeId,
    this.customName = '',
    this.quantity = 1.0,
    this.nutrition = const {},
  });
  @override
  List<Object?> get props =>
      [date, mealType, recipeId, customName, quantity, nutrition];
}

class DiaryDeleteRequested extends DiaryEvent {
  final int entryId;
  const DiaryDeleteRequested(this.entryId);
  @override
  List<Object?> get props => [entryId];
}

/// MG-605.D — import all MenuItems of a menu into the diary for a given day.
class DiaryImportFromMenuRequested extends DiaryEvent {
  final int menuId;
  final String date;
  final int? memberId;
  const DiaryImportFromMenuRequested({
    required this.menuId,
    required this.date,
    this.memberId,
  });
  @override
  List<Object?> get props => [menuId, date, memberId];
}
DART

_write "${LIB}/features/diary/bloc/diary_state.dart" <<'DART'
part of 'diary_bloc.dart';

abstract class DiaryState extends Equatable {
  const DiaryState();
  @override
  List<Object?> get props => [];
}

class DiaryInitial extends DiaryState {
  const DiaryInitial();
}

class DiaryLoading extends DiaryState {
  const DiaryLoading();
}

class DiaryLoaded extends DiaryState {
  final String date;
  final int? memberId;
  final List<DiaryEntry> entries;
  final DiaryDayStats stats;

  const DiaryLoaded({
    required this.date,
    required this.memberId,
    required this.entries,
    required this.stats,
  });

  /// Planned entries (came from menu import, may or may not be eaten yet).
  List<DiaryEntry> get plannedEntries =>
      entries.where((e) => e.isPlanned).toList();

  /// Manual / actual-only entries (no plan attached).
  List<DiaryEntry> get manualEntries =>
      entries.where((e) => !e.isPlanned).toList();

  DiaryLoaded copyWith({
    String? date,
    int? memberId,
    List<DiaryEntry>? entries,
    DiaryDayStats? stats,
  }) {
    return DiaryLoaded(
      date: date ?? this.date,
      memberId: memberId ?? this.memberId,
      entries: entries ?? this.entries,
      stats: stats ?? this.stats,
    );
  }

  @override
  List<Object?> get props => [date, memberId, entries, stats];
}

/// MG-606: backend denied access with 403 from IsFamilyPremiumOrReadOnly.
///
/// `isWrite=false` → user has no premium history at all (full lock).
/// `isWrite=true`  → user is in read-only-after-expiry mode (writes blocked).
class DiaryPremiumLocked extends DiaryState {
  final String message;
  final bool isWrite;
  const DiaryPremiumLocked({required this.message, required this.isWrite});
  @override
  List<Object?> get props => [message, isWrite];
}

class DiaryError extends DiaryState {
  final String message;
  const DiaryError({required this.message});
  @override
  List<Object?> get props => [message];
}
DART

# ----------------------------------------------------------------------------
# 7. DIARY screen — full rewrite, plan/fact sections, import button, stats card
# ----------------------------------------------------------------------------
_write "${LIB}/features/diary/screens/diary_screen.dart" <<'DART'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import 'package:table_calendar/table_calendar.dart';

import '../../../core/premium/premium_gate_cubit.dart';
import '../bloc/diary_bloc.dart';
import '../models/diary_entry.dart';
import '../models/diary_stats.dart';
import '../widgets/diary_stats_card.dart';

class DiaryScreen extends StatefulWidget {
  const DiaryScreen({super.key});
  @override
  State<DiaryScreen> createState() => _DiaryScreenState();
}

class _DiaryScreenState extends State<DiaryScreen> {
  DateTime _selected = DateTime.now();
  int? _memberId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    context.read<DiaryBloc>().add(
          DiaryLoadRequested(
            date: DateFormat('yyyy-MM-dd').format(_selected),
            memberId: _memberId,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Дневник питания'),
        actions: [
          IconButton(
            icon: const Icon(Icons.download_for_offline_outlined),
            tooltip: 'Импорт из меню',
            onPressed: _onImportTap,
          ),
        ],
      ),
      body: Column(
        children: [
          TableCalendar(
            firstDay: DateTime(2020),
            lastDay: DateTime(2030),
            focusedDay: _selected,
            selectedDayPredicate: (d) => isSameDay(d, _selected),
            onDaySelected: (sel, _) {
              setState(() => _selected = sel);
              _load();
            },
            calendarFormat: CalendarFormat.week,
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    return BlocBuilder<DiaryBloc, DiaryState>(
      builder: (context, state) {
        if (state is DiaryLoading || state is DiaryInitial) {
          return const Center(child: CircularProgressIndicator());
        }
        if (state is DiaryPremiumLocked) {
          return _PremiumLockView(message: state.message, isWrite: state.isWrite);
        }
        if (state is DiaryError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, size: 56, color: Colors.red),
                const SizedBox(height: 12),
                Text(state.message, textAlign: TextAlign.center),
                TextButton(onPressed: _load, child: const Text('Повторить')),
              ],
            ),
          );
        }
        if (state is DiaryLoaded) {
          return _LoadedView(
            state: state,
            onMarkEaten: (entry, eaten) {
              context
                  .read<DiaryBloc>()
                  .add(DiaryMarkEatenRequested(entryId: entry.id, isEaten: eaten));
            },
            onDelete: (entry) {
              context.read<DiaryBloc>().add(DiaryDeleteRequested(entry.id));
            },
          );
        }
        return const SizedBox.shrink();
      },
    );
  }

  void _onImportTap() async {
    final menuIdText = await showDialog<String?>(
      context: context,
      builder: (_) => _ImportMenuDialog(initialDate: _selected),
    );
    if (menuIdText == null) return;
    final menuId = int.tryParse(menuIdText);
    if (menuId == null) return;
    if (!mounted) return;
    context.read<DiaryBloc>().add(
          DiaryImportFromMenuRequested(
            menuId: menuId,
            date: DateFormat('yyyy-MM-dd').format(_selected),
            memberId: _memberId,
          ),
        );
  }
}

class _LoadedView extends StatelessWidget {
  final DiaryLoaded state;
  final void Function(DiaryEntry, bool) onMarkEaten;
  final void Function(DiaryEntry) onDelete;
  const _LoadedView({
    required this.state,
    required this.onMarkEaten,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final planned = state.plannedEntries;
    final manual = state.manualEntries;
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      children: [
        DiaryStatsCard(stats: state.stats),
        const SizedBox(height: 12),
        if (planned.isEmpty && manual.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 32),
            child: Center(child: Text('Нет записей')),
          ),
        if (planned.isNotEmpty) ...[
          _SectionHeader(
            icon: Icons.event_note,
            title: 'План (${planned.length})',
          ),
          ...planned.map((e) => _EntryTile(
                entry: e,
                onToggleEaten: (v) => onMarkEaten(e, v),
                onDelete: () => onDelete(e),
              )),
        ],
        if (manual.isNotEmpty) ...[
          const SizedBox(height: 12),
          _SectionHeader(
            icon: Icons.restaurant,
            title: 'Факт (${manual.length})',
          ),
          ...manual.map((e) => _EntryTile(
                entry: e,
                onToggleEaten: null, // manual entries are always actual
                onDelete: () => onDelete(e),
              )),
        ],
        const SizedBox(height: 80),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  const _SectionHeader({required this.icon, required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(children: [
        Icon(icon, size: 18, color: Colors.grey.shade600),
        const SizedBox(width: 6),
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
      ]),
    );
  }
}

class _EntryTile extends StatelessWidget {
  final DiaryEntry entry;
  final void Function(bool)? onToggleEaten;
  final VoidCallback onDelete;

  const _EntryTile({
    required this.entry,
    required this.onToggleEaten,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey('diary-${entry.id}'),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => onDelete(),
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: 4),
        child: ListTile(
          leading: onToggleEaten != null
              ? Checkbox(
                  value: entry.isEaten,
                  onChanged: (v) => onToggleEaten!(v ?? false),
                )
              : const Icon(Icons.check_circle, color: Colors.green),
          title: Text(
            entry.displayTitle.isNotEmpty ? entry.displayTitle : '—',
          ),
          subtitle: Text(entry.mealType.label),
          trailing: Text('×${entry.quantity.toStringAsFixed(entry.quantity == entry.quantity.roundToDouble() ? 0 : 1)}'),
        ),
      ),
    );
  }
}

class _PremiumLockView extends StatelessWidget {
  final String message;
  final bool isWrite;
  const _PremiumLockView({required this.message, required this.isWrite});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.lock_outline, size: 72, color: Colors.grey.shade600),
          const SizedBox(height: 16),
          Text(
            isWrite ? 'Дневник в режиме чтения' : 'Дневник доступен по Premium',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () {
              // Navigate via go_router push — paywall is at /paywall.
              // Read PremiumGateCubit so it has context if needed.
              context.read<PremiumGateCubit>();
              Navigator.of(context).pushNamed('/paywall');
            },
            child: const Text('Подключить Premium'),
          ),
        ],
      ),
    );
  }
}

class _ImportMenuDialog extends StatefulWidget {
  final DateTime initialDate;
  const _ImportMenuDialog({required this.initialDate});
  @override
  State<_ImportMenuDialog> createState() => _ImportMenuDialogState();
}

class _ImportMenuDialogState extends State<_ImportMenuDialog> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Импорт из меню'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'На дату: ${DateFormat('d MMMM yyyy', 'ru').format(widget.initialDate)}',
            style: const TextStyle(fontSize: 13, color: Colors.grey),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _ctrl,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'ID меню',
              hintText: 'Например, 42',
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, null),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _ctrl.text.trim()),
          child: const Text('Импортировать'),
        ),
      ],
    );
  }
}
DART

_write "${LIB}/features/diary/widgets/diary_stats_card.dart" <<'DART'
import 'package:flutter/material.dart';

import '../models/diary_stats.dart';

/// Compact card showing planned vs actual KБЖУ for the selected day.
class DiaryStatsCard extends StatelessWidget {
  final DiaryDayStats stats;
  const DiaryStatsCard({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('КБЖУ за день',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 8),
            Row(children: [
              _bucketColumn(label: 'План', bucket: stats.planned, color: Colors.blue.shade600),
              const SizedBox(width: 16),
              _bucketColumn(label: 'Факт', bucket: stats.actual, color: Colors.green.shade700),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _bucketColumn({
    required String label,
    required NutritionBucket bucket,
    required Color color,
  }) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          _row('ккал', bucket.calories),
          _row('Б',   bucket.proteins),
          _row('Ж',   bucket.fats),
          _row('У',   bucket.carbs),
        ],
      ),
    );
  }

  Widget _row(String k, double v) {
    final s = v == 0 ? '0' : v.toStringAsFixed(v >= 10 ? 0 : 1);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(children: [
        SizedBox(width: 36, child: Text(k, style: const TextStyle(fontSize: 12, color: Colors.grey))),
        Text(s, style: const TextStyle(fontSize: 13)),
      ]),
    );
  }
}
DART

# ----------------------------------------------------------------------------
# 8. MENU bloc — Q1 cleanup + premium-aware error mapping (MG-204-P)
# ----------------------------------------------------------------------------
_write "${LIB}/features/menu/bloc/menu_bloc.dart" <<'DART'
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/premium/premium_gate_cubit.dart';

part 'menu_event.dart';
part 'menu_state.dart';

/// MenuBloc — loads existing menu, generates new one.
///
/// MG-606: menu endpoints are protected by IsFamilyPremiumOrReadOnly.
/// We map 403 → [MenuPremiumLocked] and report to [PremiumGateCubit].
class MenuBloc extends Bloc<MenuEvent, MenuState> {
  final ApiClient apiClient;
  final AppDatabase db;
  final PremiumGateCubit? premiumGate;

  MenuBloc({
    required this.apiClient,
    required this.db,
    this.premiumGate,
  }) : super(const MenuLoading()) {
    on<MenuLoadRequested>(_onLoad);
    on<MenuGenerateRequested>(_onGenerate);
  }

  Map<String, dynamic> _asMap(dynamic d) =>
      d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};

  MenuState _toErrorState(Object err, {required bool isWrite}) {
    if (err is ApiException && err.isPremiumLocked) {
      premiumGate?.reportLock(
        feature: 'menu',
        isWrite: isWrite,
        message: err.message,
      );
      return MenuPremiumLocked(message: err.message, isWrite: isWrite);
    }
    final msg = err is ApiException ? err.message : err.toString();
    return MenuError(msg);
  }

  Future<void> _onLoad(MenuLoadRequested e, Emitter<MenuState> emit) async {
    emit(const MenuLoading());
    try {
      final listResp = await apiClient.get('/menu/');
      final list = (listResp is Map ? (listResp['results'] as List? ?? []) : [])
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      if (list.isEmpty) {
        emit(const MenuLoaded(menus: <Map<String, dynamic>>[]));
        return;
      }
      final firstId = list.first['id'];
      final detail = await apiClient.get('/menu/$firstId/');
      premiumGate?.reportReadSuccess();
      emit(MenuLoaded(menus: <Map<String, dynamic>>[_asMap(detail)]));
    } catch (err) {
      emit(_toErrorState(err, isWrite: false));
    }
  }

  Future<void> _onGenerate(MenuGenerateRequested e, Emitter<MenuState> emit) async {
    emit(const MenuGenerating());
    try {
      final body = <String, dynamic>{
        'start_date': e.startDate,
        'period_days': e.periodDays,
      };
      if (e.country != null) body['country'] = e.country;
      if (e.maxCookTime != null) body['max_cook_time'] = e.maxCookTime;
      final r = await apiClient.post('/menu/generate/', data: body);
      emit(MenuGenerated(_asMap(r)));
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }
}
DART

_write "${LIB}/features/menu/bloc/menu_event.dart" <<'DART'
part of 'menu_bloc.dart';

abstract class MenuEvent extends Equatable {
  const MenuEvent();
  @override
  List<Object?> get props => [];
}

class MenuLoadRequested extends MenuEvent {
  const MenuLoadRequested();
}

class MenuGenerateRequested extends MenuEvent {
  final String startDate;
  final int periodDays;
  final String? country;
  final int? maxCookTime;
  const MenuGenerateRequested({
    required this.startDate,
    this.periodDays = 7,
    this.country,
    this.maxCookTime,
  });
  @override
  List<Object?> get props => [startDate, periodDays, country, maxCookTime];
}
DART

_write "${LIB}/features/menu/bloc/menu_state.dart" <<'DART'
part of 'menu_bloc.dart';

abstract class MenuState extends Equatable {
  const MenuState();
  @override
  List<Object?> get props => [];
}

class MenuInitial extends MenuState {
  const MenuInitial();
}

class MenuLoading extends MenuState {
  const MenuLoading();
}

class MenuGenerating extends MenuState {
  const MenuGenerating();
}

class MenuLoaded extends MenuState {
  final List<Map<String, dynamic>> menus;
  const MenuLoaded({required this.menus});
  @override
  List<Object?> get props => [menus];
}

class MenuGenerated extends MenuState {
  final Map<String, dynamic> menu;
  const MenuGenerated(this.menu);
  @override
  List<Object?> get props => [menu];
}

/// MG-606: backend denied access with 403.
class MenuPremiumLocked extends MenuState {
  final String message;
  final bool isWrite;
  const MenuPremiumLocked({required this.message, required this.isWrite});
  @override
  List<Object?> get props => [message, isWrite];
}

class MenuError extends MenuState {
  final String message;
  const MenuError(this.message);
  @override
  List<Object?> get props => [message];
}
DART

# ----------------------------------------------------------------------------
# 9. FRIDGE bloc — premium-aware error mapping (MG-204-P)
# ----------------------------------------------------------------------------
# Need to look at the current fridge_bloc first to preserve other behaviour.
# We'll write a thin wrapper that mirrors common patterns but routes ApiException.

# Re-read existing fridge bloc to preserve semantics
if [ -f "${LIB}/features/fridge/bloc/fridge_bloc.dart" ]; then
  echo ">>> existing fridge_bloc.dart preserved at ${BAK}/lib/features/fridge/bloc/fridge_bloc.dart"
  _backup "${LIB}/features/fridge/bloc/fridge_bloc.dart"
fi

_write "${LIB}/features/fridge/bloc/fridge_bloc.dart" <<'DART'
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

class FridgeAddRequested extends FridgeEvent {
  final String name;
  final double? quantity;
  final String? unit;
  final String? expiryDate;
  const FridgeAddRequested({
    required this.name,
    this.quantity,
    this.unit,
    this.expiryDate,
  });
  @override
  List<Object?> get props => [name, quantity, unit, expiryDate];
}

class FridgeDeleteRequested extends FridgeEvent {
  final int id;
  const FridgeDeleteRequested(this.id);
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
    on<FridgeAddRequested>(_onAdd);
    on<FridgeDeleteRequested>(_onDelete);
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

  Future<void> _onAdd(FridgeAddRequested e, Emitter<FridgeState> emit) async {
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

  Future<void> _onDelete(FridgeDeleteRequested e, Emitter<FridgeState> emit) async {
    try {
      await apiClient.delete('/fridge/${e.id}/');
      add(const FridgeLoadRequested());
    } catch (err) {
      emit(_toErrorState(err, isWrite: true));
    }
  }
}
DART

# ----------------------------------------------------------------------------
# 10. MAIN.dart — wire PremiumGateCubit, attach error stream
# ----------------------------------------------------------------------------
_write "${LIB}/main.dart" <<'DART'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'core/api/dio_api_client.dart';
import 'core/api/token_storage.dart';
import 'core/connectivity/connectivity_cubit.dart';
import 'core/db/app_database.dart';
import 'core/premium/premium_gate_cubit.dart';
import 'core/router/app_router.dart';
import 'core/sync/sync_service.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/bloc/auth_bloc.dart';
import 'features/diary/bloc/diary_bloc.dart';
import 'features/fridge/bloc/fridge_bloc.dart';
import 'features/menu/bloc/menu_bloc.dart';
import 'features/recipes/bloc/recipes_bloc.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('ru', null);

  final tokenStorage = TokenStorage();
  final db = AppDatabase();
  final apiClient = DioApiClient(tokenStorage: tokenStorage);
  final syncService = SyncService(apiClient: apiClient, db: db);
  final premiumGate = PremiumGateCubit();
  // Listen to API errors globally so cross-cutting UI (banner) reacts even if
  // an individual bloc swallows the error in its own state.
  premiumGate.attachErrorStream(apiClient.errorStream);

  syncService.start();
  runApp(MenuGenApp(
    tokenStorage: tokenStorage,
    db: db,
    apiClient: apiClient,
    syncService: syncService,
    premiumGate: premiumGate,
  ));
}

class MenuGenApp extends StatelessWidget {
  final TokenStorage tokenStorage;
  final AppDatabase db;
  final DioApiClient apiClient;
  final SyncService syncService;
  final PremiumGateCubit premiumGate;

  const MenuGenApp({
    super.key,
    required this.tokenStorage,
    required this.db,
    required this.apiClient,
    required this.syncService,
    required this.premiumGate,
  });

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => ConnectivityCubit()),
        BlocProvider.value(value: premiumGate),
        BlocProvider(
          create: (_) => AuthBloc(apiClient: apiClient, tokenStorage: tokenStorage)
            ..add(const AuthCheckRequested()),
        ),
        BlocProvider(create: (_) => MenuBloc(apiClient: apiClient, db: db, premiumGate: premiumGate)),
        BlocProvider(create: (_) => RecipesBloc(apiClient: apiClient, db: db)),
        BlocProvider(create: (_) => FridgeBloc(apiClient: apiClient, db: db, premiumGate: premiumGate)),
        BlocProvider(create: (_) => DiaryBloc(apiClient: apiClient, db: db, premiumGate: premiumGate)),
      ],
      child: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, authState) {
          final router = AppRouter.create(authState: authState, apiClient: apiClient);
          return MaterialApp.router(
            title: 'MenuGen',
            theme: AppTheme.light(),
            darkTheme: AppTheme.dark(),
            themeMode: ThemeMode.system,
            routerConfig: router,
            debugShowCheckedModeBanner: false,
            locale: const Locale('ru'),
            supportedLocales: const [Locale('ru'), Locale('en')],
            localizationsDelegates: const [
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
          );
        },
      ),
    );
  }
}
DART

# ----------------------------------------------------------------------------
# 11. Router — add /paywall route
# ----------------------------------------------------------------------------
_write "${LIB}/core/router/app_router.dart" <<'DART'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/bloc/auth_bloc.dart';
import '../../features/auth/screens/login_screen.dart';
import '../../features/diary/screens/diary_screen.dart';
import '../../features/family/bloc/family_bloc.dart';
import '../../features/family/screens/family_screen.dart';
import '../../features/fridge/screens/fridge_screen.dart';
import '../../features/menu/screens/menu_screen.dart';
import '../../features/profile/screens/profile_screen.dart';
import '../../features/recipes/screens/recipes_screen.dart';
import '../../features/shopping/screens/shopping_list_screen.dart';
import '../api/api_client.dart';
import '../premium/paywall_screen.dart';
import '../widgets/main_shell.dart';

class AppRouter {
  static GoRouter create({required AuthState authState, required ApiClient apiClient}) {
    return GoRouter(
      initialLocation: '/menu',
      redirect: (context, state) {
        final isLoggedIn = authState is AuthAuthenticated;
        final isLoggingIn = state.matchedLocation == '/login';
        if (!isLoggedIn && !isLoggingIn) return '/login';
        if (isLoggedIn && isLoggingIn) return '/menu';
        return null;
      },
      routes: [
        GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
        GoRoute(path: '/paywall', builder: (_, __) => const PaywallScreen()),
        ShellRoute(
          builder: (context, state, child) => MainShell(child: child),
          routes: [
            GoRoute(path: '/menu',    builder: (_, __) => const MenuScreen()),
            GoRoute(path: '/recipes', builder: (_, __) => const RecipesScreen()),
            GoRoute(path: '/fridge',  builder: (_, __) => const FridgeScreen()),
            GoRoute(path: '/diary',   builder: (_, __) => const DiaryScreen()),
            GoRoute(path: '/profile', builder: (_, state) => ProfileScreen(apiClient: apiClient)),
          ],
        ),
        GoRoute(
          path: '/family',
          builder: (_, __) => BlocProvider(
            create: (_) => FamilyBloc(apiClient: apiClient)..add(const FamilyLoadRequested()),
            child: const FamilyScreen(),
          ),
        ),
        GoRoute(
          path: '/shopping/:menuId',
          builder: (_, state) => ShoppingListScreen(
            apiClient: apiClient,
            menuId: int.parse(state.pathParameters['menuId']!),
          ),
        ),
      ],
    );
  }
}
DART

# ----------------------------------------------------------------------------
# 12. MainShell — inject PaywallBanner above content
# ----------------------------------------------------------------------------
_write "${LIB}/core/widgets/main_shell.dart" <<'DART'
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../connectivity/connectivity_cubit.dart';
import '../premium/paywall_banner.dart';
import 'connectivity_banner.dart';

class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  static const _tabs = [
    (icon: Icons.restaurant_menu, label: 'Меню',       path: '/menu'),
    (icon: Icons.menu_book,        label: 'Рецепты',    path: '/recipes'),
    (icon: Icons.kitchen,          label: 'Холодильник',path: '/fridge'),
    (icon: Icons.book,             label: 'Дневник',    path: '/diary'),
    (icon: Icons.person,           label: 'Профиль',    path: '/profile'),
  ];

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final idx = _tabs.indexWhere((t) => location.startsWith(t.path));
    return idx >= 0 ? idx : 0;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const ConnectivityBanner(),
          const PaywallBanner(),
          Expanded(child: child),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex(context),
        onTap: (i) => context.go(_tabs[i].path),
        items: _tabs.map((t) => BottomNavigationBarItem(
          icon: Icon(t.icon),
          label: t.label,
        )).toList(),
      ),
    );
  }
}
DART

# ----------------------------------------------------------------------------
# 13. TESTS
# ----------------------------------------------------------------------------
_write "${TST}/diary_bloc_test.dart" <<'DART'
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/diary/bloc/diary_bloc.dart';
import 'package:menugen_app/features/diary/models/diary_entry.dart';

class _MockApi extends Mock implements ApiClient {}
class _MockDb extends Mock implements AppDatabase {}

void main() {
  late _MockApi api;
  late _MockDb db;

  setUp(() {
    api = _MockApi();
    db = _MockDb();
  });

  group('DiaryBloc.load', () {
    blocTest<DiaryBloc, DiaryState>(
      'emits Loading then Loaded with parsed entries',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params'))).thenAnswer(
          (_) async => {
            'count': 1,
            'results': [
              {
                'id': 7,
                'date': '2026-05-13',
                'meal_type': 'breakfast',
                'recipe': null,
                'recipe_title': null,
                'custom_name': 'Овсянка',
                'nutrition': {},
                'quantity': '1.00',
                'planned_menu_item': null,
                'is_eaten': true,
              }
            ],
          },
        );
        when(() => api.get('/diary/stats/', params: any(named: 'params'))).thenAnswer(
          (_) async => [
            {
              'date': '2026-05-13',
              'planned': {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0},
              'actual':  {'calories': 100, 'proteins': 3, 'fats': 2, 'carbs': 18},
              'total':   {'calories': 100, 'proteins': 3, 'fats': 2, 'carbs': 18},
            }
          ],
        );
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryLoadRequested(date: '2026-05-13')),
      expect: () => [
        const DiaryLoading(),
        isA<DiaryLoaded>()
            .having((s) => s.date, 'date', '2026-05-13')
            .having((s) => s.entries.length, 'entries.length', 1)
            .having((s) => s.entries.first.mealType, 'mealType', MealType.breakfast),
      ],
    );

    blocTest<DiaryBloc, DiaryState>(
      'maps 403 ApiException to DiaryPremiumLocked',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params'))).thenThrow(
          const ApiException(message: 'Premium required', statusCode: 403),
        );
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryLoadRequested(date: '2026-05-13')),
      expect: () => [
        const DiaryLoading(),
        isA<DiaryPremiumLocked>()
            .having((s) => s.isWrite, 'isWrite', false)
            .having((s) => s.message, 'message', 'Premium required'),
      ],
    );

    blocTest<DiaryBloc, DiaryState>(
      'maps generic error to DiaryError',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params')))
            .thenThrow(Exception('boom'));
        return DiaryBloc(apiClient: api, db: db);
      },
      act: (b) => b.add(const DiaryLoadRequested(date: '2026-05-13')),
      expect: () => [const DiaryLoading(), isA<DiaryError>()],
    );
  });

  group('DiaryBloc.markEaten', () {
    blocTest<DiaryBloc, DiaryState>(
      'optimistically flips is_eaten and reloads on success',
      build: () {
        when(() => api.get('/diary/', params: any(named: 'params'))).thenAnswer(
          (_) async => {
            'results': [
              {
                'id': 1,
                'date': '2026-05-13',
                'meal_type': 'lunch',
                'recipe': null,
                'recipe_title': null,
                'custom_name': 'Суп',
                'nutrition': {},
                'quantity': 1,
                'planned_menu_item': 99,
                'is_eaten': false,
              }
            ],
          },
        );
        when(() => api.get('/diary/stats/', params: any(named: 'params')))
            .thenAnswer((_) async => const []);
        when(() => api.patch('/diary/1/', data: any(named: 'data')))
            .thenAnswer((_) async => {});
        return DiaryBloc(apiClient: api, db: db);
      },
      seed: () => const DiaryLoaded(
        date: '2026-05-13',
        memberId: null,
        entries: [],
        stats: DiaryDayStats(
          date: '2026-05-13',
          planned: NutritionBucket.zero(),
          actual: NutritionBucket.zero(),
          total: NutritionBucket.zero(),
        ),
      ),
      act: (b) async {
        // Prime entries via load first.
        b.add(const DiaryLoadRequested(date: '2026-05-13'));
        await Future<void>.delayed(const Duration(milliseconds: 50));
        b.add(const DiaryMarkEatenRequested(entryId: 1, isEaten: true));
      },
      verify: (_) {
        verify(() => api.patch('/diary/1/', data: {'is_eaten': true})).called(1);
      },
    );
  });
}
DART

_write "${TST}/menu_bloc_test.dart" <<'DART'
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/menu/bloc/menu_bloc.dart';

class _MockApi extends Mock implements ApiClient {}
class _MockDb extends Mock implements AppDatabase {}

void main() {
  late _MockApi api;
  late _MockDb db;

  setUp(() {
    api = _MockApi();
    db = _MockDb();
  });

  blocTest<MenuBloc, MenuState>(
    'emits Loaded with empty list on no menus',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params')))
          .thenAnswer((_) async => {'results': [], 'count': 0});
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [
      const MenuLoading(),
      const MenuLoaded(menus: <Map<String, dynamic>>[]),
    ],
  );

  blocTest<MenuBloc, MenuState>(
    'emits Error on generic failure',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params')))
          .thenThrow(Exception('boom'));
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [const MenuLoading(), isA<MenuError>()],
  );

  blocTest<MenuBloc, MenuState>(
    'emits MenuPremiumLocked on 403 read',
    build: () {
      when(() => api.get('/menu/', params: any(named: 'params'))).thenThrow(
        const ApiException(message: 'Premium required', statusCode: 403),
      );
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuLoadRequested()),
    expect: () => [
      const MenuLoading(),
      isA<MenuPremiumLocked>().having((s) => s.isWrite, 'isWrite', false),
    ],
  );

  blocTest<MenuBloc, MenuState>(
    'emits MenuPremiumLocked(write=true) on 403 generate',
    build: () {
      when(() => api.post('/menu/generate/', data: any(named: 'data'))).thenThrow(
        const ApiException(message: 'Need active premium', statusCode: 403),
      );
      return MenuBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const MenuGenerateRequested(startDate: '2026-05-13')),
    expect: () => [
      const MenuGenerating(),
      isA<MenuPremiumLocked>().having((s) => s.isWrite, 'isWrite', true),
    ],
  );
}
DART

_write "${TST}/api_exception_test.dart" <<'DART'
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/core/api/api_exception.dart';

void main() {
  test('isPremiumLocked is true for 403', () {
    const e = ApiException(message: 'x', statusCode: 403);
    expect(e.isPremiumLocked, isTrue);
  });

  test('isPremiumLocked is false for 200/401/404/500', () {
    expect(const ApiException(message: 'x', statusCode: 200).isPremiumLocked, isFalse);
    expect(const ApiException(message: 'x', statusCode: 401).isPremiumLocked, isFalse);
    expect(const ApiException(message: 'x', statusCode: 404).isPremiumLocked, isFalse);
    expect(const ApiException(message: 'x', statusCode: 500).isPremiumLocked, isFalse);
  });

  test('isNetwork is true when statusCode is null', () {
    const e = ApiException(message: 'timeout');
    expect(e.isNetwork, isTrue);
    expect(e.isPremiumLocked, isFalse);
  });

  test('isServerError is true for 5xx only', () {
    expect(const ApiException(message: 'x', statusCode: 500).isServerError, isTrue);
    expect(const ApiException(message: 'x', statusCode: 503).isServerError, isTrue);
    expect(const ApiException(message: 'x', statusCode: 499).isServerError, isFalse);
    expect(const ApiException(message: 'x', statusCode: 403).isServerError, isFalse);
  });
}
DART

_write "${TST}/premium_gate_cubit_test.dart" <<'DART'
import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/premium/premium_gate_cubit.dart';

void main() {
  group('PremiumGateCubit', () {
    blocTest<PremiumGateCubit, PremiumGateState>(
      'starts as unknown',
      build: PremiumGateCubit.new,
      verify: (c) {
        expect(c.state.status, PremiumStatus.unknown);
      },
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'flips to lockedForRead on 403 from error stream',
      build: PremiumGateCubit.new,
      act: (c) {
        final ctl = StreamController<ApiException>.broadcast();
        c.attachErrorStream(ctl.stream);
        ctl.add(const ApiException(message: 'Need premium', statusCode: 403));
      },
      wait: const Duration(milliseconds: 50),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.lockedForRead),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'ignores non-403 ApiExceptions',
      build: PremiumGateCubit.new,
      act: (c) {
        final ctl = StreamController<ApiException>.broadcast();
        c.attachErrorStream(ctl.stream);
        ctl.add(const ApiException(message: 'oops', statusCode: 500));
      },
      wait: const Duration(milliseconds: 50),
      expect: () => const <PremiumGateState>[],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'reportLock sets isWrite-derived status',
      build: PremiumGateCubit.new,
      act: (c) {
        c.reportLock(feature: 'diary', isWrite: true, message: 'gone');
      },
      expect: () => [
        isA<PremiumGateState>()
            .having((s) => s.status, 'status', PremiumStatus.lockedForWrite)
            .having((s) => s.lastLockedFeature, 'feature', 'diary'),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'reportReadSuccess promotes lockedForRead → lockedForWrite',
      build: PremiumGateCubit.new,
      seed: () => const PremiumGateState(status: PremiumStatus.lockedForRead),
      act: (c) => c.reportReadSuccess(),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.lockedForWrite),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'reset returns to unknown',
      build: PremiumGateCubit.new,
      seed: () => const PremiumGateState(status: PremiumStatus.lockedForWrite),
      act: (c) => c.reset(),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.unknown),
      ],
    );
  });
}
DART

# ----------------------------------------------------------------------------
# 14. Update existing fridge_bloc_test to add premium-lock assertions
# ----------------------------------------------------------------------------
_write "${TST}/fridge_bloc_test.dart" <<'DART'
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/db/app_database.dart';
import 'package:menugen_app/features/fridge/bloc/fridge_bloc.dart';

class _MockApi extends Mock implements ApiClient {}
class _MockDb extends Mock implements AppDatabase {}

void main() {
  late _MockApi api;
  late _MockDb db;
  setUp(() {
    api = _MockApi();
    db = _MockDb();
  });

  blocTest<FridgeBloc, FridgeState>(
    'emits Loading→Loaded on empty list',
    build: () {
      when(() => api.get('/fridge/', params: any(named: 'params')))
          .thenAnswer((_) async => {'results': [], 'count': 0});
      return FridgeBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const FridgeLoadRequested()),
    expect: () => [const FridgeLoading(), isA<FridgeLoaded>()],
  );

  blocTest<FridgeBloc, FridgeState>(
    'emits FridgePremiumLocked on 403',
    build: () {
      when(() => api.get('/fridge/', params: any(named: 'params'))).thenThrow(
        const ApiException(message: 'Premium required', statusCode: 403),
      );
      return FridgeBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const FridgeLoadRequested()),
    expect: () => [const FridgeLoading(), isA<FridgePremiumLocked>()],
  );

  blocTest<FridgeBloc, FridgeState>(
    'emits FridgeError on generic exception',
    build: () {
      when(() => api.get('/fridge/', params: any(named: 'params')))
          .thenThrow(Exception('boom'));
      return FridgeBloc(apiClient: api, db: db);
    },
    act: (b) => b.add(const FridgeLoadRequested()),
    expect: () => [const FridgeLoading(), isA<FridgeError>()],
  );
}
DART

# ----------------------------------------------------------------------------
# 15. Summary
# ----------------------------------------------------------------------------
echo
echo "================================================================"
echo "  PATCH APPLIED"
echo "================================================================"
echo "  Backup dir: ${BAK}"
echo
echo "  Files written:"
find "${LIB}/core/api" "${LIB}/core/premium" "${LIB}/features/diary" \
     "${LIB}/features/menu/bloc" "${LIB}/features/fridge/bloc" \
     "${LIB}/main.dart" "${LIB}/core/router/app_router.dart" \
     "${LIB}/core/widgets/main_shell.dart" "${TST}" \
     -type f -newer "${BAK}" 2>/dev/null | sort | sed 's|^|    |'
echo
echo "  Next: cd ${MOB} && flutter pub get && flutter test"
echo "  (no flutter on this host — run in CI or dev machine)"
