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
      'reportReadSuccess promotes lockedForRead → lockedForWrite for expired-premium users',
      build: PremiumGateCubit.new,
      seed: () => const PremiumGateState(status: PremiumStatus.lockedForRead, hasEverPremium: true),
      act: (c) => c.reportReadSuccess(),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.lockedForWrite),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'reportReadSuccess is no-op for free users (hasEverPremium=false)',
      build: PremiumGateCubit.new,
      seed: () => const PremiumGateState(status: PremiumStatus.lockedForRead, hasEverPremium: false),
      act: (c) => c.reportReadSuccess(),
      expect: () => [],
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

    // ─── MG-profile-premium: bootstrap from /users/me/ ──────────────────

    blocTest<PremiumGateCubit, PremiumGateState>(
      'bootstrap(null) is a no-op',
      build: PremiumGateCubit.new,
      act: (c) => c.bootstrap(null),
      expect: () => const <PremiumGateState>[],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'bootstrap with subscription_status=null emits unknown',
      build: PremiumGateCubit.new,
      seed: () => const PremiumGateState(status: PremiumStatus.lockedForRead),
      act: (c) => c.bootstrap({'subscription_status': null}),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.unknown),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'bootstrap active premium -> unknown',
      build: PremiumGateCubit.new,
      seed: () => const PremiumGateState(status: PremiumStatus.lockedForRead),
      act: (c) => c.bootstrap({
        'subscription_status': {
          'is_active_premium': true,
          'has_ever_premium': true,
          'plan_code': 'premium',
          'status': 'active',
          'expires_at': '2027-01-01T00:00:00Z',
        }
      }),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.unknown),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'bootstrap expired premium -> lockedForWrite',
      build: PremiumGateCubit.new,
      act: (c) => c.bootstrap({
        'subscription_status': {
          'is_active_premium': false,
          'has_ever_premium': true,
          'plan_code': 'premium',
          'status': 'expired',
          'expires_at': '2025-01-01T00:00:00Z',
        }
      }),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.lockedForWrite),
      ],
    );

    blocTest<PremiumGateCubit, PremiumGateState>(
      'bootstrap never-paid -> lockedForRead',
      build: PremiumGateCubit.new,
      act: (c) => c.bootstrap({
        'subscription_status': {
          'is_active_premium': false,
          'has_ever_premium': false,
          'plan_code': 'premium',
          'status': 'cancelled',
          'expires_at': '2025-01-01T00:00:00Z',
        }
      }),
      expect: () => [
        isA<PremiumGateState>().having((s) => s.status, 'status', PremiumStatus.lockedForRead),
      ],
    );
  });
}
