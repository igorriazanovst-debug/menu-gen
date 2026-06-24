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

  /// True if the user has ever had an active premium subscription.
  /// False means "free tier" — reportReadSuccess() must NOT promote to lockedForWrite.
  final bool hasEverPremium;

  /// Last feature/endpoint that triggered a lock, for paywall copy
  /// (e.g. "diary", "menu", "fridge", "notifications"). Best-effort.
  final String? lastLockedFeature;

  /// Last user-visible message from backend (`detail`).
  final String? lastLockMessage;

  const PremiumGateState({
    required this.status,
    this.hasEverPremium = false,
    this.lastLockedFeature,
    this.lastLockMessage,
  });

  const PremiumGateState.unknown()
      : status = PremiumStatus.unknown,
        hasEverPremium = false,
        lastLockedFeature = null,
        lastLockMessage = null;

  PremiumGateState copyWith({
    PremiumStatus? status,
    bool? hasEverPremium,
    String? lastLockedFeature,
    String? lastLockMessage,
  }) {
    return PremiumGateState(
      status: status ?? this.status,
      hasEverPremium: hasEverPremium ?? this.hasEverPremium,
      lastLockedFeature: lastLockedFeature ?? this.lastLockedFeature,
      lastLockMessage: lastLockMessage ?? this.lastLockMessage,
    );
  }

  @override
  List<Object?> get props => [status, hasEverPremium, lastLockedFeature, lastLockMessage];
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
  /// Only applies to users who had premium before (hasEverPremium=true);
  /// free users (never premium) stay in lockedForRead.
  void reportReadSuccess() {
    if (state.status == PremiumStatus.lockedForRead && state.hasEverPremium) {
      emit(state.copyWith(status: PremiumStatus.lockedForWrite));
    }
  }

  /// Signal that user upgraded / regained access. Clears lock.
  void reset() => emit(const PremiumGateState.unknown());

  /// MG-profile-premium: proactive seed from `/users/me/` response.
  ///
  /// Decision matrix from `subscription_status`:
  ///   - null OR is_active_premium=true  → unknown (no banner, full access)
  ///   - has_ever_premium=true && !active → lockedForWrite (read-only)
  ///   - otherwise                        → lockedForRead (no access)
  ///
  /// `trial` counts as is_active_premium=true on backend, so a trial user
  /// sees no banner. When the trial expires without payment,
  /// has_ever_premium stays false → bootstrap will set lockedForRead.
  void bootstrap(Map<String, dynamic>? me) {
    if (me == null) return;
    final raw = me['subscription_status'];
    if (raw == null) {
      emit(const PremiumGateState.unknown());
      return;
    }
    if (raw is! Map) return;
    final s = Map<String, dynamic>.from(raw);
    final isActive = s['is_active_premium'] == true;
    final hasEver = s['has_ever_premium'] == true;

    if (isActive) {
      emit(const PremiumGateState.unknown());
      return;
    }
    if (hasEver) {
      emit(state.copyWith(
        status: PremiumStatus.lockedForWrite,
        hasEverPremium: true,
        lastLockMessage: null,
      ));
      return;
    }
    emit(state.copyWith(
      status: PremiumStatus.lockedForRead,
      hasEverPremium: false,
      lastLockMessage: null,
    ));
  }


  @override
  Future<void> close() async {
    await _sub?.cancel();
    return super.close();
  }
}
