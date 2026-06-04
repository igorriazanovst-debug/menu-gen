// MG_SHOPMOB001
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../models/shopping_models.dart';

class ShoppingHistoryView extends StatefulWidget {
  final ApiClient apiClient;
  const ShoppingHistoryView({super.key, required this.apiClient});
  @override
  State<ShoppingHistoryView> createState() => _ShoppingHistoryViewState();
}

class _ShoppingHistoryViewState extends State<ShoppingHistoryView> {
  List<ShoppingHistoryEntry> _entries = const [];
  String _currency = 'RUB'; // MG_SHOPMOB001
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      // MG_SHOPMOB001: family currency for price symbol (best-effort).
      try {
        final f = await widget.apiClient.get('/family/');
        if (f is Map) {
          _currency = (f['currency'] as String?) ?? 'RUB';
        }
      } catch (_) {/* keep default */}
      final raw = await widget.apiClient.get('/shopping/history/');
      final list = (raw is List ? raw : const [])
          .whereType<Map>()
          .map((e) => ShoppingHistoryEntry.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      if (mounted) {
        setState(() {
          _entries = list;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _delete(int id) async {
    try {
      await widget.apiClient.delete('/shopping/history/?entry_id=$id');
      await _load();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_entries.isEmpty) {
      return const Center(child: Text('История пуста.'));
    }
    final sym = currencySymbol(_currency);
    return ListView.builder(
      itemCount: _entries.length,
      itemBuilder: (_, i) {
        final h = _entries[i];
        final date = h.purchasedAt.length >= 10
            ? h.purchasedAt.substring(0, 10)
            : h.purchasedAt;
        final qty = h.quantity != null
            ? ' — ${h.quantity}${h.unit.isNotEmpty ? ' ${h.unit}' : ''}'
            : '';
        final price =
            h.pricePerUnit != null ? '  ·  ${h.pricePerUnit} $sym' : '';
        return ListTile(
          title: Text('${h.name}$qty'),
          subtitle: Text('$date$price'),
          trailing: IconButton(
              icon: const Icon(Icons.close), onPressed: () => _delete(h.id)),
        );
      },
    );
  }
}
