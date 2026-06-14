import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T08
import '../../../core/sync/pending_sync_cubit.dart'; // MG_T08
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
      create: (ctx) => ShoppingBloc(
        apiClient: apiClient,
        connectivity: ctx.read<ConnectivityCubit>(), // MG_T08
        pendingSync: ctx.read<PendingSyncCubit>(), // MG_T08
      )..add(const ShoppingListsRequested()),
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
    } else if (t == 3) {
      context.read<ShoppingBloc>().add(const ShoppingPendingRequested()); // MG_SHAREACCEPT
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
      // MG_B10: switch to the active tab WITHOUT a second list reload — the
      // bloc's _onCreate already reloads, avoiding the race that blanked the
      // screen (a stale GET overwriting/clashing with the create result).
      setState(() => _tab = 0);
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
      floatingActionButton: (_tab == 2 || _tab == 3) // MG_SHAREACCEPT
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
                ButtonSegment(value: 3, label: Text('Ожидают')), // MG_SHAREACCEPT
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
                : _tab == 3 // MG_SHAREACCEPT
                ? _PendingView(
                    apiClient: context.read<ShoppingBloc>().apiClient,
                    onRespond: (id, accept) => context
                        .read<ShoppingBloc>()
                        .add(ShoppingRespondRequested(id, accept)),
                  )
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
                            // MG_SHOPBUG_MOB: include creation date.
                            final dateStr = fmtListDate(l.createdAt);
                            final sub = dateStr.isEmpty
                                ? '${l.source.label} · ${l.itemsPurchased}/${l.itemsTotal}'
                                : '${l.source.label} · $dateStr · ${l.itemsPurchased}/${l.itemsTotal}';
                            return ListTile(
                              title: Text(l.name),
                              subtitle: Text(sub),
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

// ── MG_SHAREACCEPT: ожидающие принятия общие списки ──────────────────────────
class _PendingView extends StatelessWidget {
  final ApiClient apiClient;
  final void Function(int listId, bool accept) onRespond;
  const _PendingView({required this.apiClient, required this.onRespond});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ShoppingBloc, ShoppingState>(
      builder: (context, state) {
        if (state is ShoppingLoading || state is ShoppingInitial) {
          return const Center(child: CircularProgressIndicator());
        }
        if (state is ShoppingPendingLoaded) {
          if (state.pending.isEmpty) {
            return const Center(
                child: Text('Нет списков, ожидающих принятия.'));
          }
          return ListView.builder(
            itemCount: state.pending.length,
            itemBuilder: (_, i) => _PendingCard(
              item: state.pending[i],
              apiClient: apiClient,
              onRespond: onRespond,
            ),
          );
        }
        return const SizedBox.shrink();
      },
    );
  }
}

class _PendingCard extends StatefulWidget {
  final ShoppingPendingList item;
  final ApiClient apiClient;
  final void Function(int listId, bool accept) onRespond;
  const _PendingCard(
      {required this.item, required this.apiClient, required this.onRespond});
  @override
  State<_PendingCard> createState() => _PendingCardState();
}

class _PendingCardState extends State<_PendingCard> {
  bool _open = false;
  bool _busy = false;
  ShoppingListDetail? _preview;

  Future<void> _togglePreview() async {
    if (_open) {
      setState(() => _open = false);
      return;
    }
    if (_preview == null) {
      try {
        final raw =
            await widget.apiClient.get('/shopping/lists/${widget.item.id}/');
        final d = ShoppingListDetail.fromJson(
            raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{});
        if (mounted) setState(() => _preview = d);
      } catch (_) {}
    }
    if (mounted) setState(() => _open = true);
  }

  @override
  Widget build(BuildContext context) {
    final it = widget.item;
    final date = fmtListDate(it.grantedAt);
    final sub = [
      (it.sharedByName != null && it.sharedByName!.isNotEmpty)
          ? 'Поделился: ${it.sharedByName}'
          : 'Общий список',
      '${it.itemsTotal} поз.',
      if (date.isNotEmpty) date,
    ].join(' · ');
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(it.name,
                style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(sub, style: const TextStyle(color: Colors.grey, fontSize: 12)),
            if (_open && _preview != null) ...[
              const Divider(),
              if (_preview!.items.isEmpty)
                const Text('Список пуст.',
                    style: TextStyle(color: Colors.grey))
              else
                ..._preview!.items.map((p) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(children: [
                        Expanded(child: Text(p.name)),
                        if (p.quantity != null)
                          Text(
                              '${p.quantity}${p.unit.isNotEmpty ? ' ${p.unit}' : ''}',
                              style: const TextStyle(color: Colors.grey)),
                      ]),
                    )),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  onPressed: _busy ? null : _togglePreview,
                  child: Text(_open ? 'Скрыть' : 'Просмотреть'),
                ),
                FilledButton(
                  onPressed: _busy
                      ? null
                      : () {
                          setState(() => _busy = true);
                          widget.onRespond(it.id, true);
                        },
                  child: const Text('Принять'),
                ),
                OutlinedButton(
                  onPressed: _busy
                      ? null
                      : () {
                          setState(() => _busy = true);
                          widget.onRespond(it.id, false);
                        },
                  child: const Text('Отклонить'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
