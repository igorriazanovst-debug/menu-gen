import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/api/api_client.dart';

/// Result of a single recognized product, mirrors backend RecognizedProductSerializer.
class RecognizedProduct {
  final String name;
  final String category; // slug or ''
  final String? quantity;
  final double confidence;
  final int? categoryId;
  final String? categorySlug;
  final String? categoryName;
  final String? categoryIcon;
  final String? categoryColor;

  const RecognizedProduct({
    required this.name,
    required this.category,
    required this.quantity,
    required this.confidence,
    this.categoryId,
    this.categorySlug,
    this.categoryName,
    this.categoryIcon,
    this.categoryColor,
  });

  factory RecognizedProduct.fromJson(Map<String, dynamic> m) => RecognizedProduct(
        name: (m['name'] ?? '').toString(),
        category: (m['category'] ?? '').toString(),
        quantity: m['quantity'] as String?,
        confidence: (m['confidence'] is num) ? (m['confidence'] as num).toDouble() : 0.0,
        categoryId: m['category_id'] as int?,
        categorySlug: m['category_slug'] as String?,
        categoryName: m['category_name'] as String?,
        categoryIcon: m['category_icon'] as String?,
        categoryColor: m['category_color'] as String?,
      );
}

/// Ask the user: one product or several on the photo?
/// Returns 'single' | 'multi' | null (cancelled).
Future<String?> askRecognizeMode(BuildContext context) {
  return showModalBottomSheet<String>(
    context: context,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text('Что на фото?',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          ),
          ListTile(
            leading: const Icon(Icons.crop_free),
            title: const Text('Один продукт'),
            subtitle: const Text('Снимок одной упаковки'),
            onTap: () => Navigator.of(ctx).pop('single'),
          ),
          ListTile(
            leading: const Icon(Icons.grid_view),
            title: const Text('Несколько продуктов'),
            subtitle: const Text('Например, полка холодильника'),
            onTap: () => Navigator.of(ctx).pop('multi'),
          ),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );
}

/// Pick image source (camera/gallery). Returns XFile or null.
Future<XFile?> pickPhoto(BuildContext context) async {
  final source = await showModalBottomSheet<ImageSource>(
    context: context,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.photo_camera),
            title: const Text('Сделать фото'),
            onTap: () => Navigator.of(ctx).pop(ImageSource.camera),
          ),
          ListTile(
            leading: const Icon(Icons.photo_library),
            title: const Text('Выбрать из галереи'),
            onTap: () => Navigator.of(ctx).pop(ImageSource.gallery),
          ),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );
  if (source == null) return null;
  final picker = ImagePicker();
  return picker.pickImage(
    source: source,
    maxWidth: 1600,
    imageQuality: 85,
  );
}

/// Calls POST /fridge/recognize-photo/ with base64 (no API client change needed).
/// Returns the list of recognized products (1 for single, 0..N for multi).
Future<List<RecognizedProduct>> recognizePhoto({
  required ApiClient apiClient,
  required XFile file,
  required String mode,
}) async {
  final bytes = await file.readAsBytes();
  final b64 = base64Encode(bytes);
  final mime = _mimeFromName(file.name);
  final dataUrl = 'data:$mime;base64,$b64';

  final r = await apiClient.post(
    '/fridge/recognize-photo/',
    data: {'image_b64': dataUrl, 'mode': mode},
  );
  final m = (r is Map) ? Map<String, dynamic>.from(r) : <String, dynamic>{};

  if (mode == 'multi') {
    final list = (m['products'] as List?) ?? const [];
    return list
        .whereType<Map>()
        .map((e) => RecognizedProduct.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }
  final p = m['product'];
  if (p is Map) {
    return [RecognizedProduct.fromJson(Map<String, dynamic>.from(p))];
  }
  return const [];
}

String _mimeFromName(String name) {
  final n = name.toLowerCase();
  if (n.endsWith('.png')) return 'image/png';
  return 'image/jpeg';
}

/// Multi-select screen: shows recognized products with checkboxes.
/// Returns the chosen subset (or null if cancelled).
class RecognizedProductsPicker extends StatefulWidget {
  final List<RecognizedProduct> products;
  const RecognizedProductsPicker({super.key, required this.products});

  @override
  State<RecognizedProductsPicker> createState() => _RecognizedProductsPickerState();
}

class _RecognizedProductsPickerState extends State<RecognizedProductsPicker> {
  late final List<bool> _checked =
      List<bool>.filled(widget.products.length, true, growable: false);

  @override
  Widget build(BuildContext context) {
    final products = widget.products;
    return Scaffold(
      appBar: AppBar(title: const Text('Распознанные продукты')),
      body: products.isEmpty
          ? const Center(child: Text('Ничего не распознано. Попробуйте другое фото.'))
          : ListView.builder(
              itemCount: products.length,
              itemBuilder: (_, i) {
                final p = products[i];
                final pct = (p.confidence * 100).round();
                return CheckboxListTile(
                  value: _checked[i],
                  onChanged: (v) => setState(() => _checked[i] = v ?? false),
                  title: Text(p.name),
                  subtitle: Text([
                    if (p.categoryName != null && p.categoryName!.isNotEmpty)
                      '${p.categoryIcon ?? ''} ${p.categoryName}'.trim(),
                    if (p.quantity != null && p.quantity!.isNotEmpty) p.quantity!,
                    'точность $pct%',
                  ].where((s) => s.isNotEmpty).join('  ·  ')),
                );
              },
            ),
      bottomNavigationBar: products.isEmpty
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: ElevatedButton(
                  onPressed: () {
                    final chosen = <RecognizedProduct>[];
                    for (var i = 0; i < products.length; i++) {
                      if (_checked[i]) chosen.add(products[i]);
                    }
                    Navigator.of(context).pop(chosen);
                  },
                  child: const Text('Добавить выбранные'),
                ),
              ),
            ),
    );
  }
}
