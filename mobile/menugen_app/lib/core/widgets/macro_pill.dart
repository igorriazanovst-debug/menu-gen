// MG_204m_V_macro_pill = 1
import 'package:flutter/material.dart';

/// Компактная пилюля для отображения целевого значения КБЖУ (read-only).
/// Используется в ProfileScreen и FamilyScreen (редактирование участника).
class MacroPill extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  final Color background;
  final Color foreground;

  const MacroPill({
    super.key,
    required this.label,
    required this.value,
    required this.unit,
    required this.background,
    required this.foreground,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label.toUpperCase(),
            style: TextStyle(
              fontSize: 10,
              letterSpacing: 0.5,
              color: foreground.withOpacity(0.7),
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: foreground,
            ),
          ),
          Text(
            unit,
            style: TextStyle(
              fontSize: 9,
              color: foreground.withOpacity(0.6),
            ),
          ),
        ],
      ),
    );
  }
}

/// Парсит число (int/double/строка) в строку без дробной части либо '—'.
String formatTargetNumber(dynamic v) {
  if (v == null) return '—';
  if (v is num) return v.toStringAsFixed(0);
  final s = v.toString().trim();
  if (s.isEmpty) return '—';
  final parsed = num.tryParse(s);
  if (parsed == null) return '—';
  return parsed.toStringAsFixed(0);
}

/// Извлекает targets из profile-мапы. Сначала прямые поля, fallback — targets_calculated.
Map<String, dynamic>? extractTargets(Map<String, dynamic>? profile) {
  if (profile == null) return null;
  final hasDirect = profile['calorie_target'] != null && profile['protein_target_g'] != null;
  if (hasDirect) {
    return {
      'calorie_target':   profile['calorie_target'],
      'protein_target_g': profile['protein_target_g'],
      'fat_target_g':     profile['fat_target_g'],
      'carb_target_g':    profile['carb_target_g'],
      'fiber_target_g':   profile['fiber_target_g'],
    };
  }
  final calc = profile['targets_calculated'];
  if (calc is Map<String, dynamic>) return calc;
  if (calc is Map) return Map<String, dynamic>.from(calc);
  return null;
}

/// Готовый ряд из 5 пилюль КБЖУ.
class MacroPillsRow extends StatelessWidget {
  final Map<String, dynamic> targets;
  const MacroPillsRow({super.key, required this.targets});

  @override
  Widget build(BuildContext context) {
    final pills = <Widget>[
      Expanded(child: MacroPill(
        label: 'Ккал',
        value: formatTargetNumber(targets['calorie_target']),
        unit: 'ккал',
        background: const Color(0xFFFEEAEA),
        foreground: const Color(0xFFE34A4A),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Белок',
        value: formatTargetNumber(targets['protein_target_g']),
        unit: 'г',
        background: const Color(0xFFE6F0FB),
        foreground: const Color(0xFF1E5BB6),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Жиры',
        value: formatTargetNumber(targets['fat_target_g']),
        unit: 'г',
        background: const Color(0xFFFEF3D6),
        foreground: const Color(0xFFB8770A),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Углев',
        value: formatTargetNumber(targets['carb_target_g']),
        unit: 'г',
        background: const Color(0xFFE0F5EB),
        foreground: const Color(0xFF1F8B5C),
      )),
      const SizedBox(width: 6),
      Expanded(child: MacroPill(
        label: 'Клетч',
        value: formatTargetNumber(targets['fiber_target_g']),
        unit: 'г',
        background: const Color(0xFFEFE5F8),
        foreground: const Color(0xFF6B3FA0),
      )),
    ];
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: pills);
  }
}
