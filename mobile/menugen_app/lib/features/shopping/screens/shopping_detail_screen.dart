// MG_SHOPMOB001
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:printing/printing.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../bloc/shopping_bloc.dart';
import '../models/shopping_models.dart';
import 'shopping_access_sheet.dart';
import 'shopping_add_item.dart';

class ShoppingDetailScreen extends StatefulWidget {
  final int listId;
  const ShoppingDetailScreen({super.key, required this.listId});
  @override
  State<ShoppingDetailScreen> createState() => _ShoppingDetailScreenState();
}

class _ShoppingDetailScreenState extends State<ShoppingDetailScreen> {
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
    final doc = pw.Document();
    doc.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        build: (ctx) => [
          pw.Header(level: 0, text: data.title),
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
                      ? '   ${it.lineTotal} $sym'
                      : (it.pricePerUnit != null
                          ? '   ${it.pricePerUnit} $sym'
                          : '');
                  final mark = it.isPurchased ? '[x]' : '[ ]';
                  return pw.Text('$mark ${it.name}$q$price');
                }),
              ]),
          if (data.totalPrice != null) ...[
            pw.SizedBox(height: 12),
            pw.Divider(),
            pw.Text('Итого: ${data.totalPrice} $sym',
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
      parts.add('${it.lineTotal} $sym');
    } else if (it.pricePerUnit != null) {
      parts.add('${it.pricePerUnit} $sym/ед.');
    }
    if (parts.isEmpty) return null;
    return Text(parts.join('  ·  '));
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
            title: Text(d.name),
            actions: [
              if (caps.export)
                IconButton(icon: const Icon(Icons.print), onPressed: _print),
              if (caps.manage)
                IconButton(
                    icon: const Icon(Icons.people), onPressed: _openAccess),
              if (caps.manage)
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
                              CheckboxListTile(
                                value: it.isPurchased,
                                onChanged: caps.toggle
                                    ? (v) => context.read<ShoppingBloc>().add(
                                        ShoppingToggleItemRequested(
                                            d.id, it.id, v ?? false))
                                    : null,
                                title: Text(it.name),
                                subtitle: _itemSubtitle(it, sym),
                                secondary: caps.manage
                                    ? IconButton(
                                        icon: const Icon(Icons.close, size: 18),
                                        onPressed: () => context
                                            .read<ShoppingBloc>()
                                            .add(ShoppingDeleteItemRequested(
                                                d.id, it.id)),
                                      )
                                    : null,
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
                    'Итого: ${d.totalPrice} $sym',
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
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
