import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/family_bloc.dart';
import '../../../core/api/api_client.dart';

class FamilyScreen extends StatefulWidget {
  final ApiClient apiClient;
  const FamilyScreen({super.key, required this.apiClient});
  @override
  State<FamilyScreen> createState() => _FamilyScreenState();
}

class _FamilyScreenState extends State<FamilyScreen> {
  @override
  void initState() {
    super.initState();
    context.read<FamilyBloc>().add(FamilyLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Семья')),
      body: BlocBuilder<FamilyBloc, FamilyState>(
        builder: (context, state) {
          if (state is FamilyLoading) return const Center(child: CircularProgressIndicator());
          if (state is FamilyError) return Center(child: Text(state.message));
          if (state is! FamilyLoaded) return const Center(child: Text('Нет данных'));
          final family = state.family as Map<String, dynamic>;
          final members = (family['members'] as List<dynamic>?) ?? [];
          return ListView(padding: const EdgeInsets.all(16), children: [
            Text(family['name'] as String? ?? '', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            Text('Участники (${members.length})', style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            ...members.map((m) {
              final member = m as Map<String, dynamic>;
              return Card(child: ListTile(
                leading: const Icon(Icons.person_outline),
                title: Text(member['name'] as String? ?? ''),
                subtitle: Text(member['role'] as String? ?? ''),
              ));
            }),
          ]);
        },
      ),
    );
  }
}