// MG_ALLERGEN_V_mobile = 1
// Редактор аллергенов профиля: чипы выбранных + поиск по каталогу продуктов
// (/fridge/products/search/) + ручной ввод произвольного аллергена.
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
  List<Map<String, dynamic>> _results = const [];
  bool _loading = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  bool _has(String name) {
    final n = name.trim().toLowerCase();
    return widget.value.any((a) => a.trim().toLowerCase() == n);
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

  void _search(String q) {
    _debounce?.cancel();
    if (q.trim().length < 2) {
      setState(() {
        _results = const [];
        _loading = false;
      });
      return;
    }
    setState(() => _loading = true);
    _debounce = Timer(const Duration(milliseconds: 350), () async {
      try {
        final r = await widget.apiClient
            .get('/fridge/products/search/', params: {'q': q.trim()});
        final list = _resultsOf(r);
        if (mounted) {
          setState(() {
            _results = list;
            _loading = false;
          });
        }
      } catch (_) {
        if (mounted) {
          setState(() {
            _results = const [];
            _loading = false;
          });
        }
      }
    });
  }

  Future<void> _add(String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty || _has(trimmed)) {
      _clearQuery();
      return;
    }
    final next = [...widget.value, trimmed];
    _clearQuery();
    await widget.onChanged(next);
  }

  Future<void> _remove(String name) async {
    final next = widget.value.where((a) => a != name).toList();
    await widget.onChanged(next);
  }

  void _clearQuery() {
    setState(() {
      _query.clear();
      _results = const [];
    });
  }

  @override
  Widget build(BuildContext context) {
    final custom = _query.text.trim();
    final canAddCustom = custom.isNotEmpty && !_has(custom);

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
                      onDeleted: () => _remove(a),
                      deleteIcon: const Icon(Icons.close, size: 16),
                    ))
                .toList(),
          ),
        const SizedBox(height: 8),

        TextField(
          controller: _query,
          decoration: const InputDecoration(
            isDense: true,
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.search, size: 20),
            hintText: 'Поиск продукта или свой аллерген…',
          ),
          textInputAction: TextInputAction.done,
          onChanged: (q) => setState(() => _search(q)),
          onSubmitted: (q) {
            if (q.trim().isNotEmpty) _add(q);
          },
        ),

        if (_loading)
          const Padding(
            padding: EdgeInsets.all(8),
            child: Text('Поиск…',
                style: TextStyle(fontSize: 13, color: Colors.grey)),
          ),

        if (!_loading && (_results.isNotEmpty || canAddCustom))
          Container(
            margin: const EdgeInsets.only(top: 4),
            constraints: const BoxConstraints(maxHeight: 220),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.black12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: ListView(
              shrinkWrap: true,
              padding: EdgeInsets.zero,
              children: [
                ..._results.map((p) {
                  final name = (p['name'] ?? '').toString();
                  final already = _has(name);
                  return ListTile(
                    dense: true,
                    enabled: !already,
                    title: Text(name,
                        maxLines: 1, overflow: TextOverflow.ellipsis),
                    trailing: already
                        ? const Text('добавлен',
                            style:
                                TextStyle(fontSize: 12, color: Colors.grey))
                        : null,
                    onTap: already ? null : () => _add(name),
                  );
                }),
                if (canAddCustom)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.add, size: 20),
                    title: Text('Добавить «$custom»'),
                    onTap: () => _add(custom),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}
