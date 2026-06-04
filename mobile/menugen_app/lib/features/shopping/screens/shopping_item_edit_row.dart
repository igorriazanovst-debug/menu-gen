// MG_SHOPBUG_EDITMODE: inline-editable row for a shopping list item.
// Auto-saves via silent PATCH on focus loss; delete via trailing icon.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../models/shopping_models.dart';
import 'shopping_add_item.dart' show kShoppingUnits;

class ShoppingItemEditRow extends StatefulWidget {
  final int listId;
  final ShoppingItem item;
  final String currency;
  final ApiClient api;
  final VoidCallback onDeleted;

  const ShoppingItemEditRow({
    super.key,
    required this.listId,
    required this.item,
    required this.currency,
    required this.api,
    required this.onDeleted,
  });

  @override
  State<ShoppingItemEditRow> createState() => _ShoppingItemEditRowState();
}

class _ShoppingItemEditRowState extends State<ShoppingItemEditRow> {
  late TextEditingController _name;
  late TextEditingController _qty;
  late TextEditingController _price;
  late String _unit;
  late FocusNode _nameF;
  late FocusNode _qtyF;
  late FocusNode _priceF;
  late String _snap;
  bool _busy = false;
  bool _deleted = false;

  String _qtyStr(double? q) {
    if (q == null) return '';
    return q % 1 == 0 ? q.toInt().toString() : q.toString();
  }

  String _snapshot() => '${_name.text}|${_qty.text}|$_unit|${_price.text}';

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.item.name);
    _qty = TextEditingController(text: _qtyStr(widget.item.quantity));
    _price = TextEditingController(
        text: widget.item.pricePerUnit != null
            ? fmtMoney(widget.item.pricePerUnit)
            : '');
    final u = widget.item.unit;
    _unit = u.isEmpty ? 'шт' : u;
    _snap = _snapshot();
    _nameF = FocusNode()..addListener(_onAnyBlur);
    _qtyF = FocusNode()..addListener(_onAnyBlur);
    _priceF = FocusNode()..addListener(_onAnyBlur);
  }

  void _onAnyBlur() {
    // Wait one frame; if no field has focus, flush.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_nameF.hasFocus || _qtyF.hasFocus || _priceF.hasFocus) return;
      _flush();
    });
  }

  Future<void> _flush() async {
    if (_busy || _deleted) return;
    final cur = _snapshot();
    if (cur == _snap) return;
    _snap = cur;
    final name = _name.text.trim();
    final qty = double.tryParse(_qty.text.trim().replaceAll(',', '.'));
    final priceTxt = _price.text.trim().replaceAll(',', '.');
    final price = priceTxt.isEmpty ? null : double.tryParse(priceTxt);
    final payload = <String, dynamic>{
      if (name.isNotEmpty) 'name': name,
      'unit': _unit,
      if (qty != null) 'quantity': qty,
      'price_per_unit': price,
    };
    _busy = true;
    try {
      await widget.api.patch(
          '/shopping/lists/${widget.listId}/items/${widget.item.id}/',
          data: payload);
    } catch (_) {
      // Silent: user re-saves on next blur.
    } finally {
      _busy = false;
    }
  }

  Future<void> _delete() async {
    _deleted = true;
    try {
      await widget.api
          .delete('/shopping/lists/${widget.listId}/items/${widget.item.id}/');
    } catch (_) {}
    widget.onDeleted();
  }

  @override
  void dispose() {
    // Fire-and-forget final save on row removal (e.g. exit edit mode).
    if (!_deleted && _snapshot() != _snap) {
      // ignore: discarded_futures
      _flush();
    }
    _nameF.dispose();
    _qtyF.dispose();
    _priceF.dispose();
    _name.dispose();
    _qty.dispose();
    _price.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sym = currencySymbol(widget.currency);
    final units = List<String>.from(kShoppingUnits);
    if (!units.contains(_unit)) units.insert(0, _unit);
    final lineTxt = () {
      final q = double.tryParse(_qty.text.trim().replaceAll(',', '.'));
      final p = double.tryParse(_price.text.trim().replaceAll(',', '.'));
      if (q == null || p == null) return '';
      return '${(q * p).toStringAsFixed(2)} $sym';
    }();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _name,
            focusNode: _nameF,
            decoration: const InputDecoration(
              isDense: true,
              labelText: 'Продукт',
            ),
          ),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                flex: 2,
                child: TextField(
                  controller: _qty,
                  focusNode: _qtyF,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    isDense: true,
                    labelText: 'Кол-во',
                  ),
                  textAlign: TextAlign.right,
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                flex: 2,
                child: DropdownButtonFormField<String>(
                  isDense: true,
                  isExpanded: true,
                  value: _unit,
                  decoration: const InputDecoration(
                    isDense: true,
                    labelText: 'Ед.',
                  ),
                  items: units
                      .map((u) => DropdownMenuItem(
                            value: u,
                            child: Text(u,
                                style: const TextStyle(fontSize: 13)),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v == null) return;
                    setState(() => _unit = v);
                    _flush();
                  },
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                flex: 3,
                child: TextField(
                  controller: _price,
                  focusNode: _priceF,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: InputDecoration(
                    isDense: true,
                    labelText: 'Цена ($sym)',
                  ),
                  textAlign: TextAlign.right,
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: 4),
              IconButton(
                icon: const Icon(Icons.delete_outline,
                    color: Colors.red, size: 22),
                tooltip: 'Удалить',
                onPressed: _delete,
              ),
            ],
          ),
          if (lineTxt.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Align(
                alignment: Alignment.centerRight,
                child: Text('= $lineTxt',
                    style: const TextStyle(
                        fontSize: 12, fontWeight: FontWeight.bold)),
              ),
            ),
          const Divider(height: 12),
        ],
      ),
    );
  }
}
