// MG_ALLERGEN14_V_mobile = 1
// Редактор аллергенов профиля: фиксированный список 14 (ТР ТС 022/2011)
// чекбоксами по группам + возможность добавить свой (внесписочный) аллерген.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/constants/allergens.dart';

class AllergenEditor extends StatefulWidget {
  // apiClient оставлен в сигнатуре для совместимости с вызовом в профиле,
  // но список аллергенов теперь фиксированный (не требует запроса).
  final ApiClient apiClient;
  final List<String> value;

  /// Вызывается с новым списком; родитель сохраняет на бэкенд.
  final Future<void> Function(List<String>) onChanged;

  const AllergenEditor({
    super.key,
    required this.apiClient,
    required this.value,
    required this.onChanged,
  });

  @override
  State<AllergenEditor> createState() => _AllergenEditorState();
}

class _AllergenEditorState extends State<AllergenEditor> {
  final TextEditingController _custom = TextEditingController();

  @override
  void dispose() {
    _custom.dispose();
    super.dispose();
  }

  bool _has(String v) => widget.value.contains(v);

  Future<void> _toggle(String key) async {
    final next = _has(key)
        ? widget.value.where((v) => v != key).toList()
        : [...widget.value, key];
    await widget.onChanged(next);
  }

  Future<void> _addCustom() async {
    final t = _custom.text.trim();
    if (t.isEmpty) return;
    final exists = widget.value.any((v) => v.toLowerCase() == t.toLowerCase());
    final isStd = kAllergens.any((a) => a.label.toLowerCase() == t.toLowerCase());
    _custom.clear();
    if (!exists && !isStd) {
      await widget.onChanged([...widget.value, t]);
    } else {
      setState(() {});
    }
  }

  Future<void> _removeCustom(String v) async {
    await widget.onChanged(widget.value.where((x) => x != v).toList());
  }

  @override
  Widget build(BuildContext context) {
    // Группируем 14 по group (сохраняя порядок появления групп).
    final groups = <String, List<AllergenDef>>{};
    final order = <String>[];
    for (final a in kAllergens) {
      if (!groups.containsKey(a.group)) {
        groups[a.group] = <AllergenDef>[];
        order.add(a.group);
      }
      groups[a.group]!.add(a);
    }

    // Кастомные (внесписочные) значения.
    final customValues =
        widget.value.where((v) => !kAllergenKeys.contains(v)).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final g in order) ...[
          Padding(
            padding: const EdgeInsets.only(top: 4, bottom: 2),
            child: Text(g,
                style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey)),
          ),
          for (final a in groups[g]!)
            CheckboxListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: _has(a.key),
              title: Text(a.label),
              subtitle: Text(a.full,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 11, color: Colors.grey)),
              onChanged: (_) => _toggle(a.key),
            ),
        ],

        const Divider(height: 24),

        // Кастомные (внесписочные) аллергены.
        const Text('Свой аллерген (вне списка)',
            style: TextStyle(
                fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey)),
        const SizedBox(height: 8),
        if (customValues.isNotEmpty)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: customValues
                .map((v) => Chip(
                      label: Text(v),
                      onDeleted: () => _removeCustom(v),
                      deleteIcon: const Icon(Icons.close, size: 16),
                    ))
                .toList(),
          ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _custom,
                decoration: const InputDecoration(
                  isDense: true,
                  border: OutlineInputBorder(),
                  hintText: 'Напр. кориандр',
                ),
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _addCustom(),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: _addCustom,
              child: const Text('Добавить'),
            ),
          ],
        ),
        const Padding(
          padding: EdgeInsets.only(top: 6),
          child: Text(
            'Внесписочные аллергены исключаются по совпадению в названиях ингредиентов.',
            style: TextStyle(fontSize: 11, color: Colors.grey),
          ),
        ),
      ],
    );
  }
}
