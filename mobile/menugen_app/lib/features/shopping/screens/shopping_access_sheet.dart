import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../models/shopping_models.dart';

class ShoppingAccessSheet extends StatefulWidget {
  final ApiClient apiClient;
  final int listId;
  const ShoppingAccessSheet(
      {super.key, required this.apiClient, required this.listId});
  @override
  State<ShoppingAccessSheet> createState() => _ShoppingAccessSheetState();
}

class _ShoppingAccessSheetState extends State<ShoppingAccessSheet> {
  final _email = TextEditingController();
  bool _canToggle = false;
  bool _canExport = false;
  List<ShoppingAccess> _accesses = const [];
  bool _loading = true;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final raw =
          await widget.apiClient.get('/shopping/lists/${widget.listId}/access/');
      final list = (raw is List ? raw : const [])
          .whereType<Map>()
          .map((e) => ShoppingAccess.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      if (mounted) setState(() {
            _accesses = list;
            _loading = false;
          });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _grant() async {
    setState(() => _err = null);
    if (_email.text.trim().isEmpty) {
      setState(() => _err = 'Введите email.');
      return;
    }
    try {
      await widget.apiClient.post('/shopping/lists/${widget.listId}/access/',
          data: {
            'email': _email.text.trim(),
            'can_toggle': _canToggle,
            'can_export': _canExport,
          });
      _email.clear();
      _canToggle = false;
      _canExport = false;
      await _load();
    } catch (e) {
      setState(() => _err = 'Не удалось выдать доступ (проверьте email).');
    }
  }

  Future<void> _revoke(int accessId) async {
    try {
      await widget.apiClient.delete(
          '/shopping/lists/${widget.listId}/access/?access_id=$accessId');
      await _load();
    } catch (_) {}
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
            const Text('Доступ к списку',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            if (_loading)
              const Center(child: CircularProgressIndicator())
            else if (_accesses.isEmpty)
              const Text('Доступ ещё не выдан.',
                  style: TextStyle(color: Colors.grey))
            else
              ..._accesses.map((a) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(a.userName ?? a.userEmail),
                    subtitle: Text([
                      if (a.canToggle) 'отметка',
                      if (a.canExport) 'печать',
                    ].join(', ')),
                    trailing: IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => _revoke(a.id)),
                  )),
            const Divider(),
            TextField(
              controller: _email,
              decoration: const InputDecoration(labelText: 'email пользователя'),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _canToggle,
              onChanged: (v) => setState(() => _canToggle = v ?? false),
              title: const Text('Может отмечать покупки'),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _canExport,
              onChanged: (v) => setState(() => _canExport = v ?? false),
              title: const Text('Может печатать / экспортировать'),
            ),
            if (_err != null)
              Text(_err!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 8),
            FilledButton(onPressed: _grant, child: const Text('Выдать доступ')),
          ],
        ),
      ),
    );
  }
}
