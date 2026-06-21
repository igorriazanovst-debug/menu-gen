import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T08
import '../../../core/sync/offline_toggle_queue.dart'; // MG_T09
import '../../../core/cache/shopping_cache.dart'; // MG_CACHE
import '../../../core/theme/app_theme.dart'; // MG_SKIN: токены
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
        offlineQueue: ctx.read<OfflineToggleQueue>(), // MG_T09
        cache: ctx.read<ShoppingCache>(), // MG_CACHE
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
  Map<String, int> _counts = const {}; // MG_T09: list counts per tab

  @override
  void initState() {
    super.initState();
    _loadCounts();
  }

  // MG_T09: fetch counts for all tabs (active/pending/archived/history).
  Future<void> _loadCounts() async {
    try {
      final raw =
          await context.read<ShoppingBloc>().apiClient.get('/shopping/counts/');
      if (!mounted) return;
      final m = raw is Map ? Map<String, dynamic>.from(raw) : const {};
      setState(() => _counts = {
            'active': (m['active'] as int?) ?? 0,
            'pending': (m['pending'] as int?) ?? 0,
            'archived': (m['archived'] as int?) ?? 0,
            'history': (m['history'] as int?) ?? 0,
          });
    } catch (_) {
      // non-fatal
    }
  }

  // MG_T09: list count for a tab (0 if unknown).
  int _count(String key) => _counts[key] ?? 0;

  void _selectTab(int t) {
    setState(() => _tab = t);
    _loadCounts(); // MG_T09: keep tab counts fresh
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
      _loadCounts(); // MG_T09
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
      appBar: AppBar(
        toolbarHeight: 44,
        titleSpacing: 12,
        titleTextStyle: TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: Theme.of(context).colorScheme.onSurface,
        ),
        title: const Text('Списки покупок'),
      ),
      floatingActionButton: (_tab == 2 || _tab == 3) // MG_SHAREACCEPT
          ? null
          : FloatingActionButton(
              onPressed: _openCreate,
              child: const Icon(Icons.add),
            ),
      body: Column(
        children: [
          // MG_SKIN: горизонтальные вкладки — слова целиком, не переносятся;
          // счётчики в закрашенных кружочках.
          SizedBox(
            height: 50,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
              children: [
                _Tab(
                    label: 'Активные',
                    count: _count('active'),
                    selected: _tab == 0,
                    onTap: () => _selectTab(0)),
                const SizedBox(width: 8),
                _Tab(
                    label: 'Ожидают',
                    count: _count('pending'),
                    selected: _tab == 3,
                    onTap: () => _selectTab(3)),
                const SizedBox(width: 8),
                _Tab(
                    label: 'Архив',
                    count: _count('archived'),
                    selected: _tab == 1,
                    onTap: () => _selectTab(1)),
                const SizedBox(width: 8),
                _Tab(
                    label: 'История',
                    count: _count('history'),
                    selected: _tab == 2,
                    onTap: () => _selectTab(2)),
              ],
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
                      // MG_T10: offline -> only the global banner.
                      if (state is ShoppingError &&
                          context.read<ConnectivityCubit>().state !=
                              ConnectivityStatus.offline) {
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
                          padding: const EdgeInsets.fromLTRB(8, 4, 8, 88),
                          itemCount: state.lists.length,
                          itemBuilder: (_, i) {
                            final l = state.lists[i];
                            return _ListCard(
                              list: l,
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

// MG_SKIN: вкладка-чип со счётчиком в закрашенном кружочке.
class _Tab extends StatelessWidget {
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;
  const _Tab({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? cs.primary : cs.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? cs.primary : tokens.border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              maxLines: 1,
              softWrap: false,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: selected ? Colors.white : cs.onSurface,
              ),
            ),
            if (count > 0) ...[
              const SizedBox(width: 6),
              _CountBadge(count: count, onSelected: selected),
            ],
          ],
        ),
      ),
    );
  }
}

// MG_SKIN: круглый счётчик. На невыделенной вкладке — заливка primary/белая
// цифра; на выделенной (фон primary) — белый кружок с цифрой primary.
class _CountBadge extends StatelessWidget {
  final int count;
  final bool onSelected;
  const _CountBadge({required this.count, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final bg = onSelected ? Colors.white : cs.primary;
    final fg = onSelected ? cs.primary : Colors.white;
    return Container(
      constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
      alignment: Alignment.center,
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10)),
      child: Text(
        '$count',
        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: fg),
      ),
    );
  }
}

// MG_SKIN: карточка списка покупок — в рамке, с понятным статусом.
class _ListCard extends StatelessWidget {
  final ShoppingListBrief list;
  final VoidCallback onTap;
  const _ListCard({required this.list, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    final total = list.itemsTotal;
    final bought = list.itemsPurchased;
    final remaining = (total - bought).clamp(0, total);
    final allBought = total > 0 && remaining == 0;

    // «Пустой» (source.empty) — это про способ создания и сбивает с толку;
    // показываем источник только когда он информативен.
    final meta = <String>[];
    if (list.source != ShoppingSource.empty) meta.add(list.source.label);
    final date = fmtListDate(list.createdAt);
    if (date.isNotEmpty) meta.add(date);
    final metaStr = meta.join(' · ');

    Widget status;
    if (total == 0) {
      status = Text('Пока пусто',
          style: TextStyle(fontSize: 13, color: tokens.textSecondary));
    } else if (allBought) {
      status = Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.check_circle, size: 18, color: Colors.green.shade600),
          const SizedBox(width: 6),
          Text('Всё куплено',
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.green.shade700)),
        ],
      );
    } else {
      status = Text(
        'Осталось купить $remaining ${_pluralItems(remaining)}',
        style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w600, color: cs.primary),
      );
    }

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 5),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: tokens.border),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        list.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: cs.onSurface),
                      ),
                      if (metaStr.isNotEmpty) ...[
                        const SizedBox(height: 3),
                        Text(metaStr,
                            style: TextStyle(
                                fontSize: 12, color: tokens.textSecondary)),
                      ],
                      const SizedBox(height: 8),
                      status,
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, color: tokens.textSecondary),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// MG_SKIN: склонение слова «товар» для остатка.
String _pluralItems(int n) {
  final n10 = n % 10;
  final n100 = n % 100;
  if (n10 == 1 && n100 != 11) return 'товар';
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return 'товара';
  return 'товаров';
}
