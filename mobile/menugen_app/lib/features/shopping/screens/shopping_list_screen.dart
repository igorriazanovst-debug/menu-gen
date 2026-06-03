import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../bloc/shopping_bloc.dart';
import '../models/shopping_models.dart';
import 'shopping_detail_screen.dart';
import 'shopping_create_sheet.dart';
import 'shopping_history_view.dart';

/// Entry screen for the shopping lists feature (MG_SHOP003).
class ShoppingListScreen extends StatelessWidget {
  final ApiClient apiClient;
  const ShoppingListScreen({super.key, required this.apiClient});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ShoppingBloc(apiClient: apiClient)
        ..add(const ShoppingListsRequested()),
      child: const _ShoppingListView(),
    );
  }
}

class _ShoppingListView extends StatefulWidget {
  const _ShoppingListView();
  @override
  State<_ShoppingListView> createState() => _ShoppingListViewState();
}

class _ShoppingListViewState extends State<_ShoppingListView> {
  int _tab = 0; // 0 active, 1 archived, 2 history

  void _selectTab(int t) {
    setState(() => _tab = t);
    if (t == 0) {
      context.read<ShoppingBloc>().add(const ShoppingListsRequested());
    } else if (t == 1) {
      context
          .read<ShoppingBloc>()
          .add(const ShoppingListsRequested(archived: true));
    }
  }

  Future<void> _openCreate() async {
    final bloc = context.read<ShoppingBloc>();
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => BlocProvider.value(
        value: bloc,
        child: const ShoppingCreateSheet(),
      ),
    );
    if (created == true) {
      _selectTab(0);
    }
  }

  void _openDetail(int listId) {
    final bloc = context.read<ShoppingBloc>();
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => BlocProvider.value(
          value: bloc,
          child: ShoppingDetailScreen(listId: listId),
        ),
      ),
    ).then((_) => _selectTab(_tab));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Списки покупок')),
      floatingActionButton: _tab == 2
          ? null
          : FloatingActionButton(
              onPressed: _openCreate,
              child: const Icon(Icons.add),
            ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(8),
            child: SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 0, label: Text('Активные')),
                ButtonSegment(value: 1, label: Text('Архив')),
                ButtonSegment(value: 2, label: Text('История')),
              ],
              selected: {_tab},
              onSelectionChanged: (s) => _selectTab(s.first),
            ),
          ),
          Expanded(
            child: _tab == 2
                ? ShoppingHistoryView(
                    apiClient: context.read<ShoppingBloc>().apiClient)
                : BlocConsumer<ShoppingBloc, ShoppingState>(
                    listener: (context, state) {
                      if (state is ShoppingError) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(state.message)),
                        );
                      }
                    },
                    builder: (context, state) {
                      if (state is ShoppingLoading ||
                          state is ShoppingInitial) {
                        return const Center(
                            child: CircularProgressIndicator());
                      }
                      if (state is ShoppingListsLoaded) {
                        if (state.lists.isEmpty) {
                          return const Center(child: Text('Списков нет.'));
                        }
                        return ListView.builder(
                          itemCount: state.lists.length,
                          itemBuilder: (_, i) {
                            final l = state.lists[i];
                            return ListTile(
                              title: Text(l.name),
                              subtitle: Text(
                                  '${l.source.label} · ${l.itemsPurchased}/${l.itemsTotal}'),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () => _openDetail(l.id),
                            );
                          },
                        );
                      }
                      return const SizedBox.shrink();
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
