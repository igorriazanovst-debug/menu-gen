// MG_LEGAL: просмотр одного документа — оферта, политика ПД или реквизиты.
//
// Данные обычно приходят готовыми из списка (extra), но экран умеет загрузиться
// и сам: так работают прямые ссылки вида /legal/privacy, которые нужны для
// модерации в сторах — политику должно быть видно без входа в аккаунт.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../legal_repository.dart';
import '../models/legal_info.dart';

class LegalDocumentScreen extends StatefulWidget {
  final ApiClient apiClient;
  final LegalDoc doc;
  final LegalInfo? preloaded;

  const LegalDocumentScreen({
    super.key,
    required this.apiClient,
    required this.doc,
    this.preloaded,
  });

  @override
  State<LegalDocumentScreen> createState() => _LegalDocumentScreenState();
}

class _LegalDocumentScreenState extends State<LegalDocumentScreen> {
  late bool _loading = widget.preloaded == null;
  String? _error;
  late LegalInfo? _info = widget.preloaded;

  @override
  void initState() {
    super.initState();
    if (_info == null) _load();
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
      setState(() => _error = 'Не удалось загрузить документ.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.doc.title)),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());

    final info = _info;
    if (_error != null || info == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error ?? 'Документ недоступен.', textAlign: TextAlign.center),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Повторить')),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        if (widget.doc == LegalDoc.requisites)
          _Requisites(info: info)
        else
          _DocumentText(
            text: widget.doc == LegalDoc.offer ? info.offerText : info.privacyText,
          ),
      ],
    );
  }
}

class _DocumentText extends StatelessWidget {
  final String text;

  const _DocumentText({required this.text});

  @override
  Widget build(BuildContext context) {
    if (text.trim().isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 48),
        child: Text('Документ пока не опубликован.', textAlign: TextAlign.center),
      );
    }
    // SelectableText — чтобы можно было скопировать фрагмент (реквизиты, e-mail).
    return SelectableText(text, style: const TextStyle(fontSize: 14, height: 1.5));
  }
}

class _Requisites extends StatelessWidget {
  final LegalInfo info;

  const _Requisites({required this.info});

  @override
  Widget build(BuildContext context) {
    if (!info.hasRequisites) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 48),
        child: Text('Реквизиты пока не заполнены.', textAlign: TextAlign.center),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _row('Наименование', info.companyName),
        _row('ИНН', info.inn),
        _row('ОГРНИП', info.ogrnip),
        _row('Адрес', info.legalAddress),
        _row('E-mail', info.email),
        _row('Телефон', info.phone),
        _row('Банк', info.bankName),
        _row('БИК', info.bankBik),
        _row('Расчётный счёт', info.bankAccount),
        _row('Корр. счёт', info.corrAccount),
        if (info.requisitesExtra.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: SelectableText(info.requisitesExtra, style: const TextStyle(fontSize: 13)),
          ),
      ],
    );
  }

  Widget _row(String label, String value) {
    if (value.trim().isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          const SizedBox(height: 2),
          SelectableText(value, style: const TextStyle(fontSize: 14)),
        ],
      ),
    );
  }
}
