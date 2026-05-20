import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../bloc/fridge_bloc.dart';

class FridgeHistoryScreen extends StatefulWidget {
  const FridgeHistoryScreen({super.key});

  @override
  State<FridgeHistoryScreen> createState() => _FridgeHistoryScreenState();
}

class _FridgeHistoryScreenState extends State<FridgeHistoryScreen> {
  List<Map<String, dynamic>> _history = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final bloc = context.read<FridgeBloc>();
      final r = await bloc.apiClient
          .get('/fridge/products/history/', params: {'limit': '100'});
      setState(() {
        _history = (r is List)
            ? r.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList()
            : [];
      });
    } catch (_) {
      setState(() => _history = []);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _delete(Map<String, dynamic> h, bool dropFridge) async {
    final name = (h['name'] as String?) ?? '';
    if (name.isEmpty) return;
    final headline = dropFridge
        ? 'Удалить «$name» из холодильника и из истории?'
        : 'Удалить «$name» из истории добавления?\n(Активные позиции в холодильнике останутся.)';
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удаление'),
        content: Text(headline),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Отмена'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    context.read<FridgeBloc>().add(
          FridgeHistoryEntryDeleted(name, dropFridge: dropFridge),
        );
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('История добавления')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _history.isEmpty
              ? const Center(child: Text('История пуста'))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.separated(
                    padding: const EdgeInsets.all(12),
                    itemCount: _history.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (_, i) {
                      final h = _history[i];
                      final icon = (h['category_icon'] as String?) ?? '📦';
                      final name = (h['name'] as String?) ?? '';
                      final catName =
                          (h['category_name'] as String?) ?? 'Без категории';
                      final times = h['times_used'] ?? 0;
                      return Container(
                        decoration: BoxDecoration(
                          border: Border.all(color: const Color(0xFFE0E0E0)),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
                        child: Row(
                          children: [
                            Text(icon, style: const TextStyle(fontSize: 18)),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(name,
                                      style: const TextStyle(
                                          fontWeight: FontWeight.w600)),
                                  Text('$catName · добавлений: $times',
                                      style: const TextStyle(
                                          fontSize: 12,
                                          color: Color(0xFF757575))),
                                ],
                              ),
                            ),
                            IconButton(
                              tooltip: 'Удалить из истории',
                              icon: const Icon(Icons.history_toggle_off,
                                  size: 20),
                              onPressed: () => _delete(h, false),
                            ),
                            IconButton(
                              tooltip: 'Удалить из холодильника и истории',
                              icon: const Icon(Icons.delete_forever,
                                  size: 20, color: Color(0xFFC62828)),
                              onPressed: () => _delete(h, true),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
