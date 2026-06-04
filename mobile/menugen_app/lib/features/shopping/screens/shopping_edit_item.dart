// MG_SHOPBUG_MOB: edit-existing-item bottom sheet for shopping list.
import 'package:flutter/material.dart';

import '../models/shopping_models.dart';
import 'shopping_add_item.dart' show kShoppingUnits;

class ShoppingEditItem extends StatefulWidget {
  final ShoppingItem initial;
  final String currency;
  final void Function(Map<String, dynamic> payload) onSubmit;
  const ShoppingEditItem({
    super.key,
    required this.initial,
    required this.currency,
    required this.onSubmit,
  });

  @override
  State<ShoppingEditItem> createState() => _ShoppingEditItemState();
}

class _ShoppingEditItemState extends State<ShoppingEditItem> {
  late final TextEditingController _name;
  late final TextEditingController _qty;
  late final TextEditingController _price;
  late String _unit;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.initial.name);
    _qty = TextEditingController(
        text: widget.initial.quantity == null
            ? ''
            : (widget.initial.quantity! % 1 == 0
                ? widget.initial.quantity!.toInt().toString()
                : widget.initial.quantity!.toString()));
    _price = TextEditingController(
        text: widget.initial.pricePerUnit == null
            ? ''
            : fmtMoney(widget.initial.pricePerUnit));
    final u = widget.initial.unit;
    _unit = kShoppingUnits.contains(u) ? u : (u.isEmpty ? 'шт' : u);
  }

  @override
  void dispose() {
    _name.dispose();
    _qty.dispose();
    _price.dispose();
    super.dispose();
  }

  double? get _lineTotal {
    final q = double.tryParse(_qty.text.trim().replaceAll(',', '.'));
    final p = double.tryParse(_price.text.trim().replaceAll(',', '.'));
    if (q == null || p == null) return null;
    return q * p;
  }

  void _submit() {
    final name = _name.text.trim();
    if (name.isEmpty) return;
    final qty = double.tryParse(_qty.text.trim().replaceAll(',', '.'));
    final priceRaw = _price.text.trim().replaceAll(',', '.');
    final price = priceRaw.isEmpty ? null : double.tryParse(priceRaw);
    final payload = <String, dynamic>{
      'name': name,
      if (qty != null) 'quantity': qty,
      'unit': _unit,
      'price_per_unit': price,
    };
    widget.onSubmit(payload);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final sym = currencySymbol(widget.currency);
    final units = List<String>.from(kShoppingUnits);
    if (!units.contains(_unit)) units.insert(0, _unit);
    return Padding(
      padding: EdgeInsets.fromLTRB(
          16, 16, 16, MediaQuery.of(context).viewInsets.bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Редактировать позицию',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          TextField(
            controller: _name,
            decoration: const InputDecoration(labelText: 'Название'),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _qty,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Кол-во'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _unit,
                  decoration: const InputDecoration(labelText: 'Ед.'),
                  items: units
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
                  decoration:
                      InputDecoration(labelText: 'Цена ($sym)'),
                  onChanged: (_) => setState(() {}),
                ),
              ),
            ],
          ),
          if (_lineTotal != null) ...[
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: Text('= ${_lineTotal!.toStringAsFixed(2)} $sym',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Отмена'),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: _submit,
                child: const Text('Сохранить'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
