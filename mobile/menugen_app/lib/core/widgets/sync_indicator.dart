import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../connectivity/connectivity_cubit.dart';
import '../sync/pending_sync_cubit.dart';

/// MG_T08: slim, always-visible global sync-status indicator (green/amber/red).
///  * red    — offline
///  * amber  — online but unsent local changes remain
///  * green  — online and everything is synced
class SyncIndicator extends StatelessWidget {
  const SyncIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ConnectivityCubit, ConnectivityStatus>(
      builder: (context, conn) {
        return BlocBuilder<PendingSyncCubit, int>(
          builder: (context, pending) {
            Color color;
            String label;
            if (conn == ConnectivityStatus.offline) {
              color = Colors.red.shade600;
              label = 'Нет сети';
            } else if (pending > 0) {
              color = Colors.amber.shade700;
              label = 'Синхронизация…';
            } else {
              color = Colors.green.shade600;
              label = 'В сети';
            }
            return Container(
              width: double.infinity,
              color: Colors.black.withOpacity(0.03),
              padding: const EdgeInsets.symmetric(vertical: 3, horizontal: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  // MG_NOOVERFLOW: на узком экране подпись сжимается.
                  Flexible(
                    child: Text(label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 11, color: Colors.grey.shade700)),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
