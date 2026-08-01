// MG_LEGAL: список юридических документов (оферта, политика ПД, реквизиты).
//
// Бэкенд отдаёт все три одним объектом, поэтому список грузит его один раз и
// передаёт дальше через extra — экран документа не делает повторный запрос.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../legal_repository.dart';
import '../models/legal_info.dart';

class LegalDocumentsScreen extends StatefulWidget {
  final ApiClient apiClient;

  const LegalDocumentsScreen({super.key, required this.apiClient});

  @override
  State<LegalDocumentsScreen> createState() => _LegalDocumentsScreenState();
}

class _LegalDocumentsScreenState extends State<LegalDocumentsScreen> {
  bool _loading = true;
  String? _error;
  LegalInfo? _info;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final info = await LegalRepository(widget.apiClient).load();
      if (!mounted) return;
      setState(() => _info = info);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Не удалось загрузить документы.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Документы')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          children: [
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    FilledButton(onPressed: _load, child: const Text('Повторить')),
                  ],
                ),
              )
            else
              for (final doc in LegalDoc.values)
                ListTile(
                  leading: Icon(switch (doc) {
                    LegalDoc.offer => Icons.description_outlined,
                    LegalDoc.privacy => Icons.privacy_tip_outlined,
                    LegalDoc.requisites => Icons.account_balance_outlined,
                  }),
                  title: Text(doc.title),
                  subtitle: Text(doc.subtitle),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/legal/${doc.slug}', extra: _info),
                ),
          ],
        ),
      ),
    );
  }
}
