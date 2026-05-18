import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:cached_network_image/cached_network_image.dart';

import '../../../core/api/api_client.dart';
import '../bloc/fridge_bloc.dart';
import 'add_fridge_item_sheet.dart';

class FridgeScreen extends StatefulWidget {
  final ApiClient apiClient;
  const FridgeScreen({super.key, required this.apiClient});

  @override
  State<FridgeScreen> createState() => _FridgeScreenState();
}

class _FridgeScreenState extends State<FridgeScreen> {
  @override
  void initState() {
    super.initState();
    context.read<FridgeBloc>().add(const FridgeLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Холодильник')),
      body: RefreshIndicator(
        onRefresh: () async => context.read<FridgeBloc>().add(const FridgeLoadRequested()),
        child: BlocBuilder<FridgeBloc, FridgeState>(
          builder: (context, state) {
            if (state is FridgeLoading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (state is FridgeError) {
              return ListView(children: [
                const SizedBox(height: 80),
                Center(child: Text(state.message)),
              ]);
            }
            final items = state is FridgeLoaded ? state.items : <Map<String, dynamic>>[];
            if (items.isEmpty) {
              return ListView(children: const [
                SizedBox(height: 100),
                Center(child: Text('Холодильник пуст\nНажмите + чтобы добавить', textAlign: TextAlign.center)),
              ]);
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final item = items[i];
                final expiry = item['expiry_date'] as String?;
                int? daysLeft;
                try {
                  if (expiry != null) {
                    daysLeft = DateTime.parse(expiry).difference(DateTime.now()).inDays;
                  }
                } catch (_) {}
                final imageUrl = item['product_image_url'] as String?;
                return ListTile(
                  leading: imageUrl != null && imageUrl.isNotEmpty
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: CachedNetworkImage(
                            imageUrl: imageUrl,
                            width: 40, height: 40, fit: BoxFit.cover,
                            errorWidget: (_, __, ___) => const Icon(Icons.inventory_2_outlined),
                          ),
                        )
                      : const Icon(Icons.inventory_2_outlined),
                  title: Text(item['name'] as String? ?? ''),
                  subtitle: daysLeft != null
                      ? Text(daysLeft < 0
                          ? 'Просрочено ${-daysLeft} дн.'
                          : 'Осталось дней: $daysLeft')
                      : null,
                  trailing: Text('${item['quantity'] ?? ''} ${item['unit'] ?? ''}'),
                  onLongPress: () {
                    final id = item['id'];
                    if (id != null) {
                      context.read<FridgeBloc>().add(FridgeItemDeleted(id as int));
                    }
                  },
                );
              },
            );
          },
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => AddFridgeItemSheet.show(context, widget.apiClient),
        child: const Icon(Icons.add),
      ),
    );
  }
}
