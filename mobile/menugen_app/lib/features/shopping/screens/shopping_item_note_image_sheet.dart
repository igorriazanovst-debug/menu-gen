// MG_SHOPNOTE / MG_SHOPIMG — bottom-sheet: комментарий + изображение товара.
// Изображение: камера/галерея (image_picker, сжатие 1600px/q85 → base64) или
// ссылка (URL). Сохраняется одним PATCH (note / image_url / image_b64).
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../fridge/screens/recognize_photo_flow.dart' show pickPhoto;
import '../models/shopping_models.dart';

String _mimeFromName(String name) {
  final n = name.toLowerCase();
  if (n.endsWith('.png')) return 'image/png';
  if (n.endsWith('.webp')) return 'image/webp';
  if (n.endsWith('.gif')) return 'image/gif';
  return 'image/jpeg';
}

/// Возвращает true, если что-то сохранили (родитель перезагрузит список).
Future<bool> showItemNoteImageSheet({
  required BuildContext context,
  required ApiClient api,
  required int listId,
  required ShoppingItem item,
}) async {
  final res = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
      child: _ItemNoteImageForm(api: api, listId: listId, item: item),
    ),
  );
  return res ?? false;
}

enum _ImgMode { keep, file, url, clear }

class _ItemNoteImageForm extends StatefulWidget {
  final ApiClient api;
  final int listId;
  final ShoppingItem item;
  const _ItemNoteImageForm({required this.api, required this.listId, required this.item});

  @override
  State<_ItemNoteImageForm> createState() => _ItemNoteImageFormState();
}

class _ItemNoteImageFormState extends State<_ItemNoteImageForm> {
  late final TextEditingController _note;
  late final TextEditingController _url;
  _ImgMode _mode = _ImgMode.keep;
  Uint8List? _pickedBytes; // превью выбранного файла
  String _pickedMime = 'image/jpeg';
  String? _previewUrl; // превью сетевого изображения
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _note = TextEditingController(text: widget.item.note);
    _url = TextEditingController(text: widget.item.imageUrl ?? '');
    _previewUrl = widget.item.image;
  }

  @override
  void dispose() {
    _note.dispose();
    _url.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    try {
      final file = await pickPhoto(context);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      setState(() {
        _pickedBytes = bytes;
        _pickedMime = _mimeFromName(file.name);
        _previewUrl = null;
        _mode = _ImgMode.file;
        _error = null;
      });
    } catch (_) {
      setState(() => _error = 'Не удалось получить изображение.');
    }
  }

  void _applyUrl() {
    final u = _url.text.trim();
    if (u.isEmpty) return;
    setState(() {
      _pickedBytes = null;
      _previewUrl = u;
      _mode = _ImgMode.url;
    });
  }

  void _remove() {
    setState(() {
      _pickedBytes = null;
      _previewUrl = null;
      _url.clear();
      _mode = _ImgMode.clear;
    });
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    final payload = <String, dynamic>{'note': _note.text};
    if (_mode == _ImgMode.file && _pickedBytes != null) {
      payload['image_b64'] = 'data:$_pickedMime;base64,${base64Encode(_pickedBytes!)}';
    } else if (_mode == _ImgMode.url) {
      payload['image_url'] = _url.text.trim();
      payload['image_b64'] = ''; // сбросить возможный загруженный файл
    } else if (_mode == _ImgMode.clear) {
      payload['image_url'] = '';
      payload['image_b64'] = '';
    }
    try {
      await widget.api.patch(
        '/shopping/lists/${widget.listId}/items/${widget.item.id}/',
        data: payload,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _saving = false;
      });
    }
  }

  Widget _preview() {
    if (_pickedBytes != null) {
      return Image.memory(_pickedBytes!, height: 160, fit: BoxFit.contain);
    }
    if (_previewUrl != null && _previewUrl!.isNotEmpty) {
      return Image.network(
        _previewUrl!,
        height: 160,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => const Text('Не удалось загрузить изображение',
            style: TextStyle(fontSize: 12, color: Colors.grey)),
      );
    }
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 8),
      child: Text('Изображение не задано.', style: TextStyle(fontSize: 13, color: Colors.grey)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(widget.item.name,
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(false),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _note,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Комментарий',
                  hintText: 'Напр. взять посвежее, конкретный бренд…',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
              const SizedBox(height: 16),
              const Text('Изображение', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Center(child: _preview()),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: _pick,
                    icon: const Icon(Icons.photo_camera, size: 18),
                    label: const Text('Камера / галерея'),
                  ),
                  if (_pickedBytes != null || (_previewUrl != null && _previewUrl!.isNotEmpty))
                    OutlinedButton.icon(
                      onPressed: _remove,
                      icon: const Icon(Icons.delete_outline, size: 18),
                      label: const Text('Убрать'),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _url,
                      decoration: const InputDecoration(
                        labelText: 'Ссылка на изображение',
                        hintText: 'https://…',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(onPressed: _applyUrl, child: const Text('OK')),
                ],
              ),
              if (_error != null) ...[
                const SizedBox(height: 10),
                Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 12)),
              ],
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving ? null : () => Navigator.of(context).pop(false),
                    child: const Text('Отмена'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: _saving ? null : _save,
                    child: _saving
                        ? const SizedBox(
                            width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Сохранить'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
