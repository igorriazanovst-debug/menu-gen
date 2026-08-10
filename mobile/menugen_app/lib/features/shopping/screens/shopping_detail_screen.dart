// MG_SHOPMOB001 / MG_SHOPBUG_MOB / MG_SHOPBUG_EDITMODE / MG_SHOPMOB_GROUP / MG_SHOPMOB_STRIKE
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:printing/printing.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:shared_preferences/shared_preferences.dart'; // MG_SKIN: persist collapse

import '../bloc/shopping_bloc.dart';
import '../fridge_transfer.dart'; // MG_SHOP2FRIDGE: подтверждение переноса
import '../item_delete.dart'; // MG_SHOPDEL: удаление долгим нажатием
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T10
import '../widgets/item_photo_thumb.dart'; // MG_SHOPIMG: миниатюра + просмотр фото
import '../models/shopping_models.dart';
import 'shopping_access_sheet.dart';
import 'shopping_add_item.dart';
import 'shopping_item_edit_row.dart'; // MG_SHOPBUG_EDITMODE
import 'shopping_item_note_image_sheet.dart'; // MG_SHOPNOTE/IMG

class ShoppingDetailScreen extends StatefulWidget {
  final int listId;
  const ShoppingDetailScreen({super.key, required this.listId});
  @override
  State<ShoppingDetailScreen> createState() => _ShoppingDetailScreenState();
}

class _ShoppingDetailScreenState extends State<ShoppingDetailScreen> {
  // MG_SHOPBUG_EDITMODE: global edit-mode flag.
  bool _editMode = false;
  // MG_T09: show only not-purchased items (view-mode).
  bool _onlyUnpurchased = false;

  // MG_SHOPMOB_GROUP: category metadata (color/icon/sort_order) for zones.
  List<Map<String, dynamic>> _cats = const [];

  // MG_SKIN: развёрнутые группы (slug'и), сохраняются per-list.
  // Пустой набор = всё свёрнуто (поведение при первом открытии).
  Set<String> _expanded = <String>{};
  String get _expandedKey => 'shopping.expanded.${widget.listId}';

  @override
  void initState() {
    super.initState();
    context.read<ShoppingBloc>().add(ShoppingDetailRequested(widget.listId));
    _loadCategories();
    _loadExpanded();
  }

  // MG_SKIN: восстановить сохранённые состояния групп.
  Future<void> _loadExpanded() async {
    try {
      final p = await SharedPreferences.getInstance();
      final saved = p.getStringList(_expandedKey);
      if (saved != null && mounted) setState(() => _expanded = saved.toSet());
    } catch (_) {
      // non-fatal: остаёмся в свёрнутом виде
    }
  }

  // MG_SKIN: свернуть/развернуть группу и сохранить состояние.
  Future<void> _toggleGroup(String slug) async {
    setState(() {
      if (!_expanded.remove(slug)) _expanded.add(slug);
    });
    try {
      final p = await SharedPreferences.getInstance();
      await p.setStringList(_expandedKey, _expanded.toList());
    } catch (_) {
      // non-fatal
    }
  }

  // MG_SHOPMOB_GROUP: fetch rubricator categories for colored zones.
  Future<void> _loadCategories() async {
    try {
      final api = context.read<ShoppingBloc>().apiClient;
      final raw = await api.get('/fridge/categories/');
      final list = (raw is List)
          ? raw
          : (raw is Map && raw['results'] is List)
              ? raw['results'] as List
              : const [];
      final parsed = list
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList();
      if (!mounted) return;
      setState(() => _cats = parsed);
    } catch (_) {
      // Non-fatal: fall back to neutral zones.
    }
  }

  // MG_SHOPMOB_GROUP: parse '#RRGGBB' or '#AARRGGBB' to Color.
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

  Future<void> _print() async {
    final api = context.read<ShoppingBloc>().apiClient;
    final raw = await api.get('/shopping/lists/${widget.listId}/export/');
    final data = ShoppingExportData.fromJson(
        raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{});
    final sym = currencySymbol(data.currency);
    // MG_SHOPBUG_MOB: Noto Sans for Cyrillic in PDF.
    final baseFont = await PdfGoogleFonts.notoSansRegular();
    final boldFont = await PdfGoogleFonts.notoSansBold();
    final italicFont = await PdfGoogleFonts.notoSansItalic();
    final theme = pw.ThemeData.withFont(
        base: baseFont, bold: boldFont, italic: italicFont);
    final doc = pw.Document(theme: theme);
    final createdStr = fmtListDate(data.createdAt);
    doc.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        build: (ctx) => [
          pw.Header(level: 0, text: data.title),
          if (createdStr.isNotEmpty)
            pw.Text('Создан: $createdStr',
                style: pw.TextStyle(
                    fontSize: 11, color: PdfColors.grey700)),
          ...data.categories.expand((cat) => [
                pw.SizedBox(height: 8),
                pw.Text(cat.key.isEmpty ? 'Без категории' : cat.key,
                    style: pw.TextStyle(
                        fontSize: 14, fontWeight: pw.FontWeight.bold)),
                ...cat.value.map((it) {
                  final q = it.quantity != null
                      ? ' — ${it.quantity}${it.unit.isNotEmpty ? ' ${it.unit}' : ''}'
                      : '';
                  final price = it.lineTotal != null
                      ? '   ${fmtMoney(it.lineTotal)} $sym'
                      : (it.pricePerUnit != null
                          ? '   ${fmtMoney(it.pricePerUnit)} $sym'
                          : '');
                  final mark = it.isPurchased ? '[x]' : '[ ]';
                  return pw.Text('$mark ${it.name}$q$price');
                }),
              ]),
          if (data.totalPrice != null) ...[
            pw.SizedBox(height: 12),
            pw.Divider(),
            pw.Text('Итого: ${fmtMoney(data.totalPrice)} $sym',
                style: pw.TextStyle(
                    fontSize: 14, fontWeight: pw.FontWeight.bold)),
          ],
        ],
      ),
    );
    await Printing.layoutPdf(onLayout: (f) => doc.save());
  }

  // MG_SHOP2FRIDGE: push purchased items into the family fridge.
  Future<void> _addToFridge(ShoppingListDetail d) async {
    final api = context.read<ShoppingBloc>().apiClient;
    final messenger = ScaffoldMessenger.of(context);
    // Перенос необратим: обратно позиции придётся убирать вручную.
    final candidates = fridgeCandidates(d.items);
    if (candidates.isEmpty) return;
    if (!await confirmAddToFridge(context, candidates)) return;
    if (!mounted) return;
    try {
      final raw =
          await api.post('/shopping/lists/${widget.listId}/add-to-fridge/');
      final m = raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{};
      final added = (m['added'] as int?) ?? 0;
      if (!mounted) return;
      context.read<ShoppingBloc>().add(ShoppingDetailRequested(widget.listId));
      messenger.showSnackBar(SnackBar(
        content: Text(added > 0
            ? 'Добавлено в холодильник: $added'
            : 'Нет новых купленных товаров для добавления.'),
      ));
    } catch (_) {
      if (!mounted) return;
      messenger.showSnackBar(const SnackBar(
        content: Text('Не удалось добавить в холодильник.'),
      ));
    }
  }

  // MG_SHOPDEL: удаление позиции долгим нажатием — только владельцу списка
  // (у остальных бэкенд ответит 403, поэтому и жест им не предлагается).
  Future<void> _deleteItem(ShoppingListDetail d, ShoppingItem it) async {
    final bloc = context.read<ShoppingBloc>();
    final messenger = ScaffoldMessenger.of(context);
    try {
      final deleted = await deleteShoppingItem(
        context: context,
        api: bloc.apiClient,
        listId: d.id,
        item: it,
      );
      if (!deleted) return;
      bloc.add(ShoppingDetailRequested(d.id));
      messenger.showSnackBar(SnackBar(content: Text('«${it.name}» удалён')));
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Не удалось удалить товар.')),
      );
    }
  }

  // MG_SHOP2FRIDGE: un-checking an item that is in the fridge needs confirmation
  // (it will be removed from the fridge). Returns true if the toggle proceeded.
  Future<void> _onItemToggle(ShoppingListDetail d, ShoppingItem it, bool v) async {
    final bloc = context.read<ShoppingBloc>();
    if (!v && it.inFridge) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Убрать из холодильника?'),
          content: const Text(
              'Этот товар добавлен в холодильник. Снять отметку можно только '
              'вместе с удалением его из холодильника.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Отмена'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Снять и убрать'),
            ),
          ],
        ),
      );
      if (ok != true) return;
      bloc.add(ShoppingToggleItemRequested(d.id, it.id, false,
          removeFromFridge: true));
      return;
    }
    bloc.add(ShoppingToggleItemRequested(d.id, it.id, v));
  }

  void _openAccess() {
    final bloc = context.read<ShoppingBloc>();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => ShoppingAccessSheet(
        apiClient: bloc.apiClient,
        listId: widget.listId,
      ),
    );
  }

  // MG_SHOPMOB_GROUP: group items by category, with color/icon/sort_order
  // metadata from /fridge/categories/. Sort by sort_order (matches web).
  List<_CatGroup> _grouped(List<ShoppingItem> items) {
    final meta = <String, Map<String, dynamic>>{};
    final order = <String, int>{};
    for (var i = 0; i < _cats.length; i++) {
      final c = _cats[i];
      final slug = c['slug'] as String? ?? '';
      meta[slug] = c;
      order[slug] = (c['sort_order'] as int?) ?? i;
    }
    final buckets = <String, List<ShoppingItem>>{};
    final names = <String, String>{};
    for (final it in items) {
      final key = it.categorySlug ?? '__none__';
      buckets.putIfAbsent(key, () => []).add(it);
      final m = meta[key];
      names[key] = (m?['name_ru'] as String?) ??
          it.categoryName ??
          (it.category.isNotEmpty ? it.category : 'Без категории');
    }
    final groups = buckets.entries.map((e) {
      final m = meta[e.key];
      return _CatGroup(
        slug: e.key,
        name: names[e.key] ?? 'Без категории',
        color: _parseColor(m?['color'] as String?),
        icon: (m?['icon'] as String?) ?? '📦',
        sortOrder: order[e.key] ?? 9999,
        items: e.value,
      );
    }).toList()
      ..sort((a, b) => a.sortOrder.compareTo(b.sortOrder));
    return groups;
  }

  Widget? _itemSubtitle(ShoppingItem it, String sym) {
    final parts = <String>[];
    if (it.quantity != null || it.unit.isNotEmpty) {
      parts.add('${it.quantity ?? ''} ${it.unit}'.trim());
    }
    if (it.lineTotal != null) {
      parts.add('${fmtMoney(it.lineTotal)} $sym');
    } else if (it.pricePerUnit != null) {
      parts.add('${fmtMoney(it.pricePerUnit)} $sym/ед.');
    }
    if (parts.isEmpty) return null;
    // MG_SHOPMOB_STRIKE: strikethrough subtitle for purchased items.
    return Text(
      parts.join('  ·  '),
      style: it.isPurchased
          ? const TextStyle(
              decoration: TextDecoration.lineThrough,
              color: Colors.grey,
            )
          : null,
    );
  }

  // MG_SHOPNOTE: подпись + строка комментария под товаром.
  Widget? _itemSubtitleWithNote(ShoppingItem it, String sym) {
    final base = _itemSubtitle(it, sym);
    if (it.note.isEmpty) return base;
    final noteLine = Text(
      '🗒 ${it.note}',
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(fontSize: 12, color: Colors.grey),
    );
    if (base == null) return noteLine;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [base, noteLine],
    );
  }

  // MG_SHOPNOTE/IMG: открыть редактор комментария и изображения товара.
  Future<void> _openNoteImage(ShoppingListDetail d, ShoppingItem it) async {
    final api = context.read<ShoppingBloc>().apiClient;
    final saved = await showItemNoteImageSheet(
      context: context,
      api: api,
      listId: d.id,
      item: it,
    );
    if (saved && mounted) {
      context.read<ShoppingBloc>().add(ShoppingDetailRequested(d.id));
    }
  }

  void _toggleEditMode() {
    final wasEditing = _editMode;
    setState(() => _editMode = !_editMode);
    // Unfocus any field so its blur listener flushes the silent PATCH.
    FocusScope.of(context).unfocus();
    if (wasEditing) {
      // Exited edit mode: refresh from server (gives updated totals).
      // Small delay so any in-flight PATCH finishes first.
      Future<void>.delayed(const Duration(milliseconds: 350), () {
        if (!mounted) return;
        context
            .read<ShoppingBloc>()
            .add(ShoppingDetailRequested(widget.listId));
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ShoppingBloc, ShoppingState>(
      builder: (context, state) {
        if (state is ShoppingLoading || state is ShoppingInitial) {
          return const Scaffold(
              body: Center(child: CircularProgressIndicator()));
        }
        if (state is! ShoppingDetailLoaded) {
          if (state is ShoppingError) {
            // MG_T10: offline -> quiet icon instead of the error text.
            final offline = context.watch<ConnectivityCubit>().state ==
                ConnectivityStatus.offline;
            return Scaffold(
              appBar: AppBar(),
              body: Center(
                child: offline
                    ? const Icon(Icons.cloud_off,
                        size: 48, color: Colors.black26)
                    : Text(state.message),
              ),
            );
          }
          return const Scaffold(body: SizedBox.shrink());
        }
        final d = state.detail;
        final caps = d.capabilities;
        final sym = currencySymbol(d.currency);
        // MG_T09: optional 'unpurchased only' filter.
        final visibleItems = _onlyUnpurchased
            ? d.items.where((it) => !it.isPurchased).toList()
            : d.items;
        final groups = _grouped(visibleItems);
        // MG_SKIN: реальные счётчики по группам (из всех товаров, не из
        // отфильтрованных) — для заголовка «куплено/осталось».
        final totalBy = <String, int>{};
        final boughtBy = <String, int>{};
        for (final it in d.items) {
          final k = it.categorySlug ?? '__none__';
          totalBy[k] = (totalBy[k] ?? 0) + 1;
          if (it.isPurchased) boughtBy[k] = (boughtBy[k] ?? 0) + 1;
        }
        return Scaffold(
          appBar: AppBar(
            // MG_SHOPBUG_MOB: title shows list name + creation date.
            title: Builder(builder: (_) {
              final ds = fmtListDate(d.createdAt);
              if (ds.isEmpty) return Text(d.name);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(d.name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 17)),
                  Text(ds,
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.normal)),
                ],
              );
            }),
            actions: [
              // MG_T09: filter to unpurchased items (view-mode only).
              if (!_editMode && d.items.isNotEmpty)
                IconButton(
                  icon: Icon(_onlyUnpurchased
                      ? Icons.filter_alt
                      : Icons.filter_alt_outlined),
                  tooltip: _onlyUnpurchased
                      ? 'Показать все'
                      : 'Только некупленные',
                  onPressed: () =>
                      setState(() => _onlyUnpurchased = !_onlyUnpurchased),
                ),
              // MG_SHOP2FRIDGE: stock purchased FOOD items into the fridge
              // (non-food — pet food / chemistry / hygiene — excluded).
              if (!_editMode && caps.toggle && fridgeCandidates(d.items).isNotEmpty)
                IconButton(
                  icon: const Icon(Icons.kitchen_outlined),
                  tooltip: 'Добавить купленное в холодильник',
                  onPressed: () => _addToFridge(d),
                ),
              // MG_SHOPBUG_EDITMODE: global edit-mode toggle.
              if (caps.manage)
                IconButton(
                  icon: Icon(_editMode ? Icons.check : Icons.edit),
                  tooltip: _editMode ? 'Готово' : 'Редактировать',
                  onPressed: _toggleEditMode,
                ),
              if (caps.export && !_editMode)
                IconButton(icon: const Icon(Icons.print), onPressed: _print),
              if (caps.manage && !_editMode)
                IconButton(
                    icon: const Icon(Icons.people), onPressed: _openAccess),
              if (caps.manage && !_editMode)
                PopupMenuButton<String>(
                  onSelected: (v) {
                    final bloc = context.read<ShoppingBloc>();
                    if (v == 'archive') {
                      bloc.add(ShoppingArchiveRequested(d.id, !d.isArchived));
                      Navigator.of(context).pop();
                    } else if (v == 'delete') {
                      bloc.add(ShoppingDeleteRequested(d.id));
                      Navigator.of(context).pop();
                    }
                  },
                  itemBuilder: (_) => [
                    PopupMenuItem(
                        value: 'archive',
                        child: Text(
                            d.isArchived ? 'Вернуть из архива' : 'В архив')),
                    const PopupMenuItem(
                        value: 'delete', child: Text('Удалить список')),
                  ],
                ),
            ],
          ),
          body: Column(
            children: [
              Expanded(
                child: d.items.isEmpty
                    ? const Center(child: Text('Список пуст.'))
                    : visibleItems.isEmpty
                        ? const Center(
                            child: Text('Все товары куплены.')) // MG_T09
                        : ListView(
                        children: [
                          // MG_SHOPMOB_GROUP: colored category zones.
                          for (final g in groups)
                            Container(
                              margin: const EdgeInsets.fromLTRB(
                                  12, 8, 12, 4),
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: g.color,
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: Column(
                                crossAxisAlignment:
                                    CrossAxisAlignment.stretch,
                                children: [
                                  // MG_SKIN: тап по заголовку — свернуть/развернуть.
                                  InkWell(
                                    borderRadius: BorderRadius.circular(12),
                                    onTap: () => _toggleGroup(g.slug),
                                    child: Padding(
                                      padding: const EdgeInsets.fromLTRB(
                                          6, 4, 4, 8),
                                      child: Row(
                                        children: [
                                          Text(g.icon,
                                              style: const TextStyle(
                                                  fontSize: 16)),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.start,
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Text(
                                                  g.name,
                                                  style: const TextStyle(
                                                    fontWeight:
                                                        FontWeight.w700,
                                                    fontSize: 13,
                                                  ),
                                                ),
                                                const SizedBox(height: 2),
                                                Builder(builder: (_) {
                                                  final total =
                                                      totalBy[g.slug] ??
                                                          g.items.length;
                                                  final bought =
                                                      boughtBy[g.slug] ?? 0;
                                                  final remaining =
                                                      (total - bought)
                                                          .clamp(0, total);
                                                  final allBought =
                                                      total > 0 &&
                                                          remaining == 0;
                                                  return Text(
                                                    allBought
                                                        ? 'Всё куплено'
                                                        : 'куплено $bought · осталось $remaining',
                                                    style: TextStyle(
                                                      fontSize: 11,
                                                      fontWeight:
                                                          FontWeight.w600,
                                                      color: allBought
                                                          ? Colors.green
                                                              .shade800
                                                          : Colors.black
                                                              .withOpacity(
                                                                  0.6),
                                                    ),
                                                  );
                                                }),
                                              ],
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          // Кол-во товаров в группе.
                                          Container(
                                            constraints:
                                                const BoxConstraints(
                                                    minWidth: 22,
                                                    minHeight: 22),
                                            padding:
                                                const EdgeInsets.symmetric(
                                                    horizontal: 6,
                                                    vertical: 2),
                                            alignment: Alignment.center,
                                            decoration: BoxDecoration(
                                              color: Colors.white
                                                  .withOpacity(0.85),
                                              borderRadius:
                                                  BorderRadius.circular(11),
                                            ),
                                            child: Text(
                                              '${totalBy[g.slug] ?? g.items.length}',
                                              style: const TextStyle(
                                                fontSize: 12,
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                          ),
                                          const SizedBox(width: 4),
                                          AnimatedRotation(
                                            turns: _expanded
                                                    .contains(g.slug)
                                                ? 0.0
                                                : -0.25,
                                            duration: const Duration(
                                                milliseconds: 180),
                                            child: const Icon(
                                                Icons.keyboard_arrow_down,
                                                size: 22),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                  if (_expanded.contains(g.slug))
                                  Container(
                                    decoration: BoxDecoration(
                                      color:
                                          Colors.white.withOpacity(0.7),
                                      borderRadius:
                                          BorderRadius.circular(12),
                                    ),
                                    child: Column(
                                      children: [
                                        for (final it in g.items)
                                          if (_editMode && caps.manage)
                                            // MG_SHOPBUG_EDITMODE: inline editable row.
                                            ShoppingItemEditRow(
                                              key: ValueKey(
                                                  'edit-${it.id}'),
                                              listId: d.id,
                                              item: it,
                                              currency: d.currency,
                                              api: context
                                                  .read<ShoppingBloc>()
                                                  .apiClient,
                                              onDeleted: () => context
                                                  .read<ShoppingBloc>()
                                                  .add(ShoppingDetailRequested(
                                                      d.id)),
                                            )
                                          else
                                            // MG_SHOPDEL: долгое нажатие —
                                            // удаление позиции (владельцу списка).
                                            GestureDetector(
                                              behavior: HitTestBehavior.opaque,
                                              onLongPress: caps.manage
                                                  ? () => _deleteItem(d, it)
                                                  : null,
                                              child: CheckboxListTile(
                                              key: ValueKey(
                                                  'view-${it.id}'),
                                              value: it.isPurchased,
                                              onChanged: caps.toggle
                                                  ? (v) => _onItemToggle(
                                                      d, it, v ?? false)
                                                  : null,
                                              // MG_SHOPMOB_STRIKE: line-through when purchased.
                                              // MG_SHOP2FRIDGE: ❄ marks items in the fridge.
                                              title: Row(
                                                children: [
                                                  // MG_SHOPIMG: миниатюра фото —
                                                  // по нажатию открывается целиком.
                                                  if (it.image != null &&
                                                      it.image!.isNotEmpty) ...[
                                                    ItemPhotoThumb(url: it.image!),
                                                    const SizedBox(width: 8),
                                                  ],
                                                  Flexible(
                                                    child: Text(
                                                      it.name,
                                                      style: it.isPurchased
                                                          ? const TextStyle(
                                                              decoration:
                                                                  TextDecoration
                                                                      .lineThrough,
                                                              color:
                                                                  Colors.grey,
                                                            )
                                                          : null,
                                                    ),
                                                  ),
                                                  if (it.inFridge) ...[
                                                    const SizedBox(width: 6),
                                                    const Icon(Icons.kitchen,
                                                        size: 15,
                                                        color: Colors.blueGrey),
                                                  ],
                                                ],
                                              ),
                                              subtitle: _itemSubtitleWithNote(
                                                  it, sym),
                                              // MG_SHOPNOTE/IMG: кнопка редактора.
                                              secondary: caps.manage
                                                  ? IconButton(
                                                      icon: const Icon(
                                                          Icons
                                                              .sticky_note_2_outlined,
                                                          size: 20),
                                                      tooltip:
                                                          'Комментарий и фото',
                                                      onPressed: () =>
                                                          _openNoteImage(d, it),
                                                    )
                                                  : null,
                                              ),
                                            ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
              ),
              if (d.totalPrice != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 10),
                  color: Colors.black.withOpacity(0.04),
                  child: Text(
                    'Итого: ${fmtMoney(d.totalPrice)} $sym',
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
              // MG_B08: show the add-bar in edit-mode too (replica of web
              // B-07). The list scrolls independently (Expanded > ListView),
              // «Готово» is the check action in the AppBar, and this bar
              // stays pinned below the list in both modes.
              if (caps.manage)
                ShoppingAddItem(
                  apiClient: context.read<ShoppingBloc>().apiClient,
                  currency: d.currency,
                  onSubmit: (payload) => context
                      .read<ShoppingBloc>()
                      .add(ShoppingAddItemRequested(d.id, payload)),
                ),
            ],
          ),
        );
      },
    );
  }
}

// MG_SHOPMOB_GROUP: rich group descriptor for colored category zones.
class _CatGroup {
  final String slug;
  final String name;
  final Color color;
  final String icon;
  final int sortOrder;
  final List<ShoppingItem> items;
  const _CatGroup({
    required this.slug,
    required this.name,
    required this.color,
    required this.icon,
    required this.sortOrder,
    required this.items,
  });
}
