import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../models/shopping_models.dart';
import '../share_error_text.dart'; // MG_SHAREERR

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
  final _phone = TextEditingController();
  // MG_PHONESHARE: доступ выдаётся по e-mail или по телефону — у части
  // пользователей аккаунт заведён через мессенджер и почты у них нет.
  bool _byPhone = false;
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
    _phone.dispose();
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
    final value = (_byPhone ? _phone : _email).text.trim();
    if (value.isEmpty) {
      setState(() => _err = _byPhone ? 'Введите телефон.' : 'Введите email.');
      return;
    }
    try {
      await widget.apiClient.post('/shopping/lists/${widget.listId}/access/',
          data: {
            if (_byPhone) 'phone': value else 'email': value,
            'can_toggle': _canToggle,
            'can_export': _canExport,
          });
      _email.clear();
      _phone.clear();
      _canToggle = false;
      _canExport = false;
      await _load();
    } catch (e) {
      // MG_SHAREERR: причину называет бэкенд («Пользователь не найден»,
      // «Нет прав»). Раньше она терялась: на любой отказ показывался один и тот
      // же текст «проверьте email», и понять, что адрес верный, а аккаунта с ним
      // просто нет, было невозможно.
      setState(() => _err = grantErrorText(e, byPhone: _byPhone));
    }
  }

  String _accessTitle(ShoppingAccess a) {
    final name = (a.userName ?? '').trim();
    if (name.isNotEmpty) return name;
    if (a.userEmail.trim().isNotEmpty) return a.userEmail;
    return 'Пользователь #${a.id}';
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
                    // У аккаунтов из мессенджера e-mail пустой, поэтому нужен
                    // запасной вариант — иначе строка была бы без подписи.
                    title: Text(_accessTitle(a)),
                    subtitle: Text([
                      if (a.canToggle) 'отметка',
                      if (a.canExport) 'печать',
                    ].join(', ')),
                    trailing: IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => _revoke(a.id)),
                  )),
            const Divider(),
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('E-mail')),
                ButtonSegment(value: true, label: Text('Телефон')),
              ],
              selected: {_byPhone},
              onSelectionChanged: (s) => setState(() {
                _byPhone = s.first;
                _err = null;
              }),
            ),
            const SizedBox(height: 12),
            if (_byPhone)
              TextField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'телефон пользователя',
                  hintText: '+7 900 000-00-00',
                ),
              )
            else
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(labelText: 'email пользователя'),
              ),
            // MG_SHAREERR: главное ограничение — видно до попытки, а не после.
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'Доступ выдаётся только тем, кто уже зарегистрирован в MenuGen.',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
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
