import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';
import '../bloc/fridge_bloc.dart';
import 'barcode_scanner_screen.dart';
import 'recognize_photo_flow.dart';

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
  // MG-610 focus
  final _nameFocus = FocusNode();
  final _qtyFocus = FocusNode();
  final _categoryKey = GlobalKey();
  final _dateKey = GlobalKey();
  bool _highlightCategory = false;
  bool _highlightDate = false;
  String _unit = _UNITS.first;
  DateTime? _expiry;
  int? _productId;
  String? _imageUrl;
  bool _loadingBarcode = false;
  // MG_SCANSRC: что нашлось по штрих-коду — КБЖУ строкой и оговорка, если это
  // догадка модели, а не запись из справочника. Цифры удобнее сверить с
  // этикеткой сразу, пока упаковка в руках.
  String? _scanKbju;
  bool _scanGuess = false;
  // MG_FAMBARCODE: код последней отсканированной упаковки — уходит вместе с
  // позицией, чтобы сервер запомнил название, если товар не опознан.
  String? _scannedCode;
  String? _error;

  // MG-609 additions
  List<Map<String, dynamic>> _categories = [];
  Map<String, dynamic>? _selectedCategory; // {id, slug, name_ru, icon, color, ...}
  List<Map<String, dynamic>> _seedProducts = [];     // for the chosen category
  List<Map<String, dynamic>> _history = [];          // family history
  bool _loadingMeta = true;

  // MG_MANUALPROD: живой поиск по каталогу прямо в поле «Название». Раньше
  // форма подсказывала только базовые продукты выбранной категории и историю
  // холодильника — свои продукты (заведённые вручную или из дневника) не
  // находились никак.
  //
  // Отдельного поля поиска нет намеренно: «найти существующее» и «вписать
  // новое» — одно действие, и раздваивать его значит требовать от человека
  // заранее знать, есть продукт в базе или нет.
  List<Map<String, dynamic>> _searchResults = const [];
  bool _searchLoading = false;
  // Подсказки открывает только набор текста руками: скан, фото, история и
  // базовые продукты тоже пишут в «Название», и выпадающий им в ответ список
  // выглядел бы как сбой.
  bool _searchOpen = false;
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    setState(() => _loadingMeta = true);
    try {
      final results = await Future.wait([
        widget.apiClient.get('/fridge/categories/'),
        widget.apiClient.get('/fridge/products/history/', params: {'limit': '40'}),
      ]);
      final cats = results[0];
      final hist = results[1];
      setState(() {
        _categories = (cats is List)
            ? cats.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList()
            : [];
        _history = (hist is List)
            ? hist.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList()
            : [];
      });
    } catch (_) {/* non-fatal */}
    if (mounted) setState(() => _loadingMeta = false);
  }

  Future<void> _loadSeedForCategory(Map<String, dynamic> cat) async {
    final slug = cat['slug'] as String?;
    if (slug == null || slug.isEmpty) return;
    try {
      final r = await widget.apiClient.get(
        '/fridge/products/',
        params: {'category': slug, 'seed': '1'},
      );
      if (r is List) {
        setState(() {
          _seedProducts = r.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
        });
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _nameCtrl.dispose();
    _qtyCtrl.dispose();
    _nameFocus.dispose();
    _qtyFocus.dispose();
    super.dispose();
  }

  void _scrollToKey(GlobalKey key) {
    final ctx = key.currentContext;
    if (ctx != null) {
      Scrollable.ensureVisible(ctx,
          duration: const Duration(milliseconds: 300),
          alignment: 0.3);
    }
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

  /// MG_SCANSRC: «121 ккал · Б 16 · Ж 5 · У 3 (на 100 г)» либо null, если
  /// сервер ничего про КБЖУ не знает: пустое «0 ккал» хуже молчания.
  static String? _kbjuLine(Map<String, dynamic> m) {
    String? fmt(dynamic v) {
      final n = v is num ? v.toDouble() : double.tryParse('${v ?? ''}');
      if (n == null) return null;
      return n == n.roundToDouble() ? '${n.round()}' : n.toStringAsFixed(1);
    }

    final parts = <String>[];
    final cals = fmt(m['calories_per_100g']);
    if (cals != null) parts.add('$cals ккал');
    final nutrition = (m['nutrition'] is Map)
        ? Map<String, dynamic>.from(m['nutrition'] as Map)
        : <String, dynamic>{};
    for (final e in const [['proteins', 'Б'], ['fats', 'Ж'], ['carbs', 'У']]) {
      final v = fmt(nutrition[e[0]]);
      if (v != null) parts.add('${e[1]} $v');
    }
    if (parts.isEmpty) return null;
    return '${parts.join(' · ')} (на 100 г)';
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
        _scanKbju = _kbjuLine(m); // MG_SCANSRC
        _scanGuess = m['low_confidence'] == true;
        _scannedCode = scanned; // MG_FAMBARCODE
        // MG_FAMBARCODE: без названия поле оставляем пустым. Раньше сюда
        // подставлялся сам код — и он же уехал бы в память семьи как название.
        final found = (m['name'] as String?) ?? '';
        if (found.isNotEmpty) _nameCtrl.text = found;
        _productId = m['id'] as int?;
        _closeSuggest();
        _imageUrl = m['image_url'] as String?;
        final du = (m['default_unit'] as String?) ?? '';
        if (du.isNotEmpty && _UNITS.contains(du)) _unit = du;
        // Try to set category from product response.
        final catSlug = m['category_slug'] as String?;
        if (catSlug != null && catSlug.isNotEmpty) {
          final found = _categories.where((c) => c['slug'] == catSlug);
          if (found.isNotEmpty) {
            _selectedCategory = found.first;
            _loadSeedForCategory(_selectedCategory!);
          }
        }
      });
    } catch (e) {
      final msg = e.toString();
      setState(() {
        _scanKbju = null; // MG_SCANSRC
        _scanGuess = false;
        // MG_FAMBARCODE: код всё равно запоминаем — по названию, которое
        // впишет человек, и в следующий раз подставим сами.
        _scannedCode = scanned;
        _error = msg.contains('404') || msg.contains('not found')
            ? 'Штрих-код не найден. Впишите название — в следующий раз подставим сами.'
            : 'Ошибка поиска: $msg';
      });
    } finally {
      if (mounted) setState(() => _loadingBarcode = false);
    }
  }

  // MG_MANUALPROD: дебаунс-поиск по каталогу (общий + продукты семьи).
  void _onNameTyped(String value) {
    // Набор текста руками разрывает связь с продуктом: иначе позиция осталась
    // бы привязана к прежнему продукту, а называлась бы уже иначе.
    _productId = null;
    _searchOpen = true;
    _searchDebounce?.cancel();
    final q = value.trim();
    if (q.length < 2) {
      setState(() => _searchResults = const []);
      return;
    }
    setState(() => _searchLoading = true);
    _searchDebounce = Timer(const Duration(milliseconds: 300), () async {
      try {
        final r = await widget.apiClient
            .get('/fridge/products/search/', params: {'q': q});
        // Ответ пагинирован DRF; на всякий случай терпим и голый список.
        final list = r is Map ? (r['results'] as List? ?? const []) : (r as List? ?? const []);
        if (!mounted) return;
        setState(() {
          _searchResults =
              list.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
          _searchLoading = false;
        });
      } catch (_) {
        if (!mounted) return;
        setState(() {
          _searchResults = const [];
          _searchLoading = false;
        });
      }
    });
  }

  void _closeSuggest() {
    _searchDebounce?.cancel();
    _searchOpen = false;
    _searchResults = const [];
  }

  void _applyProduct(Map<String, dynamic> p) {
    setState(() {
      _nameCtrl.text = (p['name'] as String?) ?? '';
      _productId = p['id'] as int?;
      final img = p['image_url'] as String?;
      if (img != null && img.isNotEmpty) _imageUrl = img;
      final unit = p['default_unit'] as String?;
      if (unit != null && _UNITS.contains(unit)) _unit = unit;
      final slug = p['category_slug'] as String?;
      if (slug != null && slug.isNotEmpty) {
        for (final c in _categories) {
          if (c['slug'] == slug) {
            _selectedCategory = c;
            break;
          }
        }
      }
      _closeSuggest();
    });
  }

  void _applyHistory(Map<String, dynamic> h) {
    setState(() {
      _nameCtrl.text = (h['name'] as String?) ?? '';
      _productId = h['product_id'] as int?;
      _closeSuggest();
      _imageUrl = h['image_url'] as String?;
      final du = (h['default_unit'] as String?) ?? '';
      if (du.isNotEmpty && _UNITS.contains(du)) _unit = du;
      final slug = h['category_slug'] as String?;
      if (slug != null && slug.isNotEmpty) {
        final found = _categories.where((c) => c['slug'] == slug);
        if (found.isNotEmpty) {
          _selectedCategory = found.first;
          _loadSeedForCategory(_selectedCategory!);
        }
      }
    });
  }

  void _applySeed(Map<String, dynamic> p) {
    setState(() {
      _nameCtrl.text = (p['name'] as String?) ?? '';
      _productId = p['id'] as int?;
      _imageUrl = p['image_url'] as String?;
      final du = (p['default_unit'] as String?) ?? '';
      if (du.isNotEmpty && _UNITS.contains(du)) _unit = du;
      _closeSuggest();
    });
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

  void _submit() {
    // MG-610 focus: highlight & focus the first missing required field.
    setState(() {
      _highlightCategory = false;
      _highlightDate = false;
    });

    if (_selectedCategory == null) {
      setState(() {
        _error = 'Выберите категорию';
        _highlightCategory = true;
      });
      _scrollToKey(_categoryKey);
      return;
    }

    final nameEmpty = _nameCtrl.text.trim().isEmpty;
    final qtyVal = double.tryParse(_qtyCtrl.text.replaceAll(',', '.'));
    final qtyBad = _qtyCtrl.text.trim().isEmpty || qtyVal == null || qtyVal <= 0;

    if (nameEmpty) {
      _formKey.currentState!.validate();
      setState(() => _error = 'Укажите название');
      _nameFocus.requestFocus();
      return;
    }
    if (qtyBad) {
      _formKey.currentState!.validate();
      setState(() => _error = 'Укажите количество (> 0)');
      _qtyFocus.requestFocus();
      return;
    }
    if (_expiry == null) {
      setState(() {
        _error = 'Укажите срок годности';
        _highlightDate = true;
      });
      _scrollToKey(_dateKey);
      return;
    }

    if (!_formKey.currentState!.validate()) return;

    final qty = qtyVal ?? 0;
    final rec = _lastRecognized; // MENUGEN_KBJU
    final recMatchesName =
        rec != null && rec.name.trim() == _nameCtrl.text.trim();
    context.read<FridgeBloc>().add(FridgeItemAdded(
          name: _nameCtrl.text.trim(),
          quantity: qty,
          unit: _unit,
          expiryDate: DateFormat('yyyy-MM-dd').format(_expiry!),
          productId: _productId,
          categorySlug: (_selectedCategory?['slug'] as String?) ??
              (recMatchesName ? (rec.categorySlug ?? rec.category) : null),
          caloriesPer100g: recMatchesName ? rec.caloriesPer100g : null,
          nutrition: recMatchesName ? rec.nutrition : null,
          barcode: _scannedCode, // MG_FAMBARCODE
        ));
    Navigator.of(context).pop();
  }

  Future<void> _recognizePhoto() async {

    final mode = await askRecognizeMode(context);

    if (mode == null) return;

    final file = await pickPhoto(context);

    if (file == null) return;

    setState(() {

      _loadingBarcode = true;

      _error = null;

    });

    try {

      final products = await recognizePhoto(

        apiClient: widget.apiClient,

        file: file,

        mode: mode,

      );

      if (!mounted) return;

      if (mode == 'single') {

        if (products.isEmpty) {

          setState(() => _error = 'Продукт не распознан. Заполните вручную.');

        } else {

          _applyRecognized(products.first);

        }

      } else {

        final chosen = await Navigator.of(context).push<List<RecognizedProduct>>(

          MaterialPageRoute(

            builder: (_) => RecognizedProductsPicker(products: products),

          ),

        );

        if (chosen != null && chosen.isNotEmpty) {

          _addRecognizedBatch(chosen);

        }

      }

    } catch (e) {

      if (mounted) setState(() => _error = 'Ошибка распознавания: $e');

    } finally {

      if (mounted) setState(() => _loadingBarcode = false);

    }

  }


  // MENUGEN_KBJU: remember last recognized product so manual save forwards KBJU.
  RecognizedProduct? _lastRecognized;

  void _applyRecognized(RecognizedProduct p) {
    _lastRecognized = p;

    setState(() {

      _nameCtrl.text = p.name;

      _productId = null;

      _closeSuggest();

      final q = p.quantity;

      if (q != null && q.isNotEmpty) {

        final num = RegExp(r'[0-9]+([.,][0-9]+)?').firstMatch(q)?.group(0);

        if (num != null) _qtyCtrl.text = num.replaceAll(',', '.');

      }

      if (p.categorySlug != null) {

        for (final c in _categories) {

          if (c['slug'] == p.categorySlug) {

            _selectedCategory = c;

            break;

          }

        }

      }

    });

  }


  void _addRecognizedBatch(List<RecognizedProduct> chosen) {

    final bloc = context.read<FridgeBloc>();

    final today = DateTime.now();

    final expiry = DateFormat('yyyy-MM-dd').format(

      today.add(const Duration(days: 7)),

    );

    for (final p in chosen) {

      double qty = 1;

      final q = p.quantity;

      if (q != null) {

        final num = RegExp(r'[0-9]+([.,][0-9]+)?').firstMatch(q)?.group(0);

        if (num != null) {

          qty = double.tryParse(num.replaceAll(',', '.')) ?? 1;

        }

      }

      bloc.add(FridgeItemAdded(

        name: p.name,

        quantity: qty,

        unit: _UNITS.first,

        expiryDate: expiry,

        productId: null,

        categorySlug: p.categorySlug ?? p.category, // MENUGEN_KBJU

        caloriesPer100g: p.caloriesPer100g,

        nutrition: p.nutrition,

      ));

    }

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
                width: 40,
                height: 4,
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
                    tooltip: 'Распознать по фото',
                    onPressed: _loadingBarcode ? null : _recognizePhoto,
                    icon: const Icon(Icons.photo_camera_outlined),
                  ),
                  IconButton(
                    onPressed: _loadingBarcode ? null : _scanAndLookup,
                    icon: _loadingBarcode
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.qr_code_scanner),
                    tooltip: 'Сканировать штрих-код',
                  ),
                ],
              ),
              // MG_SCANSRC: результат скана — справочно, до сохранения.
              if (_scanKbju != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(_scanKbju!,
                      style: const TextStyle(fontSize: 12, color: Colors.black54)),
                ),
              if (_scanGuess)
                const Padding(
                  padding: EdgeInsets.only(bottom: 4),
                  child: Text(
                    'Товара нет в справочнике — данные подобраны ИИ по коду. Проверьте по упаковке.',
                    style: TextStyle(fontSize: 12, color: Color(0xFFB45309)),
                  ),
                ),
              const SizedBox(height: 6),

              // ── HISTORY ──
              if (_history.isNotEmpty) ...[
                const Text('Из истории',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                SizedBox(
                  height: 36,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _history.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 6),
                    itemBuilder: (_, i) {
                      final h = _history[i];
                      final icon = (h['category_icon'] as String?) ?? '';
                      return ActionChip(
                        avatar: icon.isNotEmpty ? Text(icon) : null,
                        label: Text(h['name'] as String? ?? ''),
                        onPressed: () => _applyHistory(h),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 14),
              ],

              // ── CATEGORY ──
              const Text('Категория *',
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
                    final selected = _selectedCategory != null &&
                        _selectedCategory!['id'] == c['id'];
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
                      onSelected: (_) {
                        setState(() => _selectedCategory = c);
                        _loadSeedForCategory(c);
                      },
                    );
                  }).toList(),
                ),

              // ── SEED PRODUCTS for chosen category ──
              if (_selectedCategory != null && _seedProducts.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Базовые продукты',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                SizedBox(
                  height: 36,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _seedProducts.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 6),
                    itemBuilder: (_, i) {
                      final p = _seedProducts[i];
                      return ActionChip(
                        label: Text(p['name'] as String? ?? ''),
                        onPressed: () => _applySeed(p),
                      );
                    },
                  ),
                ),
              ],

              const SizedBox(height: 16),

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

              // MG_MANUALPROD: поле-подсказка. Совпало с каталогом — берём
              // готовый продукт (с категорией и единицей); не совпало —
              // остаётся вписанное, как и раньше.
              TextFormField(
                controller: _nameCtrl,
                decoration: InputDecoration(
                  labelText: 'Название *',
                  helperText: 'Начните вводить — предложим из каталога',
                  suffixIcon: _searchLoading
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
                textInputAction: TextInputAction.next,
                onChanged: _onNameTyped,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Обязательно' : null,
              ),
              if (_searchOpen && _searchResults.isNotEmpty)
                Container(
                  margin: const EdgeInsets.only(top: 4),
                  constraints: const BoxConstraints(maxHeight: 180),
                  decoration: BoxDecoration(
                    border: Border.all(color: Theme.of(context).dividerColor),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: ListView.builder(
                    shrinkWrap: true,
                    itemCount: _searchResults.length,
                    itemBuilder: (_, i) {
                      final p = _searchResults[i];
                      final own = p['is_own'] == true;
                      return ListTile(
                        dense: true,
                        title: Text(
                          '${p['name'] ?? ''}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: own ? const Text('своё') : null,
                        onTap: () => _applyProduct(p),
                      );
                    },
                  ),
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
                Text(_error!,
                    style: const TextStyle(color: Colors.red, fontSize: 13)),
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
