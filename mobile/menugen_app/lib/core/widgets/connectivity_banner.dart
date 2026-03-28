import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../connectivity/connectivity_cubit.dart';

class ConnectivityBanner extends StatelessWidget {
  const ConnectivityBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ConnectivityCubit, ConnectivityStatus>(
      builder: (context, status) {
        if (status == ConnectivityStatus.online) return const SizedBox.shrink();
        return Container(
          width: double.infinity,
          color: Colors.orange.shade700,
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: const [
              Icon(Icons.wifi_off, color: Colors.white, size: 16),
              SizedBox(width: 8),
              Text('Офлайн-режим', style: TextStyle(color: Colors.white, fontSize: 13)),
            ],
          ),
        );
      },
    );
  }
}
