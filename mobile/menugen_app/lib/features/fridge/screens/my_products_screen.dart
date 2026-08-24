// MG_MYPRODUCTS: продукты семьи — посмотреть, поправить, удалить.
//
// Заводить свои продукты стало легко (галочка в дневнике включена по
// умолчанию), а управлять ими было негде: опечатку в названии не исправить,
// ошибку в КБЖУ не поправить, лишнее не удалить.
//
// Каталожные продукты сюда не попадают: их правит только админка, и сервер
// откажет, даже если запрос как-то дойдёт (см. _guard_own во вьюхе).

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';

class MyProductsScreen extends StatefulWidget {
  final ApiClient apiClient;
  const MyProductsScreen({super.key, required this.apiClient});

  @override
  State<MyProductsScreen> createState() => _MyProductsScreenState();
}

class _MyProductsScreenState extends State<MyProductsScreen> {
  List<Map<String, dynamic>> _items = const [];
  List<Map<String, dynamic>> _categories = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  num? _num(Object? v) {
    if (v == null) return null;
    if (v is num) return v;
    return double.tryParse(v.toString().replaceAll(',', '.'));
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        widget.apiClient.get('/fridge/products/', params: {'own': '1'}),
        widget.apiClient.get('/fridge/categories/'),
      ]);
      if (!mounted) return;
      List<Map<String, dynamic>> asList(Object? r) => r is List
          ? r.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList()
          : const [];
      setState(() {
        _items = asList(results[0]);
        _categories = asList(results[1]);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  // p == null — создание нового продукта.
  Future<void> _edit(Map<String, dynamic>? p) async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => _EditProductDialog(
        apiClient: widget.apiClient,
        product: p,
        categories: _categories,
      ),
    );
    if (saved == true) await _load();
  }

  Future<void> _delete(Map<String, dynamic> p) async {
    // Позиции холодильника переживут удаление (FK стоит SET_NULL), но потеряют
    // связь с КБЖУ и категорией — об этом честно предупреждаем.
    final used = (_num(p['fridge_usage']) ?? 0).toInt();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить продукт?'),
        content: Text(
          used > 0
              ? '«${p['name']}»\n\nНа продукт ссылается позиций в холодильнике: '
                  '$used. Они останутся, но потеряют КБЖУ и категорию.'
              : '«${p['name']}»',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Удалить')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await widget.apiClient.delete('/fridge/products/${p['id']}/');
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось удалить: $e')),
      );
    }
  }

  String _kbjuLine(Map<String, dynamic> p) {
    final n = (p['nutrition'] is Map)
        ? Map<String, dynamic>.from(p['nutrition'] as Map)
        : <String, dynamic>{};
    final cal = _num(p['calories_per_100g']) ?? 0;
    final prot = _num(n['proteins']) ?? 0;
    final fat = _num(n['fats']) ?? 0;
    final carb = _num(n['carbs']) ?? 0;
    if (cal == 0 && prot == 0 && fat == 0 && carb == 0) return 'КБЖУ не указано';
    return '${cal.round()} ккал · Б $prot · Ж $fat · У $carb (на 100 г)';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Мои продукты')),
      // MG_MYPRODUCTS: продукт можно и завести отсюда. Уметь править и удалять,
      // но не создавать — странная половина возможности.
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _loading ? null : () => _edit(null),
        icon: const Icon(Icons.add),
        label: const Text('Продукт'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        FilledButton(onPressed: _load, child: const Text('Повторить')),
                      ],
                    ),
                  ),
                )
              : _items.isEmpty
                  ? const Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                          'Своих продуктов пока нет.\n\nЗаведите продукт кнопкой ниже — '
                          'или внесите его вручную в дневник, оставив галочку '
                          '«Сохранить продукт в каталог».',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey),
                        ),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        itemCount: _items.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final p = _items[i];
                          final used = (_num(p['fridge_usage']) ?? 0).toInt();
                          final cat = (p['category_name'] as String?) ?? 'Без категории';
                          return ListTile(
                            title: Text(
                              '${p['category_icon'] ?? ''} ${p['name'] ?? ''}'.trim(),
                            ),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(_kbjuLine(p), style: const TextStyle(fontSize: 12)),
                                Text(
                                  used > 0 ? '$cat · в холодильнике: $used' : cat,
                                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                                ),
                              ],
                            ),
                            isThreeLine: true,
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  tooltip: 'Править',
                                  icon: const Icon(Icons.edit_outlined),
                                  onPressed: () => _edit(p),
                                ),
                                IconButton(
                                  tooltip: 'Удалить',
                                  icon: const Icon(Icons.delete_outline),
                                  onPressed: () => _delete(p),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}

// Одна форма и на правку, и на создание: разъехавшись, они начали бы принимать
// разный набор полей — а продукт и там и там один и тот же.
// product == null — создание нового.
class _EditProductDialog extends StatefulWidget {
  final ApiClient apiClient;
  final Map<String, dynamic>? product;
  final List<Map<String, dynamic>> categories;
  const _EditProductDialog({
    required this.apiClient,
    required this.product,
    required this.categories,
  });

  @override
  State<_EditProductDialog> createState() => _EditProductDialogState();
}

class _EditProductDialogState extends State<_EditProductDialog> {
  late final TextEditingController _name;
  late final TextEditingController _cal;
  late final TextEditingController _prot;
  late final TextEditingController _fat;
  late final TextEditingController _carb;
  Map<String, dynamic>? _cat;
  bool _saving = false;
  String? _error;

  String _s(Object? v) => v == null ? '' : v.toString();

  @override
  void initState() {
    super.initState();
    final p = widget.product;
    final n = (p?['nutrition'] is Map)
        ? Map<String, dynamic>.from(p!['nutrition'] as Map)
        : <String, dynamic>{};
    // Пустые поля КБЖУ означают «неизвестно», а не ноль.
    _name = TextEditingController(text: _s(p?['name']));
    _cal = TextEditingController(text: _s(p?['calories_per_100g']));
    _prot = TextEditingController(text: _s(n['proteins']));
    _fat = TextEditingController(text: _s(n['fats']));
    _carb = TextEditingController(text: _s(n['carbs']));
    for (final c in widget.categories) {
      if (p != null && c['id'] == p['category_id']) {
        _cat = c;
        break;
      }
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _cal.dispose();
    _prot.dispose();
    _fat.dispose();
    _carb.dispose();
    super.dispose();
  }

  num? _n(TextEditingController c) =>
      double.tryParse(c.text.trim().replaceAll(',', '.'));

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) {
      setState(() => _error = 'Укажите название');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      // КБЖУ пишем только заполненное: пустое поле означает «неизвестно», а не
      // «ноль». Ноль в дневнике выглядел бы как факт.
      final kbju = <String, num>{};
      if (_prot.text.trim().isNotEmpty) kbju['proteins'] = _n(_prot) ?? 0;
      if (_fat.text.trim().isNotEmpty) kbju['fats'] = _n(_fat) ?? 0;
      if (_carb.text.trim().isNotEmpty) kbju['carbs'] = _n(_carb) ?? 0;
      final payload = {
        'name': _name.text.trim(),
        'calories_per_100g': _cal.text.trim().isEmpty ? null : _n(_cal),
        'nutrition': kbju,
        'category_id': _cat?['id'],
      };
      final p = widget.product;
      if (p == null) {
        await widget.apiClient.post('/fridge/products/', data: payload);
      } else {
        await widget.apiClient.patch('/fridge/products/${p['id']}/', data: payload);
      }
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Не удалось сохранить: $e';
        _saving = false;
      });
    }
  }

  InputDecoration _dec(String label) => InputDecoration(labelText: label, isDense: true);

  @override
  Widget build(BuildContext context) {
    const kb = TextInputType.numberWithOptions(decimal: true);
    return AlertDialog(
      title: Text(widget.product == null ? 'Новый продукт' : 'Правка продукта'),
      content: SizedBox(
        width: double.maxFinite,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(controller: _name, decoration: _dec('Название')),
              const SizedBox(height: 12),
              const Text('КБЖУ на 100 г',
                  style: TextStyle(fontSize: 12, color: Colors.grey)),
              const SizedBox(height: 6),
              TextField(controller: _cal, keyboardType: kb, decoration: _dec('Калории (ккал)')),
              const SizedBox(height: 8),
              TextField(controller: _prot, keyboardType: kb, decoration: _dec('Белки (г)')),
              const SizedBox(height: 8),
              TextField(controller: _fat, keyboardType: kb, decoration: _dec('Жиры (г)')),
              const SizedBox(height: 8),
              TextField(controller: _carb, keyboardType: kb, decoration: _dec('Углеводы (г)')),
              if (widget.categories.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Категория',
                    style: TextStyle(fontSize: 12, color: Colors.grey)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: widget.categories.map((c) {
                    final selected = _cat?['id'] == c['id'];
                    return ChoiceChip(
                      label: Text('${c['icon'] ?? ''} ${c['name_ru'] ?? ''}'.trim()),
                      selected: selected,
                      onSelected: (_) => setState(() => _cat = selected ? null : c),
                    );
                  }).toList(),
                ),
              ],
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Text(_error!,
                      style: const TextStyle(color: Colors.red, fontSize: 13)),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context, false),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: Text(_saving ? 'Сохранение…' : 'Сохранить'),
        ),
      ],
    );
  }
}
