// MG_MYPRODUCTS: продукты семьи — посмотреть, поправить, удалить.
//
// Заводить свои продукты стало легко (галочка в дневнике включена по
// умолчанию), а управлять ими было негде: опечатку в названии не исправить,
// ошибку в КБЖУ не поправить, лишнее не удалить.
//
// Каталожные продукты сюда не попадают: их правит только админка, и сервер
// откажет, даже если запрос как-то дойдёт (см. _guard_own во вьюхе).

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/tall_dialog.dart'; // MG_TALLDIALOG

/// Число из ответа сервера: он шлёт и числа, и строки вроде «220.00».
num? _num(Object? v) {
  if (v == null) return null;
  if (v is num) return v;
  return double.tryParse(v.toString().replaceAll(',', '.'));
}

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

  /// MG_KBJUMATCH: записи без КБЖУ. Считаются из уже загруженного списка —
  /// отдельный запрос ради числа, которое и так на руках, лишний.
  List<Map<String, dynamic>> get _noKbju => _items.where((p) {
        final n = (p['nutrition'] is Map) ? Map<String, dynamic>.from(p['nutrition'] as Map) : const {};
        return _num(p['calories_per_100g']) == null && n.isEmpty;
      }).toList();

  Future<void> _bulkFill() async {
    final filled = await showModalBottomSheet<int>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _KbjuBulkSheet(apiClient: widget.apiClient, products: _noKbju),
    );
    if (filled != null && filled > 0) await _load();
  }

  /// Плашка «у стольких-то нет КБЖУ».
  ///
  /// Молча заполнить их нельзя: это записи человека, и пустое поле там может
  /// значить «мой фарш не такой, как в каталоге». Поэтому плашка предлагает,
  /// а решает он — и каждую строку отдельно.
  Widget _gapBanner(BuildContext context) {
    final n = _noKbju.length;
    if (n == 0) return const SizedBox.shrink();
    final tokens = context.tokens;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
      decoration: BoxDecoration(
        color: tokens.surfaceAlt,
        border: Border.all(color: tokens.border),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              n == 1 ? 'У одного продукта не указано КБЖУ' : 'У $n продуктов не указано КБЖУ',
              style: const TextStyle(fontSize: 13),
            ),
          ),
          TextButton(onPressed: _bulkFill, child: const Text('Заполнить')),
        ],
      ),
    );
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
      // MG_NAVBARINSET: отступ снизу под системную полосу навигации — экран
      // открывается поверх, нижней панели у него нет. См. подробности в
      // recipes/screens/recipe_detail_screen.dart.
      body: SafeArea(
        top: false,
        child: _loading
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
                        // Плашка про пустое КБЖУ идёт первой строкой — но
                        // только когда есть о чём говорить, иначе над списком
                        // повиснет пустая строка с разделителем.
                        itemCount: _items.length + (_noKbju.isEmpty ? 0 : 1),
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (_, index) {
                          final offset = _noKbju.isEmpty ? 0 : 1;
                          if (offset == 1 && index == 0) return _gapBanner(context);
                          final i = index - offset;
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

  // MG_KBJUMATCH: что каталог предлагает под набранное название.
  //
  // Человек набирает «фарш телятина» и сохраняет запись без чисел, хотя в
  // каталоге лежит «Фарш из телятины» с 220 ккал. Обычный поиск его не
  // показывает: он требует слова подряд и в том же порядке, а между ними
  // стоит «из». Подсказка спрашивает сервер по набору слов.
  Map<String, dynamic>? _hint;
  String _hintFor = '';
  Timer? _hintTimer;

  String _s(Object? v) => v == null ? '' : v.toString();

  /// Пусты ли все поля КБЖУ. Подсказка лезет только туда, где пусто:
  /// перебивать числа, которые человек уже вписал, нельзя.
  bool get _kbjuEmpty =>
      _cal.text.trim().isEmpty &&
      _prot.text.trim().isEmpty &&
      _fat.text.trim().isEmpty &&
      _carb.text.trim().isEmpty;

  void _scheduleHint() {
    _hintTimer?.cancel();
    _hintTimer = Timer(const Duration(milliseconds: 400), _askHint);
  }

  Future<void> _askHint() async {
    final name = _name.text.trim();
    if (name.length < 2 || !_kbjuEmpty) {
      if (_hint != null && mounted) setState(() => _hint = null);
      return;
    }
    if (name == _hintFor) return;
    _hintFor = name;
    try {
      final r = await widget.apiClient.get(
        '/fridge/products/kbju-suggest/',
        params: {'name': name},
      );
      final list = ((r as Map?)?['suggestions'] as List?) ?? const [];
      if (!mounted) return;
      setState(() => _hint = list.isEmpty ? null : Map<String, dynamic>.from(list.first as Map));
    } catch (_) {
      // Молча: подсказка — удобство, а не часть сохранения. Ругаться на
      // человека из-за неё значит мешать ему делать то, зачем он пришёл.
      if (mounted) setState(() => _hint = null);
    }
  }

  void _applyHint() {
    final h = _hint;
    if (h == null) return;
    final n = (h['nutrition'] is Map) ? Map<String, dynamic>.from(h['nutrition'] as Map) : <String, dynamic>{};
    setState(() {
      _cal.text = _s(h['calories_per_100g']);
      _prot.text = _s(n['proteins']);
      _fat.text = _s(n['fats']);
      _carb.text = _s(n['carbs']);
      if (_cat == null && h['category_id'] != null) {
        for (final c in widget.categories) {
          if (c['id'] == h['category_id']) {
            _cat = c;
            break;
          }
        }
      }
      _hint = null;
    });
  }

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
    // Правка записи, у которой КБЖУ не указано, — тот же случай, что и ввод
    // нового названия: спросить каталог стоит сразу, не дожидаясь правки.
    if (_name.text.trim().length >= 2 && _kbjuEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _askHint());
    }
  }

  @override
  void dispose() {
    _hintTimer?.cancel();
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

  /// Плашка «в каталоге есть такое — подставить».
  ///
  /// Показывается, а не применяется сама. Записать чужие числа в продукт
  /// человека молча нельзя: он мог завести свой «фарш» именно потому, что
  /// каталожный ему не подходит.
  Widget _hintCard(BuildContext context) {
    final h = _hint!;
    final n = (h['nutrition'] is Map) ? Map<String, dynamic>.from(h['nutrition'] as Map) : <String, dynamic>{};
    final parts = <String>[
      if (h['calories_per_100g'] != null) '${_num(h['calories_per_100g'])?.round()} ккал',
      if (n['proteins'] != null) 'Б ${n['proteins']}',
      if (n['fats'] != null) 'Ж ${n['fats']}',
      if (n['carbs'] != null) 'У ${n['carbs']}',
    ];
    final tokens = context.tokens;
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
      decoration: BoxDecoration(
        color: tokens.surfaceAlt,
        border: Border.all(color: tokens.border),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'В каталоге есть «${h['name']}»',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                ),
                if (parts.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      '${parts.join(' · ')} (на 100 г)',
                      style: TextStyle(fontSize: 12, color: tokens.textSecondary),
                    ),
                  ),
              ],
            ),
          ),
          TextButton(onPressed: _applyHint, child: const Text('Подставить')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    const kb = TextInputType.numberWithOptions(decimal: true);
    // MG_TALLDIALOG: форма с полями и клавиатурой — тот самый случай, где
    // обычный диалог ужимается в остаток экрана и режет содержимое.
    return TallDialog(
      title: widget.product == null ? 'Новый продукт' : 'Правка продукта',
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
      child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _name,
                decoration: _dec('Название'),
                onChanged: (_) => _scheduleHint(),
              ),
              if (_hint != null) _hintCard(context),
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
    );
  }
}

// MG_KBJUMATCH: заполнить КБЖУ сразу у нескольких своих продуктов.
//
// Экран «Мои продукты» видит, у скольких записей чисел нет, и предлагает
// закрыть их разом. Лист спрашивает каталог по каждому названию и показывает,
// что именно нашлось, — отметки человек расставляет сам.
//
// Почему не заполняем молча, даже когда совпадение точное: это записи
// человека, и пустое КБЖУ там может означать «мой фарш не такой, как в
// каталоге». Молчаливая подстановка чужих чисел разойдётся по дневнику и
// меню, а человек об этом не узнает.
//
// Почему отмечено по умолчанию только точное совпадение: частичное («фарш
// телятина» против «фарш телячий нежирный») нередко другой продукт, и
// отметка по умолчанию превратила бы подсказку в ловушку — человек жмёт
// «подставить», не вчитываясь.
class _KbjuBulkSheet extends StatefulWidget {
  final ApiClient apiClient;
  final List<Map<String, dynamic>> products;

  const _KbjuBulkSheet({required this.apiClient, required this.products});

  @override
  State<_KbjuBulkSheet> createState() => _KbjuBulkSheetState();
}

class _KbjuBulkSheetState extends State<_KbjuBulkSheet> {
  /// id продукта -> подсказка из каталога.
  final Map<int, Map<String, dynamic>> _hints = {};

  /// id продукта -> отмечен ли к подстановке.
  final Map<int, bool> _checked = {};

  bool _loading = true;
  bool _saving = false;
  int _done = 0;

  @override
  void initState() {
    super.initState();
    _ask();
  }

  Future<void> _ask() async {
    for (final p in widget.products) {
      final id = p['id'] as int?;
      final name = (p['name'] ?? '').toString().trim();
      if (id == null || name.length < 2) continue;
      try {
        final r = await widget.apiClient.get(
          '/fridge/products/kbju-suggest/',
          params: {'name': name},
        );
        final list = ((r as Map?)?['suggestions'] as List?) ?? const [];
        if (list.isEmpty) continue;
        final hint = Map<String, dynamic>.from(list.first as Map);
        _hints[id] = hint;
        _checked[id] = (_num(hint['match']) ?? 0) >= 1.0;
      } catch (_) {
        // Молча: не нашли так не нашли, строка просто не появится.
      }
      if (mounted) setState(() {});
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _apply() async {
    setState(() => _saving = true);
    var ok = 0;
    for (final p in widget.products) {
      final id = p['id'] as int?;
      if (id == null || _checked[id] != true) continue;
      final h = _hints[id];
      if (h == null) continue;
      try {
        await widget.apiClient.patch('/fridge/products/$id/', data: {
          'calories_per_100g': h['calories_per_100g'],
          'nutrition': h['nutrition'] ?? {},
        });
        ok += 1;
      } catch (_) {
        // Одна неудача не должна рушить остальные: продолжаем и честно
        // показываем, сколько получилось.
      }
      if (mounted) setState(() => _done = ok);
    }
    if (!mounted) return;
    Navigator.pop(context, ok);
  }

  String _kbjuOf(Map<String, dynamic> h) {
    final n = (h['nutrition'] is Map) ? Map<String, dynamic>.from(h['nutrition'] as Map) : const {};
    final parts = <String>[
      if (h['calories_per_100g'] != null) '${_num(h['calories_per_100g'])?.round()} ккал',
      if (n['proteins'] != null) 'Б ${n['proteins']}',
      if (n['fats'] != null) 'Ж ${n['fats']}',
      if (n['carbs'] != null) 'У ${n['carbs']}',
    ];
    return parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final withHint = widget.products.where((p) => _hints.containsKey(p['id'])).toList();
    final picked = _checked.values.where((v) => v).length;

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
              child: Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Заполнить КБЖУ из каталога',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
                    ),
                  ),
                  if (_loading)
                    const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                ],
              ),
            ),
            Flexible(
              child: _loading && withHint.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.fromLTRB(16, 8, 16, 24),
                      child: Text('Ищу в каталоге…'),
                    )
                  : withHint.isEmpty
                      ? const Padding(
                          padding: EdgeInsets.fromLTRB(16, 8, 16, 24),
                          child: Text(
                            'В каталоге не нашлось ничего похожего. Впишите КБЖУ руками '
                            'в карточке продукта.',
                          ),
                        )
                      : ListView.separated(
                          shrinkWrap: true,
                          itemCount: withHint.length,
                          separatorBuilder: (_, __) => Divider(height: 1, color: tokens.border),
                          itemBuilder: (_, i) {
                            final p = withHint[i];
                            final id = p['id'] as int;
                            final h = _hints[id]!;
                            final exact = (_num(h['match']) ?? 0) >= 1.0;
                            return CheckboxListTile(
                              value: _checked[id] ?? false,
                              onChanged: _saving ? null : (v) => setState(() => _checked[id] = v ?? false),
                              controlAffinity: ListTileControlAffinity.leading,
                              title: Text('${p['name']}', style: const TextStyle(fontSize: 15)),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '→ ${h['name']}',
                                    style: TextStyle(fontSize: 13, color: tokens.textSecondary),
                                  ),
                                  Text(
                                    _kbjuOf(h) + (exact ? '' : ' · похоже, но не точно'),
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: exact ? tokens.textSecondary : const Color(0xFFB45309),
                                    ),
                                  ),
                                ],
                              ),
                              isThreeLine: true,
                            );
                          },
                        ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: Row(
                children: [
                  TextButton(
                    onPressed: _saving ? null : () => Navigator.pop(context, 0),
                    child: const Text('Отмена'),
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: (_saving || picked == 0) ? null : _apply,
                    child: Text(_saving ? 'Записываю… $_done' : 'Подставить ($picked)'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
