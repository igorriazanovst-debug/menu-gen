import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../bloc/fridge_bloc.dart';
import 'add_fridge_item_sheet.dart';
import 'fridge_history_screen.dart';

/// Days-left buckets for "by expiry" view.
class _ExpiryBucket {
  final String title;
  final String emoji;
  final Color color;
  final bool Function(int? daysLeft) match;
  const _ExpiryBucket(this.title, this.emoji, this.color, this.match);
}

final List<_ExpiryBucket> _EXPIRY_BUCKETS = [
  _ExpiryBucket('Просрочено!', '❌', const Color(0xFFFFCDD2),
      (d) => d != null && d < 0),
  _ExpiryBucket('Съесть в течение 2 дней', '⚠️', const Color(0xFFFFE0B2),
      (d) => d != null && d >= 0 && d <= 2),
  _ExpiryBucket('Подходят к завершению', '⏰', const Color(0xFFFFF9C4),
      (d) => d != null && d >= 3 && d <= 7),
  _ExpiryBucket('Достаточно времени', '✅', const Color(0xFFC8E6C9),
      (d) => d == null || d > 7),
];

class FridgeScreen extends StatefulWidget {
  final ApiClient apiClient;
  const FridgeScreen({super.key, required this.apiClient});

  @override
  State<FridgeScreen> createState() => _FridgeScreenState();
}

class _FridgeScreenState extends State<FridgeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tab;

  // MG-610 select mode (expired only)
  bool _selecting = false;
  final Set<int> _selected = {};

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 2, vsync: this);
    context.read<FridgeBloc>().add(const FridgeLoadRequested());
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  int? _daysLeft(Map<String, dynamic> item) {
    final s = item['expiry_date'] as String?;
    if (s == null) return null;
    try {
      final exp = DateTime.parse(s);
      final today = DateTime.now();
      final t0 = DateTime(today.year, today.month, today.day);
      final e0 = DateTime(exp.year, exp.month, exp.day);
      return e0.difference(t0).inDays;
    } catch (_) {
      return null;
    }
  }

  bool _isExpired(Map<String, dynamic> item) {
    final d = _daysLeft(item);
    return d != null && d < 0;
  }

  Color _parseColor(String? hex) {
    if (hex == null || hex.isEmpty) return const Color(0xFFECEFF1);
    var h = hex.replaceFirst('#', '');
    if (h.length == 6) h = 'FF$h';
    try {
      return Color(int.parse(h, radix: 16));
    } catch (_) {
      return const Color(0xFFECEFF1);
    }
  }

  void _exitSelect() {
    setState(() {
      _selecting = false;
      _selected.clear();
    });
  }

  Future<bool?> _askDropHistory(String headline) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) {
        bool drop = false;
        return StatefulBuilder(
          builder: (ctx, setSt) => AlertDialog(
            title: const Text('Удаление'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(headline),
                const SizedBox(height: 8),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: drop,
                  title: const Text('Также удалить из истории'),
                  subtitle: const Text('по умолчанию выключено'),
                  onChanged: (v) => setSt(() => drop = v),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(null),
                child: const Text('Отмена'),
              ),
              ElevatedButton(
                onPressed: () => Navigator.of(ctx).pop(drop),
                child: const Text('Удалить'),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _deleteSelected() async {
    if (_selected.isEmpty) return;
    final drop = await _askDropHistory(
        'Удалить выбранные продукты (${_selected.length} шт.)?');
    if (drop == null) return;
    context.read<FridgeBloc>().add(FridgeExpiredBulkDeleted(
          ids: _selected.toList(),
          dropHistory: drop,
        ));
    _exitSelect();
  }

  Future<void> _deleteAllExpired(int count) async {
    final drop =
        await _askDropHistory('Удалить ВСЮ просрочку ($count шт.)?');
    if (drop == null) return;
    context.read<FridgeBloc>().add(FridgeExpiredBulkDeleted(
          all: true,
          dropHistory: drop,
        ));
    _exitSelect();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Холодильник'),
        actions: [
          IconButton(
            tooltip: 'История добавления',
            icon: const Icon(Icons.history),
            onPressed: () {
              final bloc = context.read<FridgeBloc>();
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => BlocProvider.value(
                    value: bloc,
                    child: const FridgeHistoryScreen(),
                  ),
                ),
              );
            },
          ),
          BlocBuilder<FridgeBloc, FridgeState>(
            builder: (context, state) {
              final loaded = state is FridgeLoaded ? state : null;
              final items = loaded?.items ?? const <Map<String, dynamic>>[];
              final hasExpired = items.any(_isExpired);
              if (!hasExpired) return const SizedBox.shrink();
              if (_selecting) {
                return IconButton(
                  tooltip: 'Отмена',
                  icon: const Icon(Icons.close),
                  onPressed: _exitSelect,
                );
              }
              return IconButton(
                tooltip: 'Удалить просрочку',
                icon: const Icon(Icons.cleaning_services_outlined),
                onPressed: () => setState(() => _selecting = true),
              );
            },
          ),
        ],
        bottom: TabBar(
          controller: _tab,
          tabs: const [
            Tab(text: 'По группам', icon: Icon(Icons.category_outlined)),
            Tab(text: 'По сроку', icon: Icon(Icons.event_outlined)),
          ],
        ),
      ),
      body: BlocBuilder<FridgeBloc, FridgeState>(
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
          final loaded = state is FridgeLoaded ? state : null;
          final items = loaded?.items ?? const <Map<String, dynamic>>[];
          final cats = loaded?.categories ?? const <Map<String, dynamic>>[];

          if (items.isEmpty) {
            return RefreshIndicator(
              onRefresh: () async =>
                  context.read<FridgeBloc>().add(const FridgeLoadRequested()),
              child: ListView(children: const [
                SizedBox(height: 100),
                Center(
                    child: Text('Холодильник пуст\nНажмите + чтобы добавить',
                        textAlign: TextAlign.center)),
              ]),
            );
          }

          final expiredCount = items.where(_isExpired).length;

          return Column(
            children: [
              if (_selecting)
                Container(
                  width: double.infinity,
                  color: const Color(0xFFFFEBEE),
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Выберите просрочку (${_selected.length} выбрано)',
                          style: const TextStyle(
                              fontSize: 13, color: Color(0xFFC62828)),
                        ),
                      ),
                      TextButton(
                        onPressed: () => _deleteAllExpired(expiredCount),
                        child: const Text('Удалить всю'),
                      ),
                      const SizedBox(width: 4),
                      ElevatedButton(
                        onPressed:
                            _selected.isEmpty ? null : _deleteSelected,
                        child: const Text('Выбранные'),
                      ),
                    ],
                  ),
                ),
              Expanded(
                child: TabBarView(
                  controller: _tab,
                  children: [
                    _buildGroupedView(context, items, cats),
                    _buildExpiryView(context, items),
                  ],
                ),
              ),
            ],
          );
        },
      ),
      floatingActionButton: _selecting
          ? null
          : FloatingActionButton(
              onPressed: () =>
                  AddFridgeItemSheet.show(context, widget.apiClient),
              child: const Icon(Icons.add),
            ),
    );
  }

  // ── View 1: by category groups ──
  Widget _buildGroupedView(
    BuildContext context,
    List<Map<String, dynamic>> items,
    List<Map<String, dynamic>> categories,
  ) {
    final Map<String, Map<String, dynamic>> bySlug = {
      for (final c in categories) (c['slug'] as String? ?? ''): c,
    };

    final Map<String, List<Map<String, dynamic>>> groups = {};
    for (final it in items) {
      final slug = (it['product_category_slug'] as String?)?.trim();
      final key = (slug == null || slug.isEmpty) ? 'other' : slug;
      groups.putIfAbsent(key, () => []).add(it);
    }

    final keys = groups.keys.toList()
      ..sort((a, b) {
        final ao = (bySlug[a]?['sort_order'] as int?) ?? 9999;
        final bo = (bySlug[b]?['sort_order'] as int?) ?? 9999;
        return ao.compareTo(bo);
      });

    return RefreshIndicator(
      onRefresh: () async =>
          context.read<FridgeBloc>().add(const FridgeLoadRequested()),
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
        itemCount: keys.length,
        itemBuilder: (_, idx) {
          final slug = keys[idx];
          final cat = bySlug[slug];
          final name = (cat?['name_ru'] as String?) ?? 'Без категории';
          final icon = (cat?['icon'] as String?) ?? '📦';
          final bg = _parseColor(cat?['color'] as String?);
          final groupItems = groups[slug]!;

          return Container(
            margin: const EdgeInsets.only(bottom: 16),
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: bg.withOpacity(0.6), width: 1),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
                  child: Row(
                    children: [
                      Text(icon, style: const TextStyle(fontSize: 20)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(name,
                            style: const TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w700)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.7),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text('${groupItems.length}',
                            style: const TextStyle(
                                fontSize: 12, fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                ),
                Container(
                  margin: const EdgeInsets.fromLTRB(8, 4, 8, 8),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    children: [
                      for (int i = 0; i < groupItems.length; i++) ...[
                        _itemTile(groupItems[i]),
                        if (i < groupItems.length - 1)
                          const Divider(height: 1),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  // ── View 2: by expiry buckets ──
  Widget _buildExpiryView(
      BuildContext context, List<Map<String, dynamic>> items) {
    final Map<int, List<Map<String, dynamic>>> buckets = {
      for (var i = 0; i < _EXPIRY_BUCKETS.length; i++) i: []
    };
    for (final it in items) {
      final d = _daysLeft(it);
      for (var i = 0; i < _EXPIRY_BUCKETS.length; i++) {
        if (_EXPIRY_BUCKETS[i].match(d)) {
          buckets[i]!.add(it);
          break;
        }
      }
    }

    return RefreshIndicator(
      onRefresh: () async =>
          context.read<FridgeBloc>().add(const FridgeLoadRequested()),
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
        itemCount: _EXPIRY_BUCKETS.length,
        itemBuilder: (_, idx) {
          final bucket = _EXPIRY_BUCKETS[idx];
          final group = buckets[idx]!;
          if (group.isEmpty) return const SizedBox.shrink();
          return Container(
            margin: const EdgeInsets.only(bottom: 16),
            decoration: BoxDecoration(
              color: bucket.color,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
                  child: Row(
                    children: [
                      Text(bucket.emoji, style: const TextStyle(fontSize: 20)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(bucket.title,
                            style: const TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w700)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.7),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text('${group.length}',
                            style: const TextStyle(
                                fontSize: 12, fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                ),
                Container(
                  margin: const EdgeInsets.fromLTRB(8, 4, 8, 8),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    children: [
                      for (int i = 0; i < group.length; i++) ...[
                        _itemTile(group[i]),
                        if (i < group.length - 1) const Divider(height: 1),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _itemTile(Map<String, dynamic> item) {
    final imageUrl = item['product_image_url'] as String?;
    final d = _daysLeft(item);
    final expired = d != null && d < 0;
    final id = item['id'] as int?;
    final selectable = _selecting && expired;
    final isSel = id != null && _selected.contains(id);

    String? subtitle;
    Color? subtitleColor;
    if (d != null) {
      if (d < 0) {
        subtitle = 'Просрочено ${-d} дн.';
        subtitleColor = const Color(0xFFC62828);
      } else if (d <= 2) {
        subtitle = 'Осталось $d дн.';
        subtitleColor = const Color(0xFFE65100);
      } else {
        subtitle = 'Осталось $d дн.';
      }
    }

    return ListTile(
      tileColor: selectable && isSel ? const Color(0xFFFFEBEE) : null,
      leading: selectable
          ? Checkbox(
              value: isSel,
              activeColor: const Color(0xFFC62828),
              onChanged: (_) {
                if (id == null) return;
                setState(() {
                  isSel ? _selected.remove(id) : _selected.add(id);
                });
              },
            )
          : (imageUrl != null && imageUrl.isNotEmpty
              ? ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: CachedNetworkImage(
                    imageUrl: imageUrl,
                    width: 40,
                    height: 40,
                    fit: BoxFit.cover,
                    errorWidget: (_, __, ___) =>
                        const Icon(Icons.inventory_2_outlined),
                  ),
                )
              : const Icon(Icons.inventory_2_outlined)),
      title: Text(item['name'] as String? ?? ''),
      subtitle: subtitle == null
          ? null
          : Text(subtitle,
              style: TextStyle(color: subtitleColor, fontSize: 12)),
      trailing: Text(
        '${item['quantity'] ?? ''} ${item['unit'] ?? ''}',
        style: const TextStyle(fontSize: 13),
      ),
      onTap: () async {
        if (selectable) {
          if (id == null) return;
          setState(() {
            isSel ? _selected.remove(id) : _selected.add(id);
          });
          return;
        }
        if (id != null) {
          // MG_B03: reload list on return so edits reflect immediately.
          await context.push('/fridge/$id/details');
          if (mounted) {
            context.read<FridgeBloc>().add(const FridgeLoadRequested());
          }
        }
      },
      onLongPress: _selecting
          ? null
          : () {
              if (id != null) {
                context.read<FridgeBloc>().add(FridgeItemDeleted(id));
              }
            },
    );
  }
}
