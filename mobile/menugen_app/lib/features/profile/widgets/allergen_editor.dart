// MG_ALLERGEN_V_mobile = 3
// Редактор аллергенов профиля: выбор ИЗ СПИСКА продуктов (каталог грузится сразу
// и виден), поиск по каталогу (серверный, для полного охвата) и ввод
// произвольного аллергена.
import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';

class AllergenEditor extends StatefulWidget {
  final ApiClient apiClient;
  final List<String> value;

  /// Вызывается с новым списком; родитель сохраняет на бэкенд.
  final Future<void> Function(List<String>) onChanged;

  const AllergenEditor({
    super.key,
    required this.apiClient,
    required this.value,
    required this.onChanged,
  });

  @override
  State<AllergenEditor> createState() => _AllergenEditorState();
}

class _AllergenEditorState extends State<AllergenEditor> {
  final TextEditingController _query = TextEditingController();
  Timer? _debounce;
  List<Map<String, dynamic>> _browse = const []; // полный каталог (обзор)
  List<Map<String, dynamic>> _results = const []; // серверный поиск
  bool _loading = true;
  bool _searching = false;
  bool _loadErr = false;
  String _q = '';

  @override
  void initState() {
    super.initState();
    _loadCatalog();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  Future<void> _loadCatalog() async {
    try {
      final r = await widget.apiClient.get('/fridge/products/catalog/');
      final list = _resultsOf(r);
      if (mounted) {
        setState(() {
          _browse = list;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _loadErr = true;
          _loading = false;
        });
      }
    }
  }

  void _search(String q) {
    _debounce?.cancel();
    setState(() => _q = q);
    if (q.trim().length < 2) {
      setState(() {
        _results = const [];
        _searching = false;
      });
      return;
    }
    setState(() => _searching = true);
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      try {
        final r = await widget.apiClient
            .get('/fridge/products/catalog/', params: {'q': q.trim()});
        final list = _resultsOf(r);
        if (mounted) {
          setState(() {
            _results = list;
            _searching = false;
          });
        }
      } catch (_) {
        if (mounted) {
          setState(() {
            _results = const [];
            _searching = false;
          });
        }
      }
    });
  }

  List<Map<String, dynamic>> _resultsOf(dynamic d) {
    try {
      d = d.data;
    } catch (_) {}
    if (d is List) {
      return d.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    if (d is Map) {
      return (d['results'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    }
    return const [];
  }

  bool _has(String name) {
    final n = name.trim().toLowerCase();
    return widget.value.any((a) => a.trim().toLowerCase() == n);
  }

  Future<void> _toggle(String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return;
    final List<String> next;
    if (_has(trimmed)) {
      next = widget.value
          .where((a) => a.trim().toLowerCase() != trimmed.toLowerCase())
          .toList();
    } else {
      next = [...widget.value, trimmed];
    }
    await widget.onChanged(next);
  }

  @override
  Widget build(BuildContext context) {
    final custom = _q.trim();
    final canAddCustom = custom.isNotEmpty && !_has(custom);
    final searchMode = custom.length >= 2;
    final items = searchMode ? _results : _browse;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Чипы выбранных.
        if (widget.value.isEmpty)
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text('Аллергены не выбраны.',
                style: TextStyle(fontSize: 13, color: Colors.grey)),
          )
        else
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: widget.value
                .map((a) => Chip(
                      label: Text(a),
                      onDeleted: () => _toggle(a),
                      deleteIcon: const Icon(Icons.close, size: 16),
                    ))
                .toList(),
          ),
        const SizedBox(height: 8),

        // Поиск по списку.
        TextField(
          controller: _query,
          decoration: const InputDecoration(
            isDense: true,
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.search, size: 20),
            hintText: 'Поиск по списку или свой аллерген…',
          ),
          onChanged: _search,
        ),

        // Добавить произвольный аллерген.
        if (canAddCustom)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  _toggle(custom);
                  _query.clear();
                  _search('');
                },
                icon: const Icon(Icons.add, size: 18),
                label: Text('Добавить свой аллерген «$custom»'),
              ),
            ),
          ),

        const SizedBox(height: 8),

        // Список продуктов каталога.
        Container(
          constraints: const BoxConstraints(maxHeight: 300),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.black12),
            borderRadius: BorderRadius.circular(8),
          ),
          child: _buildList(items, searchMode),
        ),
      ],
    );
  }

  Widget _buildList(List<Map<String, dynamic>> items, bool searchMode) {
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text('Загрузка каталога…',
            style: TextStyle(fontSize: 13, color: Colors.grey)),
      );
    }
    if (_loadErr) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text(
          'Не удалось загрузить каталог. Можно ввести аллерген вручную выше.',
          style: TextStyle(fontSize: 13, color: Colors.red),
        ),
      );
    }
    if (searchMode && _searching) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text('Поиск…',
            style: TextStyle(fontSize: 13, color: Colors.grey)),
      );
    }
    if (items.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text('Ничего не найдено.',
            style: TextStyle(fontSize: 13, color: Colors.grey)),
      );
    }
    return ListView.builder(
      shrinkWrap: true,
      itemCount: items.length,
      itemBuilder: (context, i) {
        final p = items[i];
        final name = (p['name'] ?? '').toString();
        final checked = _has(name);
        final cat = (p['category_name'] ?? '').toString();
        return CheckboxListTile(
          dense: true,
          controlAffinity: ListTileControlAffinity.leading,
          value: checked,
          title: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis),
          subtitle: cat.isNotEmpty
              ? Text(cat, style: const TextStyle(fontSize: 11))
              : null,
          onChanged: (_) => _toggle(name),
        );
      },
    );
  }
}
