import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../features/auth/bloc/auth_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';

class ProfileScreen extends StatelessWidget {
  final ApiClient apiClient;
  const ProfileScreen({super.key, required this.apiClient});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Профиль')),
      body: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, state) {
          if (state is! AuthAuthenticated) return const SizedBox.shrink();
          final user = state.user as Map<String, dynamic>;
          return ListView(padding: const EdgeInsets.all(16), children: [
            Center(child: CircleAvatar(radius: 44,
                backgroundColor: AppColors.primary.withOpacity(0.15),
                child: Text((user['name'] as String? ?? 'U')[0].toUpperCase(),
                    style: const TextStyle(fontSize: 32, color: AppColors.primary)))),
            const SizedBox(height: 12),
            Center(child: Text(user['name'] ?? '',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold))),
            Center(child: Text(user['email'] ?? user['phone'] ?? '',
                style: TextStyle(color: Colors.grey.shade600))),
            const SizedBox(height: 32),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.people_outline, color: AppColors.secondary),
              title: const Text('Семья'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/family'),
            ),
            ListTile(
              leading: const Icon(Icons.notifications_outlined),
              title: const Text('Уведомления'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {},
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout, color: Colors.red),
              title: const Text('Выйти', style: TextStyle(color: Colors.red)),
              onTap: () => context.read<AuthBloc>().add(const AuthLogoutRequested()),
            ),
          ]);
        },
      ),
    );
  }
}
