import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../bloc/shopping_bloc.dart';
import '../models/shopping_models.dart';

class ShoppingCreateSheet extends StatefulWidget {
  const ShoppingCreateSheet({super.key});
  @override
  State<ShoppingCreateSheet> createState() => _ShoppingCreateSheetState();
}

class _ShoppingCreateSheetState extends State<ShoppingCreateSheet> {
  final _name = TextEditingController();
  final _text = TextEditingController();
  final _csv = TextEditingController();
  ShoppingSource _source = ShoppingSource.empty;
  List<Map<String, dynamic>> _menus = const [];
  int? _menuId;
  bool _busy = false;
  String? _err;

  @override
  void dispose() {
    _name.dispose();
    _text.dispose();
    _csv.dispose();
    super.dispose();
  }

  Future<void> _loadMenus() async {
    final api = context.read<ShoppingBloc>().apiClient;
    try {
      final r = await api.get('/menu/');
      final list = (r is Map ? r['results'] : r);
      if (list is List && mounted) {
        setState(() => _menus = list
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList());
      }
    } catch (_) {}
  }

  void _onSourceChanged(ShoppingSource s) {
    setState(() => _source = s);
    if (s == ShoppingSource.menu || s == ShoppingSource.fridge) {
      _loadMenus();
    }
  }

  void _submit() {
    setState(() => _err = null);
    if (_name.text.trim().isEmpty) {
      setState(() => _err = 'Введите название.');
      return;
    }
    final payload = <String, dynamic>{
      'name': _name.text.trim(),
      'source': _source.value,
    };
    if (_source == ShoppingSource.menu || _source == ShoppingSource.fridge) {
      if (_menuId == null) {
        setState(() => _err = 'Выберите меню.');
        return;
      }
      payload['menu_id'] = _menuId;
      payload['subtract_fridge'] = _source == ShoppingSource.fridge;
    }
    if (_source == ShoppingSource.aiText) payload['text'] = _text.text;
    if (_source == ShoppingSource.csv) payload['csv_text'] = _csv.text;

    setState(() => _busy = true);
    context.read<ShoppingBloc>().add(ShoppingCreateRequested(payload));
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
          16, 16, 16, MediaQuery.of(context).viewInsets.bottom + 16),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Новый список покупок',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Название'),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<ShoppingSource>(
              value: _source,
              decoration: const InputDecoration(labelText: 'Источник'),
              items: ShoppingSource.values
                  .map((s) =>
                      DropdownMenuItem(value: s, child: Text(s.label)))
                  .toList(),
              onChanged: (s) => s != null ? _onSourceChanged(s) : null,
            ),
            if (_source == ShoppingSource.menu ||
                _source == ShoppingSource.fridge) ...[
              const SizedBox(height: 12),
              DropdownButtonFormField<int>(
                value: _menuId,
                decoration: const InputDecoration(labelText: 'Меню'),
                items: _menus
                    .map((m) => DropdownMenuItem(
                          value: m['id'] as int,
                          child: Text(
                              (m['title'] as String?) ?? 'Меню #${m['id']}'),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _menuId = v),
              ),
            ],
            if (_source == ShoppingSource.aiText) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _text,
                maxLines: 4,
                decoration: const InputDecoration(
                    labelText: 'Текст со списком',
                    border: OutlineInputBorder()),
              ),
            ],
            if (_source == ShoppingSource.csv) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _csv,
                maxLines: 4,
                decoration: const InputDecoration(
                    labelText: 'CSV: name,quantity,unit,category',
                    border: OutlineInputBorder()),
              ),
            ],
            if (_err != null) ...[
              const SizedBox(height: 8),
              Text(_err!, style: const TextStyle(color: Colors.red)),
            ],
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _busy ? null : _submit,
              child: const Text('Создать'),
            ),
          ],
        ),
      ),
    );
  }
}
