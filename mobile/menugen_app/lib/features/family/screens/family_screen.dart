import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/family_bloc.dart';

class FamilyScreen extends StatelessWidget {
  const FamilyScreen({super.key});

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
