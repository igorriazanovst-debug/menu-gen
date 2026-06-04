// MG_SHOPMOB001: rubricator-aware add-item widget for shopping lists.
import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../models/shopping_models.dart';

const List<String> kShoppingUnits = [
  'шт',
  'г',
  'кг',
  'мл',
  'л',
  'упак',
  'банка',
  'пучок',
  'головка',
  'бутылка',
  'тюбик',
];

class ShoppingAddItem extends StatefulWidget {
  final ApiClient apiClient;
  final String currency;
  final void Function(Map<String, dynamic> payload) onSubmit;
  const ShoppingAddItem({
    super.key,
    required this.apiClient,
    required this.currency,
    required this.onSubmit,
  });

  @override
  State<ShoppingAddItem> createState() => _ShoppingAddItemState();
}

class _ShoppingAddItemState extends State<ShoppingAddItem> {
  final _search = TextEditingController();
  final _qty = TextEditingController(text: '1');
  final _price = TextEditingController();
  Timer? _debounce;

  List<RubricResult> _results = const [];
  List<Map<String, dynamic>> _categories = const [];
  bool _searching = false;
  String? _suggestedSlug;

  // staging state
  bool _staged = false;
  String _name = '';
  int? _productId; // null => new product
  String _unit = 'шт';
  String? _categorySlug;

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    _qty.dispose();
    _price.dispose();
    super.dispose();
  }

  void _onQueryChanged(String q) {
    _debounce?.cancel();
    if (q.trim().isEmpty) {
      setState(() => _results = const []);
      return;
    }
    _debounce =
        Timer(const Duration(milliseconds: 300), () => _runSearch(q.trim()));
  }

  Future<void> _runSearch(String q) async {
    setState(() => _searching = true);
    try {
      final raw = await widget.apiClient.get('/shopping/rubric/search/',
          params: {'q': q, 'classify': '1'});
      final map =
          raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{};
      final res = (map['results'] as List? ?? const [])
          .whereType<Map>()
          .map((e) => RubricResult.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      String? suggSlug;
      final sugg = map['suggestion'];
      if (sugg is Map) suggSlug = sugg['category_slug'] as String?;
      if (mounted) {
        setState(() {
          _results = res;
          _searching = false;
          _suggestedSlug = suggSlug;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _searching = false);
    }
  }

  Future<void> _ensureCategories() async {
    if (_categories.isNotEmpty) return;
    try {
      final raw = await widget.apiClient.get('/fridge/categories/');
      if (raw is List) {
        _categories = raw
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      }
    } catch (_) {/* non-fatal */}
  }

  void _pickExisting(RubricResult r) {
    setState(() {
      _staged = true;
      _name = r.name;
      _productId = r.productId;
      _unit = r.unit.isNotEmpty ? r.unit : 'шт';
      _categorySlug = r.categorySlug.isNotEmpty ? r.categorySlug : null;
      _results = const [];
    });
  }

  Future<void> _pickNew(String name) async {
    await _ensureCategories();
    final slugs = _categories.map((c) => c['slug'] as String?).toSet();
    var chosen = _suggestedSlug;
    if (chosen == null || !slugs.contains(chosen)) {
      chosen =
          _categories.isNotEmpty ? _categories.first['slug'] as String? : null;
    }
    if (!mounted) return;
    setState(() {
      _staged = true;
      _name = name;
      _productId = null;
      _unit = 'шт';
      _categorySlug = chosen;
      _results = const [];
    });
  }

  void _cancelStage() {
    setState(() {
      _staged = false;
      _name = '';
      _productId = null;
      _categorySlug = null;
      _qty.text = '1';
      _price.clear();
      _search.clear();
      _results = const [];
    });
  }

  void _commit() {
    final qty = double.tryParse(_qty.text.trim().replaceAll(',', '.'));
    final priceRaw = _price.text.trim().replaceAll(',', '.');
    final price = priceRaw.isEmpty ? null : double.tryParse(priceRaw);
    final payload = <String, dynamic>{
      'name': _name,
      if (qty != null) 'quantity': qty,
      'unit': _unit,
    };
    if (_productId != null) payload['product_id'] = _productId;
    if (_categorySlug != null && _categorySlug!.isNotEmpty) {
      payload['category_slug'] = _categorySlug;
    }
    if (price != null) payload['price_per_unit'] = price;
    widget.onSubmit(payload);
    _cancelStage();
  }

  double? get _lineTotal {
    final qty = double.tryParse(_qty.text.trim().replaceAll(',', '.'));
    final price = double.tryParse(_price.text.trim().replaceAll(',', '.'));
    if (qty == null || price == null) return null;
    return qty * price;
  }

  @override
  Widget build(BuildContext context) {
    final sym = currencySymbol(widget.currency);
    final bottom = MediaQuery.of(context).viewInsets.bottom;

    if (_staged) {
      return Padding(
        padding: EdgeInsets.fromLTRB(12, 8, 12, bottom + 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(_name,
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
                IconButton(
                    icon: const Icon(Icons.close), onPressed: _cancelStage),
              ],
            ),
            if (_productId == null) ...[
              DropdownButtonFormField<String>(
                value: _categorySlug,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Категория'),
                items: _categories
                    .map((c) => DropdownMenuItem(
                          value: c['slug'] as String?,
                          child: Text((c['name_ru'] as String?) ??
                              (c['slug'] as String? ?? '')),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _categorySlug = v),
              ),
              const SizedBox(height: 8),
            ],
            Row(
              children: [
                SizedBox(
                  width: 72,
                  child: TextField(
                    controller: _qty,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Кол-во'),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 112,
                  child: DropdownButtonFormField<String>(
                    value: _unit,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Ед.'),
                    items: kShoppingUnits
                        .map((u) =>
                            DropdownMenuItem(value: u, child: Text(u)))
                        .toList(),
                    onChanged: (v) => setState(() => _unit = v ?? _unit),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _price,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    decoration: InputDecoration(labelText: 'Цена, $sym'),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                if (_lineTotal != null)
                  Text('= ${_lineTotal!.toStringAsFixed(2)} $sym',
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                const Spacer(),
                FilledButton(
                    onPressed: _commit,
                    child: const Text('Добавить в список')),
              ],
            ),
          ],
        ),
      );
    }

    final showList =
        _results.isNotEmpty || (_search.text.trim().isNotEmpty && !_searching);
    return Padding(
      padding: EdgeInsets.fromLTRB(12, 4, 12, bottom + 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showList)
            Container(
              constraints: const BoxConstraints(maxHeight: 220),
              margin: const EdgeInsets.only(bottom: 6),
              decoration: BoxDecoration(
                border: Border.all(color: Colors.black12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final r in _results)
                    ListTile(
                      dense: true,
                      title: Text(r.name),
                      subtitle: r.categoryName.isNotEmpty
                          ? Text(r.categoryName)
                          : null,
                      onTap: () => _pickExisting(r),
                    ),
                  if (_search.text.trim().isNotEmpty)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.add),
                      title: Text(
                          'Добавить «${_search.text.trim()}» как новый'),
                      onTap: () => _pickNew(_search.text.trim()),
                    ),
                ],
              ),
            ),
          TextField(
            controller: _search,
            decoration: InputDecoration(
              hintText: 'Поиск товара…',
              suffixIcon: _searching
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    )
                  : null,
            ),
            onChanged: _onQueryChanged,
            onSubmitted: (v) {
              if (v.trim().isNotEmpty) _pickNew(v.trim());
            },
          ),
        ],
      ),
    );
  }
}
