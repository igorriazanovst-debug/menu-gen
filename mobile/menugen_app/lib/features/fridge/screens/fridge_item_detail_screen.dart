import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import 'edit_fridge_item_sheet.dart'; // MG_B03

class FridgeItemDetailScreen extends StatefulWidget {
  final ApiClient apiClient;
  final int itemId;
  const FridgeItemDetailScreen({super.key, required this.apiClient, required this.itemId});

  @override
  State<FridgeItemDetailScreen> createState() => _FridgeItemDetailScreenState();
}

class _FridgeItemDetailScreenState extends State<FridgeItemDetailScreen> {
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final r = await widget.apiClient.get('/fridge/${widget.itemId}/details/');
      setState(() {
        _data = (r is Map) ? Map<String, dynamic>.from(r) : null;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Карточка продукта'),
        actions: [
          // MG_B03: edit this item.
          if (!_loading && _error == null && _data != null)
            IconButton(
              tooltip: 'Редактировать',
              icon: const Icon(Icons.edit),
              onPressed: _openEdit,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final data = _data ?? {};
    final item = (data['item'] as Map?)?.cast<String, dynamic>() ?? {};
    final product = (data['product'] as Map?)?.cast<String, dynamic>();
    final daysLeft = data['days_left'] as int?;
    final usage = (data['usage_30d'] as Map?)?.cast<String, dynamic>() ?? {};

    final name = (item['name'] as String?) ?? '';
    final qty = item['quantity'];
    final unit = (item['unit'] as String?) ?? '';
    final expiry = item['expiry_date'] as String?;
    final imageUrl = (item['product_image_url'] as String?)
        ?? (product?['image_url'] as String?);

    // nutrition: product.nutrition + calories_per_100g
    final nutrition = (product?['nutrition'] as Map?)?.cast<String, dynamic>() ?? {};
    final kcal = product?['calories_per_100g'];

    final usageCount = (usage['count'] as int?) ?? 0;
    final recipes = (usage['recipes'] as List?) ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Header: image + name
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (imageUrl != null && imageUrl.isNotEmpty)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: CachedNetworkImage(
                  imageUrl: imageUrl,
                  width: 96, height: 96, fit: BoxFit.cover,
                  errorWidget: (_, __, ___) => Container(
                    width: 96, height: 96,
                    color: Colors.grey.shade100,
                    child: const Icon(Icons.image_not_supported_outlined, size: 40),
                  ),
                ),
              )
            else
              Container(
                width: 96, height: 96,
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.inventory_2_outlined, size: 40),
              ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  if (product?['category'] != null && (product!['category'] as String).isNotEmpty)
                    Text(product['category'] as String,
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                ],
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // Stock + expiry
        Row(
          children: [
            Expanded(
              child: _statCard(
                icon: Icons.scale,
                label: 'Остаток',
                value: '${qty ?? '—'} $unit',
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _statCard(
                icon: Icons.event,
                label: 'Срок годности',
                value: daysLeft == null
                    ? '—'
                    : daysLeft < 0
                        ? 'Просрочено\n${-daysLeft} дн.'
                        : '$daysLeft дн.',
                color: daysLeft == null
                    ? null
                    : daysLeft < 0
                        ? Colors.red
                        : daysLeft < 3
                            ? Colors.orange
                            : null,
              ),
            ),
          ],
        ),

        if (expiry != null) Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text('Годен до $expiry',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
              textAlign: TextAlign.center),
        ),

        const SizedBox(height: 24),

        // KBJU
        const Text('Пищевая ценность (на 100 г)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        if (product == null)
          const Text('— нет данных',
              style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic))
        else
          Wrap(
            spacing: 8, runSpacing: 8,
            children: [
              _kbjuChip('Ккал', kcal),
              _kbjuChip('Белки', nutrition['proteins']),
              _kbjuChip('Жиры', nutrition['fats']),
              _kbjuChip('Углеводы', nutrition['carbs']),
              if (nutrition['fiber'] != null) _kbjuChip('Клетч.', nutrition['fiber']),
            ],
          ),

        const SizedBox(height: 24),

        // Usage in menu
        Row(
          children: [
            const Text('Использование в меню',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: usageCount > 0 ? Colors.green.shade50 : Colors.grey.shade100,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text('за 30 дн: $usageCount',
                  style: TextStyle(
                    fontSize: 12,
                    color: usageCount > 0 ? Colors.green.shade800 : Colors.grey.shade700,
                  )),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (recipes.isEmpty)
          const Text('Этот продукт не появлялся в меню за последние 30 дней.',
              style: TextStyle(color: Colors.grey, fontSize: 13))
        else
          Column(
            children: recipes.map((r) {
              final m = (r as Map).cast<String, dynamic>();
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.restaurant_menu),
                title: Text(m['title'] as String? ?? ''),
                trailing: Text('×${m['times']}',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
                onTap: () {
                  final id = m['recipe_id'];
                  if (id != null) context.go('/recipes/$id');
                },
              );
            }).toList(),
          ),
      ],
    );
  }

  Widget _statCard({
    required IconData icon,
    required String label,
    required String value,
    Color? color,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, color: color ?? Colors.grey.shade600),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: color)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _kbjuChip(String label, dynamic value) {
    final txt = value == null
        ? '—'
        : value is num
            ? value.toStringAsFixed(value % 1 == 0 ? 0 : 1)
            : value.toString();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text('$label: $txt', style: const TextStyle(fontSize: 13)),
    );
  }
}
