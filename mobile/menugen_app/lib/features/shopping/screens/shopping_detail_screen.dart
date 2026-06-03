import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:printing/printing.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../bloc/shopping_bloc.dart';
import '../models/shopping_models.dart';
import 'shopping_access_sheet.dart';

class ShoppingDetailScreen extends StatefulWidget {
  final int listId;
  const ShoppingDetailScreen({super.key, required this.listId});
  @override
  State<ShoppingDetailScreen> createState() => _ShoppingDetailScreenState();
}

class _ShoppingDetailScreenState extends State<ShoppingDetailScreen> {
  final _addCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    context.read<ShoppingBloc>().add(ShoppingDetailRequested(widget.listId));
  }

  @override
  void dispose() {
    _addCtrl.dispose();
    super.dispose();
  }

  Future<void> _print() async {
    final api = context.read<ShoppingBloc>().apiClient;
    final raw = await api.get('/shopping/lists/${widget.listId}/export/');
    final data = ShoppingExportData.fromJson(
        raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{});
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
                  final mark = it.isPurchased ? '[x]' : '[ ]';
                  return pw.Text('$mark ${it.name}$q');
                }),
              ]),
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
                      bloc.add(
                          ShoppingArchiveRequested(d.id, !d.isArchived));
                      Navigator.of(context).pop();
                    } else if (v == 'delete') {
                      bloc.add(ShoppingDeleteRequested(d.id));
                      Navigator.of(context).pop();
                    }
                  },
                  itemBuilder: (_) => [
                    PopupMenuItem(
                        value: 'archive',
                        child: Text(d.isArchived
                            ? 'Вернуть из архива'
                            : 'В архив')),
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
                    : ListView.builder(
                        itemCount: d.items.length,
                        itemBuilder: (_, i) {
                          final it = d.items[i];
                          return CheckboxListTile(
                            value: it.isPurchased,
                            onChanged: caps.toggle
                                ? (v) => context.read<ShoppingBloc>().add(
                                    ShoppingToggleItemRequested(
                                        d.id, it.id, v ?? false))
                                : null,
                            title: Text(it.name),
                            subtitle: (it.quantity != null || it.unit.isNotEmpty)
                                ? Text('${it.quantity ?? ''} ${it.unit}')
                                : null,
                            secondary: caps.manage
                                ? IconButton(
                                    icon: const Icon(Icons.close, size: 18),
                                    onPressed: () => context
                                        .read<ShoppingBloc>()
                                        .add(ShoppingDeleteItemRequested(
                                            d.id, it.id)),
                                  )
                                : null,
                          );
                        },
                      ),
              ),
              if (caps.manage)
                Padding(
                  padding: EdgeInsets.fromLTRB(
                      12, 4, 12, MediaQuery.of(context).viewInsets.bottom + 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _addCtrl,
                          decoration: const InputDecoration(
                              hintText: 'Добавить позицию…'),
                          onSubmitted: (_) => _submitAdd(d.id),
                        ),
                      ),
                      IconButton(
                          icon: const Icon(Icons.add),
                          onPressed: () => _submitAdd(d.id)),
                    ],
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  void _submitAdd(int listId) {
    final name = _addCtrl.text.trim();
    if (name.isEmpty) return;
    context.read<ShoppingBloc>().add(ShoppingAddItemRequested(listId, name));
    _addCtrl.clear();
  }
}
