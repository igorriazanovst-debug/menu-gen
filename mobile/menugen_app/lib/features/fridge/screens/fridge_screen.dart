import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/fridge_bloc.dart';

class FridgeScreen extends StatefulWidget {
  const FridgeScreen({super.key});
  @override
  State<FridgeScreen> createState() => _FridgeScreenState();
}

class _FridgeScreenState extends State<FridgeScreen> {
  @override
  void initState() {
    super.initState();
    context.read<FridgeBloc>().add(FridgeLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Холодильник')),
      body: BlocBuilder<FridgeBloc, FridgeState>(
        builder: (context, state) {
          if (state is FridgeLoading) return const Center(child: CircularProgressIndicator());
          if (state is FridgeError) return Center(child: Text(state.message));
          final items = state is FridgeLoaded ? state.items : <Map<String, dynamic>>[];
          if (items.isEmpty) return const Center(child: Text('Холодильник пуст'));
          return ListView.builder(
            itemCount: items.length,
            itemBuilder: (_, i) {
              final item = items[i] as Map<String, dynamic>;
              final expiry = item['expiry_date'] as String?;
              int? daysLeft;
              try {
                if (expiry != null) daysLeft = DateTime.parse(expiry).difference(DateTime.now()).inDays;
              } catch (_) {}
              return ListTile(
                leading: const Icon(Icons.inventory_2_outlined),
                title: Text(item['name'] as String? ?? ''),
                subtitle: daysLeft != null ? Text('Осталось дней: $daysLeft') : null,
                trailing: Text('${item['quantity'] ?? ''} ${item['unit'] ?? ''}'),
                onLongPress: () {
                  final id = item['id'];
                  if (id != null) context.read<FridgeBloc>().add(FridgeItemDeleted(id as int));
                },
              );
            },
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        child: const Icon(Icons.add),
      ),
    );
  }
}