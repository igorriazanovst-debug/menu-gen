// MG_SHOPMOB001 / MG_SHOPBUG_MOB / MG_SHOPBUG_EDITMODE
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:printing/printing.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../bloc/shopping_bloc.dart';
import '../models/shopping_models.dart';
import 'shopping_access_sheet.dart';
import 'shopping_add_item.dart';
import 'shopping_item_edit_row.dart'; // MG_SHOPBUG_EDITMODE

class ShoppingDetailScreen extends StatefulWidget {
  final int listId;
  const ShoppingDetailScreen({super.key, required this.listId});
  @override
  State<ShoppingDetailScreen> createState() => _ShoppingDetailScreenState();
}

class _ShoppingDetailScreenState extends State<ShoppingDetailScreen> {
  // MG_SHOPBUG_EDITMODE: global edit-mode flag.
  bool _editMode = false;

  @override
  void initState() {
    super.initState();
    context.read<ShoppingBloc>().add(ShoppingDetailRequested(widget.listId));
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

  // MG_SHOPMOB001: group items by category, preserving first-seen order.
  List<MapEntry<String, List<ShoppingItem>>> _grouped(
      List<ShoppingItem> items) {
    final buckets = <String, List<ShoppingItem>>{};
    final names = <String, String>{};
    for (final it in items) {
      final key = it.categorySlug ?? '__none__';
      buckets.putIfAbsent(key, () => []).add(it);
      names[key] = it.categoryName ??
          (it.category.isNotEmpty ? it.category : 'Без категории');
    }
    return buckets.entries
        .map((e) => MapEntry(names[e.key] ?? 'Без категории', e.value))
        .toList();
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
    return Text(parts.join('  ·  '));
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
            return Scaffold(
              appBar: AppBar(),
              body: Center(child: Text(state.message)),
            );
          }
          return const Scaffold(body: SizedBox.shrink());
        }
        final d = state.detail;
        final caps = d.capabilities;
        final sym = currencySymbol(d.currency);
        final groups = _grouped(d.items);
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
                    : ListView(
                        children: [
                          for (final g in groups) ...[
                            Padding(
                              padding:
                                  const EdgeInsets.fromLTRB(16, 12, 16, 4),
                              child: Text(
                                g.key,
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                    color: Colors.grey),
                              ),
                            ),
                            for (final it in g.value)
                              if (_editMode && caps.manage)
                                // MG_SHOPBUG_EDITMODE: inline editable row.
                                ShoppingItemEditRow(
                                  key: ValueKey('edit-${it.id}'),
                                  listId: d.id,
                                  item: it,
                                  currency: d.currency,
                                  api: context
                                      .read<ShoppingBloc>()
                                      .apiClient,
                                  onDeleted: () => context
                                      .read<ShoppingBloc>()
                                      .add(ShoppingDetailRequested(d.id)),
                                )
                              else
                                // MG_SHOPBUG_EDITMODE: view-mode (no delete).
                                CheckboxListTile(
                                  key: ValueKey('view-${it.id}'),
                                  value: it.isPurchased,
                                  onChanged: caps.toggle
                                      ? (v) => context
                                          .read<ShoppingBloc>()
                                          .add(ShoppingToggleItemRequested(
                                              d.id, it.id, v ?? false))
                                      : null,
                                  title: Text(it.name),
                                  subtitle: _itemSubtitle(it, sym),
                                ),
                          ],
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
              // MG_SHOPBUG_EDITMODE: hide add-row in edit mode.
              if (caps.manage && !_editMode)
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
