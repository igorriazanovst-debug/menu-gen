import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';

// MG_B03: edit an existing fridge item (name / category / qty / unit / expiry).
const _UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

class EditFridgeItemSheet extends StatefulWidget {
  final ApiClient apiClient;
  final Map<String, dynamic> item;
  const EditFridgeItemSheet({
    super.key,
    required this.apiClient,
    required this.item,
  });

  static Future<bool?> show(
    BuildContext context,
    ApiClient apiClient,
    Map<String, dynamic> item,
  ) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
        child: EditFridgeItemSheet(apiClient: apiClient, item: item),
      ),
    );
  }

  @override
  State<EditFridgeItemSheet> createState() => _EditFridgeItemSheetState();
}

class _EditFridgeItemSheetState extends State<EditFridgeItemSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _qtyCtrl = TextEditingController();
  late String _unit;
  DateTime? _expiry;
  String? _selectedSlug;
  bool _submitting = false;
  String? _error;

  List<Map<String, dynamic>> _categories = [];
  List<String> _units = List.of(_UNITS);
  bool _loadingMeta = true;

  @override
  void initState() {
    super.initState();
    final it = widget.item;
    _nameCtrl.text = (it['name'] as String?) ?? '';
    final q = it['quantity'];
    _qtyCtrl.text = q == null ? '' : q.toString();
    final u = (it['unit'] as String?) ?? '';
    if (u.isNotEmpty && !_units.contains(u)) _units = [u, ..._units];
    _unit = u.isNotEmpty ? u : _UNITS.first;
    _expiry = DateTime.tryParse((it['expiry_date'] as String?) ?? '');
    _selectedSlug = it['product_category_slug'] as String?;
    _loadCategories();
  }

  Future<void> _loadCategories() async {
    try {
      final r = await widget.apiClient.get('/fridge/categories/');
      if (mounted && r is List) {
        setState(() {
          _categories = r
              .whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList();
        });
      }
    } catch (_) {/* non-fatal */}
    if (mounted) setState(() => _loadingMeta = false);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _qtyCtrl.dispose();
    super.dispose();
  }

  Color _parseColor(String? hex) {
    if (hex == null || hex.isEmpty) return const Color(0xFFECEFF1);
    var h = hex.replaceFirst('#', '');
    if (h.length == 6) h = 'FF$h';
    try {
      return Color(int.parse(h, radix: 16));
    } catch (_) {
      return const Color(0xFFECEFF1);
    }
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _expiry ?? now.add(const Duration(days: 7)),
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now.add(const Duration(days: 365 * 3)),
    );
    if (picked != null) setState(() => _expiry = picked);
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    if (_nameCtrl.text.trim().isEmpty) {
      setState(() => _error = 'Укажите название');
      return;
    }
    final qty = double.tryParse(_qtyCtrl.text.replaceAll(',', '.'));
    if (qty == null || qty <= 0) {
      setState(() => _error = 'Укажите количество (> 0)');
      return;
    }
    if (_expiry == null) {
      setState(() => _error = 'Укажите срок годности');
      return;
    }
    setState(() => _submitting = true);
    try {
      final body = <String, dynamic>{
        'name': _nameCtrl.text.trim(),
        'quantity': qty,
        'unit': _unit,
        'expiry_date': DateFormat('yyyy-MM-dd').format(_expiry!),
      };
      if (_selectedSlug != null && _selectedSlug!.isNotEmpty) {
        body['category_slug'] = _selectedSlug;
      }
      final id = widget.item['id'];
      await widget.apiClient.patch('/fridge/$id/', data: body);
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) setState(() => _error = 'Ошибка: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const Text('Редактировать продукт',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 14),

              // ── CATEGORY ──
              const Text('Категория',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              if (_loadingMeta)
                const Padding(
                  padding: EdgeInsets.all(8),
                  child: LinearProgressIndicator(),
                )
              else
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: _categories.map((c) {
                    final slug = c['slug'] as String?;
                    final selected = slug != null && slug == _selectedSlug;
                    final bg = _parseColor(c['color'] as String?);
                    return ChoiceChip(
                      selected: selected,
                      backgroundColor: bg,
                      selectedColor: bg,
                      side: BorderSide(
                        color: selected ? Colors.black : Colors.transparent,
                        width: selected ? 1.5 : 0,
                      ),
                      label: Text(
                        '${c['icon'] ?? ''} ${c['name_ru'] ?? ''}',
                        style: const TextStyle(fontSize: 12),
                      ),
                      onSelected: (_) => setState(() => _selectedSlug = slug),
                    );
                  }).toList(),
                ),
              const SizedBox(height: 16),

              TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Название *'),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Обязательно' : null,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextFormField(
                      controller: _qtyCtrl,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Кол-во *'),
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) return 'Обязательно';
                        final n = double.tryParse(v.replaceAll(',', '.'));
                        if (n == null || n <= 0) return 'Число > 0';
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: DropdownButtonFormField<String>(
                      value: _unit,
                      decoration: const InputDecoration(labelText: 'Ед. изм. *'),
                      items: _units
                          .map((u) =>
                              DropdownMenuItem(value: u, child: Text(u)))
                          .toList(),
                      onChanged: (v) =>
                          setState(() => _unit = v ?? _UNITS.first),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              InkWell(
                onTap: _pickDate,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Срок годности *',
                    suffixIcon: Icon(Icons.calendar_today),
                  ),
                  child: Text(
                    _expiry == null
                        ? 'Выбрать дату'
                        : DateFormat('dd.MM.yyyy').format(_expiry!),
                  ),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!,
                    style: const TextStyle(color: Colors.red, fontSize: 13)),
              ],
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Сохранить'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
