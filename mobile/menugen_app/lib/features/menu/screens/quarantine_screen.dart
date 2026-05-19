import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';
import '../bloc/menu_bloc.dart';

/// MG_608_V_mobile_quarantine: экран карантина меню.
class QuarantineScreen extends StatefulWidget {
  final ApiClient apiClient;
  const QuarantineScreen({super.key, required this.apiClient});

  @override
  State<QuarantineScreen> createState() => _QuarantineScreenState();
}

class _QuarantineScreenState extends State<QuarantineScreen> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.get('/menu/quarantine/');
      final list = (r is List
              ? r
              : (r is Map ? (r['results'] as List? ?? []) : const []))
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      if (!mounted) return;
      setState(() {
        _items = list;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _restore(int id) async {
    try {
      await widget.apiClient.post('/menu/quarantine/$id/restore/');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Меню восстановлено')),
      );
      // Обновим главный список
      context.read<MenuBloc>().add(const MenuLoadRequested());
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка восстановления: $e')),
      );
    }
  }

  Future<void> _purge(int id) async {
    final ok = await _confirm(
      title: 'Удалить навсегда?',
      message: 'Это действие нельзя отменить.',
    );
    if (!ok) return;
    try {
      await widget.apiClient.delete('/menu/quarantine/$id/purge/');
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $e')),
      );
    }
  }

  Future<void> _purgeAll() async {
    final ok = await _confirm(
      title: 'Очистить весь карантин?',
      message: 'Все ${_items.length} записей будут удалены навсегда.',
    );
    if (!ok) return;
    try {
      await widget.apiClient.delete('/menu/quarantine/purge-all/');
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $e')),
      );
    }
  }

  Future<bool> _confirm({required String title, required String message}) async {
    final r = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Отмена'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    return r == true;
  }

  String _fmt(dynamic v) {
    if (v is! String || v.isEmpty) return '—';
    try {
      final d = DateTime.parse(v).toLocal();
      return DateFormat('d MMM HH:mm', 'ru').format(d);
    } catch (_) {
      return v;
    }
  }

  String _fmtDate(dynamic v) {
    if (v is! String || v.isEmpty) return '';
    try {
      final d = DateTime.parse(v);
      return DateFormat('d MMM', 'ru').format(d);
    } catch (_) {
      return v;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Карантин меню'),
        actions: [
          if (_items.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined),
              tooltip: 'Очистить всё',
              onPressed: _purgeAll,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : (_error != null)
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline, size: 56, color: Colors.red),
                        const SizedBox(height: 12),
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 8),
                        TextButton(onPressed: _load, child: const Text('Повторить')),
                      ],
                    ),
                  ),
                )
              : (_items.isEmpty
                  ? const Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text('Карантин пуст',
                            style: TextStyle(color: Colors.grey)),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.all(12),
                      itemCount: _items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (context, i) {
                        final it = _items[i];
                        final id = it['id'] as int;
                        final menuId = it['menu_id'];
                        final data = it['data'] is Map
                            ? Map<String, dynamic>.from(it['data'] as Map)
                            : <String, dynamic>{};
                        final start = _fmtDate(data['start_date']);
                        final end = _fmtDate(data['end_date']);
                        final delAt = _fmt(it['deleted_at']);
                        final purgeAt = _fmt(it['purge_after']);
                        final by = it['deleted_by_name'];
                        return Container(
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF9C3),
                            border: Border.all(color: const Color(0xFFFDE68A)),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      'Меню #$menuId  $start — $end',
                                      style: const TextStyle(
                                          fontWeight: FontWeight.w600),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Удалено: $delAt'
                                '${by != null ? ' · $by' : ''}',
                                style: const TextStyle(
                                    fontSize: 12, color: Colors.black54),
                              ),
                              Text('Истекает: $purgeAt',
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.black54)),
                              const SizedBox(height: 8),
                              Row(
                                children: [
                                  Expanded(
                                    child: OutlinedButton.icon(
                                      onPressed: () => _restore(id),
                                      icon: const Icon(Icons.undo, size: 18),
                                      label: const Text('Восстановить'),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: ElevatedButton.icon(
                                      onPressed: () => _purge(id),
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: Colors.red,
                                      ),
                                      icon: const Icon(Icons.delete_forever,
                                          size: 18),
                                      label: const Text('Навсегда'),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        );
                      },
                    )),
    );
  }
}
