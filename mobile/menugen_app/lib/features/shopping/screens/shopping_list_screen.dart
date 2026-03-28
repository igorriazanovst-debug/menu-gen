import 'package:flutter/material.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../family/models/family_models.dart';

class ShoppingListScreen extends StatefulWidget {
  final ApiClient apiClient;
  final int menuId;
  const ShoppingListScreen({super.key, required this.apiClient, required this.menuId});
  @override State<ShoppingListScreen> createState() => _ShoppingListScreenState();
}

class _ShoppingListScreenState extends State<ShoppingListScreen> {
  ShoppingListModel? _list;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final resp = await widget.apiClient.get('/menu/\${widget.menuId}/shopping-list/');
      setState(() {
        _list = ShoppingListModel.fromJson(resp.data as Map<String, dynamic>);
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = ApiException.fromDio(e).message; _loading = false; });
    }
  }

  Future<void> _toggle(ShoppingItemModel item) async {
    try {
      await widget.apiClient.patch(
        '/menu/\${widget.menuId}/shopping-list/items/\${item.id}/toggle/',
      );
      setState(() => item.isPurchased = !item.isPurchased);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Список покупок'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
          IconButton(
            icon: const Icon(Icons.share_outlined),
            onPressed: _list != null ? () => _share(context) : null,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  const SizedBox(height: 12), Text(_error!),
                  TextButton(onPressed: _load, child: const Text('Повторить')),
                ]))
              : _list == null || _list!.items.isEmpty
                  ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.shopping_cart_outlined, size: 80, color: Colors.grey.shade300),
                      const SizedBox(height: 16),
                      const Text('Список покупок пуст'),
                      const SizedBox(height: 8),
                      Text('Все продукты уже есть в холодильнике!',
                          style: TextStyle(color: Colors.grey.shade600)),
                    ]))
                  : _buildList(),
    );
  }

  Widget _buildList() {
    final items = _list!.items;
    // Группируем по категории
    final grouped = <String, List<ShoppingItemModel>>{};
    for (final item in items) {
      final cat = item.category?.isNotEmpty == true ? item.category! : 'Прочее';
      grouped.putIfAbsent(cat, () => []).add(item);
    }

    final purchased = items.where((i) => i.isPurchased).length;
    final total = items.length;

    return Column(
      children: [
        // Progress bar
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Куплено: $purchased / $total',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
              if (purchased == total && total > 0)
                const Chip(label: Text('Готово!', style: TextStyle(color: Colors.white)),
                    backgroundColor: AppColors.secondary),
            ]),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: total > 0 ? purchased / total : 0,
                minHeight: 8,
                backgroundColor: Colors.grey.shade200,
                valueColor: const AlwaysStoppedAnimation(AppColors.secondary),
              ),
            ),
          ]),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            children: grouped.entries.map((entry) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
                  child: Text(entry.key,
                      style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.secondary)),
                ),
                ...entry.value.map((item) => Card(
                  child: ListTile(
                    leading: Checkbox(
                      value: item.isPurchased,
                      activeColor: AppColors.secondary,
                      onChanged: (_) => _toggle(item),
                    ),
                    title: Text(
                      item.name,
                      style: item.isPurchased
                          ? const TextStyle(decoration: TextDecoration.lineThrough, color: Colors.grey)
                          : null,
                    ),
                    trailing: item.quantity != null
                        ? Text('\${item.quantity?.toStringAsFixed(item.quantity! % 1 == 0 ? 0 : 1)} \${item.unit ?? ''}',
                            style: const TextStyle(color: Colors.grey))
                        : null,
                  ),
                )),
              ],
            )).toList(),
          ),
        ),
      ],
    );
  }

  void _share(BuildContext context) {
    if (_list == null) return;
    final buf = StringBuffer('Список покупок:\n\n');
    for (final item in _list!.items.where((i) => !i.isPurchased)) {
      buf.writeln('• \${item.name} \${item.quantity?.toStringAsFixed(1) ?? ''} \${item.unit ?? ''}');
    }
    showDialog(context: context, builder: (_) => AlertDialog(
      title: const Text('Список покупок'),
      content: SelectableText(buf.toString()),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Закрыть')),
      ],
    ));
  }
}
