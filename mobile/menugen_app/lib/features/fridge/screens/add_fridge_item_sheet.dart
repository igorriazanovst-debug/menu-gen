import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';
import '../bloc/fridge_bloc.dart';
import 'barcode_scanner_screen.dart';

const _UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка'];

class AddFridgeItemSheet extends StatefulWidget {
  final ApiClient apiClient;
  const AddFridgeItemSheet({super.key, required this.apiClient});

  static Future<void> show(BuildContext context, ApiClient apiClient) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: BlocProvider.value(
          value: context.read<FridgeBloc>(),
          child: AddFridgeItemSheet(apiClient: apiClient),
        ),
      ),
    );
  }

  @override
  State<AddFridgeItemSheet> createState() => _AddFridgeItemSheetState();
}

class _AddFridgeItemSheetState extends State<AddFridgeItemSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _qtyCtrl = TextEditingController();
  String _unit = _UNITS.first;
  DateTime? _expiry;
  int? _productId;
  String? _imageUrl;
  bool _loadingBarcode = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _qtyCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _expiry ?? now.add(const Duration(days: 7)),
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 365 * 3)),
    );
    if (picked != null) setState(() => _expiry = picked);
  }

  Future<void> _scanAndLookup() async {
    final scanned = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const BarcodeScannerScreen()),
    );
    if (scanned == null || scanned.isEmpty) return;
    setState(() {
      _loadingBarcode = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.post('/fridge/scan/', data: {'barcode': scanned});
      final m = (r is Map) ? Map<String, dynamic>.from(r) : <String, dynamic>{};
      setState(() {
        _nameCtrl.text = (m['name'] as String?) ?? scanned;
        _productId = m['id'] as int?;
        _imageUrl = m['image_url'] as String?;
        final du = (m['default_unit'] as String?) ?? '';
        if (du.isNotEmpty && _UNITS.contains(du)) _unit = du;
      });
    } catch (e) {
      final msg = e.toString();
      setState(() {
        _error = msg.contains('404') || msg.contains('not found')
            ? 'Штрих-код не найден. Заполните поля вручную.'
            : 'Ошибка поиска: $msg';
      });
    } finally {
      if (mounted) setState(() => _loadingBarcode = false);
    }
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    if (_expiry == null) {
      setState(() => _error = 'Укажите срок годности');
      return;
    }
    final qty = double.tryParse(_qtyCtrl.text.replaceAll(',', '.')) ?? 0;
    context.read<FridgeBloc>().add(FridgeItemAdded(
      name: _nameCtrl.text.trim(),
      quantity: qty,
      unit: _unit,
      expiryDate: DateFormat('yyyy-MM-dd').format(_expiry!),
      productId: _productId,
    ));
    Navigator.of(context).pop();
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
                width: 40, height: 4,
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Row(
                children: [
                  const Text(
                    'Добавить в холодильник',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: _loadingBarcode ? null : _scanAndLookup,
                    icon: _loadingBarcode
                        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.qr_code_scanner),
                    tooltip: 'Сканировать штрих-код',
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (_imageUrl != null && _imageUrl!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.network(
                      _imageUrl!,
                      height: 120,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                    ),
                  ),
                ),
              TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Название *'),
                textInputAction: TextInputAction.next,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Обязательно' : null,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextFormField(
                      controller: _qtyCtrl,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
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
                      items: _UNITS
                          .map((u) => DropdownMenuItem(value: u, child: Text(u)))
                          .toList(),
                      onChanged: (v) => setState(() => _unit = v ?? _UNITS.first),
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
                Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
              ],
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _submit,
                child: const Text('Добавить'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
