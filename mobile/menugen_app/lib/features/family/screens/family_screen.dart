import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/family_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';

class FamilyScreen extends StatefulWidget {
  final ApiClient apiClient;
  const FamilyScreen({super.key, required this.apiClient});
  @override State<FamilyScreen> createState() => _FamilyScreenState();
}
class _FamilyScreenState extends State<FamilyScreen> {
  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => FamilyBloc(apiClient: widget.apiClient)..add(const FamilyLoadRequested()),
      child: const _FamilyView(),
    );
  }
}

class _FamilyView extends StatelessWidget {
  const _FamilyView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Семья')),
      body: BlocBuilder<FamilyBloc, FamilyState>(
        builder: (context, state) {
          if (state is FamilyLoading) return const Center(child: CircularProgressIndicator());
          if (state is FamilyError) return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 12), Text(state.message),
            TextButton(onPressed: () => context.read<FamilyBloc>().add(const FamilyLoadRequested()),
              child: const Text('Повторить')),
          ]));
          if (state is FamilyLoaded) {
            final family = state.family;
            return ListView(padding: const EdgeInsets.all(16), children: [
              // Family header
              Card(child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(children: [
                  Container(width: 52, height: 52,
                    decoration: BoxDecoration(color: AppColors.primary.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(12)),
                    child: const Icon(Icons.people, color: AppColors.primary, size: 28)),
                  const SizedBox(width: 16),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(family.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    Text('Глава: \${family.ownerName}', style: TextStyle(color: Colors.grey.shade600)),
                  ])),
                ]),
              )),
              const SizedBox(height: 16),

              // Members
              Text('Участники (${family.members.length})',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
              const SizedBox(height: 8),
              ...family.members.map((member) => Card(
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: member.role == 'head'
                        ? AppColors.primary.withOpacity(0.15) : Colors.grey.shade100,
                    child: Text(member.name[0].toUpperCase(),
                        style: TextStyle(color: member.role == 'head' ? AppColors.primary : Colors.grey)),
                  ),
                  title: Text(member.name),
                  subtitle: Text(member.email ?? ''),
                  trailing: member.role == 'head'
                      ? const Chip(label: Text('Глава', style: TextStyle(fontSize: 11)))
                      : IconButton(
                          icon: const Icon(Icons.remove_circle_outline, color: Colors.red),
                          onPressed: () => _confirmRemove(context, member.id, member.name),
                        ),
                ),
              )),

              const SizedBox(height: 16),
              // Invite button
              ElevatedButton.icon(
                onPressed: () => _showInviteDialog(context),
                icon: const Icon(Icons.person_add_outlined),
                label: const Text('Пригласить участника'),
              ),
            ]);
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  void _showInviteDialog(BuildContext context) {
    final ctrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('Пригласить участника'),
      content: TextField(controller: ctrl,
        keyboardType: TextInputType.emailAddress,
        decoration: const InputDecoration(labelText: 'Email участника')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
        ElevatedButton(onPressed: () {
          if (ctrl.text.trim().isNotEmpty) {
            context.read<FamilyBloc>().add(FamilyInviteMemberRequested(ctrl.text.trim()));
            Navigator.pop(ctx);
          }
        }, child: const Text('Пригласить')),
      ],
    ));
  }

  void _confirmRemove(BuildContext context, int memberId, String name) {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('Удалить участника?'),
      content: Text('Удалить $name из семьи?'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
        ElevatedButton(
          style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
          onPressed: () {
            context.read<FamilyBloc>().add(FamilyRemoveMemberRequested(memberId));
            Navigator.pop(ctx);
          },
          child: const Text('Удалить'),
        ),
      ],
    ));
  }
}
