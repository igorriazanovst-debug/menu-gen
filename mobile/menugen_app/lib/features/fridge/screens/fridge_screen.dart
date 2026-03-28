import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/fridge_bloc.dart';

class FridgeScreen extends StatefulWidget {
  const FridgeScreen({super.key});
  @override State<FridgeScreen> createState() => _FridgeScreenState();
}
class _FridgeScreenState extends State<FridgeScreen> {
  @override void initState() { super.initState(); context.read<FridgeBloc>().add(const FridgeLoadRequested()); }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Холодильник')),
      body: BlocBuilder<FridgeBloc, FridgeState>(builder: (context, state) {
        if (state is FridgeLoading) return const Center(child: CircularProgressIndicator());
        if (state is FridgeLoaded) {
          if (state.items.isEmpty) return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.kitchen, size: 80, color: Colors.grey.shade300), const SizedBox(height: 16),
            const Text('Холодильник пуст')]));
          return ListView.builder(
            padding: const EdgeInsets.all(12), itemCount: state.items.length,
            itemBuilder: (_, i) {
              final item = state.items[i];
              final daysLeft = item.expiryDate != null
                  ? DateTime.parse(item.expiryDate!).difference(DateTime.now()).inDays : null;
              return Card(child: ListTile(
                leading: const Icon(Icons.inventory_2_outlined), title: Text(item.name),
                subtitle: daysLeft != null ? Text('Истекает через \$daysLeft дн.',
                    style: TextStyle(color: daysLeft <= 3 ? Colors.red : Colors.grey)) : null,
                trailing: Text('\${item.quantity?.toStringAsFixed(1) ?? ''} \${item.unit ?? ''}'),
                onLongPress: () => context.read<FridgeBloc>().add(FridgeItemDeleted(item.id)),
              ));
            });
        }
        return const SizedBox.shrink();
      }),
      floatingActionButton: FloatingActionButton(
        onPressed: () { final c = TextEditingController();
          showDialog(context: context, builder: (ctx) => AlertDialog(
            title: const Text('Добавить продукт'),
            content: TextField(controller: c, decoration: const InputDecoration(labelText: 'Название')),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
              ElevatedButton(onPressed: () { if (c.text.trim().isNotEmpty) {
                  context.read<FridgeBloc>().add(FridgeItemAdded({'name': c.text.trim()}));
                  Navigator.pop(ctx); }}, child: const Text('Добавить')),
            ]));
        },
        child: const Icon(Icons.add),
      ),
    );
  }
}
