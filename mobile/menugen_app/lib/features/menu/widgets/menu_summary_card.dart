import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';
import 'menu_meal_carousel.dart' show MealNutritionTotals;

// MG_SKIN: карточка-итог дня в стиле Main-референса (meal_calendar):
// донат-диаграмма распределения калорий по макросам + сводка КБЖУ.
class MenuSummaryCard extends StatelessWidget {
  final MealNutritionTotals totals;
  final DateTime start;
  final DateTime end;
  // MG_SKIN: переопределение подписи периода (для режима «выбранный день»).
  final String? periodLabel;

  const MenuSummaryCard({
    super.key,
    required this.totals,
    required this.start,
    required this.end,
    this.periodLabel,
  });

  // Углеводы — фиксированный «семантический» синий (не брендовый);
  // жиры/белки берём из активного скина.
  static const _carbColor = Color(0xFF5B9BD5);

  String _fmt(double v) =>
      v == v.roundToDouble() ? v.round().toString() : v.toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    final fatColor = tokens.accent;
    final proColor = cs.primary;
    final fmt = DateFormat('d MMM', 'ru');
    final period = periodLabel ?? '${fmt.format(start)} – ${fmt.format(end)}';

    final carbCal = totals.carbs * 4;
    final fatCal = totals.fats * 9;
    final proCal = totals.proteins * 4;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          SizedBox(
            width: 64,
            height: 64,
            child: CustomPaint(
              painter: _MacroDonutPainter(
                carbCal: carbCal,
                fatCal: fatCal,
                proCal: proCal,
                carbColor: _carbColor,
                fatColor: fatColor,
                proColor: proColor,
                emptyColor: tokens.surfaceAlt,
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  period,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: tokens.textSecondary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${_fmt(totals.calories)} ккал',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: cs.onSurface,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 12,
                  runSpacing: 4,
                  children: [
                    _MacroLegend(
                      color: _carbColor,
                      label: 'У',
                      value: '${_fmt(totals.carbs)} г',
                    ),
                    _MacroLegend(
                      color: fatColor,
                      label: 'Ж',
                      value: '${_fmt(totals.fats)} г',
                    ),
                    _MacroLegend(
                      color: proColor,
                      label: 'Б',
                      value: '${_fmt(totals.proteins)} г',
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MacroLegend extends StatelessWidget {
  final Color color;
  final String label;
  final String value;

  const _MacroLegend({
    required this.color,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 5),
        Text(
          '$value $label',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: context.tokens.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _MacroDonutPainter extends CustomPainter {
  final double carbCal;
  final double fatCal;
  final double proCal;
  final Color carbColor;
  final Color fatColor;
  final Color proColor;
  final Color emptyColor;

  _MacroDonutPainter({
    required this.carbCal,
    required this.fatCal,
    required this.proCal,
    required this.carbColor,
    required this.fatColor,
    required this.proColor,
    required this.emptyColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 9.0;
    final rect = Offset.zero & size;
    final center = rect.center;
    final radius = (math.min(size.width, size.height) - stroke) / 2;
    final arcRect = Rect.fromCircle(center: center, radius: radius);

    final total = carbCal + fatCal + proCal;

    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..color = emptyColor;

    if (total <= 0) {
      canvas.drawCircle(center, radius, base);
      return;
    }

    const startAngle = -math.pi / 2;
    const gap = 0.06; // небольшой зазор между сегментами
    final segments = <MapEntry<Color, double>>[
      MapEntry(carbColor, carbCal / total),
      MapEntry(fatColor, fatCal / total),
      MapEntry(proColor, proCal / total),
    ];

    double angle = startAngle;
    for (final seg in segments) {
      final sweep = seg.value * (2 * math.pi);
      if (sweep <= 0) continue;
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.round
        ..color = seg.key;
      final adjust = math.min(gap, sweep / 2);
      canvas.drawArc(arcRect, angle + adjust, sweep - adjust * 2, false, paint);
      angle += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _MacroDonutPainter old) =>
      old.carbCal != carbCal || old.fatCal != fatCal || old.proCal != proCal;
}
