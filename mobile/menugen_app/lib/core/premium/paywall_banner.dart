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
