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
