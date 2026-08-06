import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/diary_stats.dart';

/// DIARY_CHART: сводка КБЖУ за день — круговая диаграмма «факт/план» по калориям
/// + компактные прогресс-бары Б/Ж/У (факт к плану).
class DiaryStatsCard extends StatelessWidget {
  final DiaryDayStats stats;
  const DiaryStatsCard({super.key, required this.stats});

  static String _n(double v) => v == 0 ? '0' : v.toStringAsFixed(v >= 10 ? 0 : 1);

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final factCal = stats.actual.calories;
    final planCal = stats.planned.calories;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 2),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            _CalorieDonut(fact: factCal, plan: planCal, color: cs.primary),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _macroBar('Белки', stats.actual.proteins, stats.planned.proteins,
                      const Color(0xFF42A5F5)),
                  const SizedBox(height: 6),
                  _macroBar('Жиры', stats.actual.fats, stats.planned.fats,
                      const Color(0xFFFFB74D)),
                  const SizedBox(height: 6),
                  _macroBar('Углеводы', stats.actual.carbs, stats.planned.carbs,
                      const Color(0xFF66BB6A)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _macroBar(String label, double fact, double plan, Color color) {
    final ratio = plan > 0 ? (fact / plan).clamp(0.0, 1.0) : (fact > 0 ? 1.0 : 0.0);
    return Row(
      children: [
        SizedBox(
          width: 64,
          // MG_NOOVERFLOW: подпись обрезается по ширине колонки.
          child: Text(label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11)),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 6,
              color: color,
              backgroundColor: color.withOpacity(0.15),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Text('${_n(fact)} / ${_n(plan)} г',
            style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
      ],
    );
  }
}

/// DIARY_CHART: кольцо «факт/план» по калориям с подписью в центре.
class _CalorieDonut extends StatelessWidget {
  final double fact;
  final double plan;
  final Color color;
  const _CalorieDonut({required this.fact, required this.plan, required this.color});

  @override
  Widget build(BuildContext context) {
    final ratio = plan > 0 ? (fact / plan).clamp(0.0, 1.0) : (fact > 0 ? 1.0 : 0.0);
    final pct = plan > 0 ? (fact / plan * 100).round() : null;
    return SizedBox(
      width: 78,
      height: 78,
      child: CustomPaint(
        painter: _DonutPainter(ratio: ratio, color: color, track: color.withOpacity(0.15)),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(fact == 0 ? '0' : fact.toStringAsFixed(0),
                  style: TextStyle(
                      fontWeight: FontWeight.w700, fontSize: 15, color: color)),
              Container(
                margin: const EdgeInsets.symmetric(vertical: 1),
                width: 26,
                height: 1,
                color: Colors.grey.shade300,
              ),
              Text(plan == 0 ? '— ккал' : '${plan.toStringAsFixed(0)} ккал',
                  style: TextStyle(fontSize: 9, color: Colors.grey.shade600)),
              if (pct != null)
                Text('$pct%',
                    style: TextStyle(fontSize: 9, color: Colors.grey.shade500)),
            ],
          ),
        ),
      ),
    );
  }
}

class _DonutPainter extends CustomPainter {
  final double ratio;
  final Color color;
  final Color track;
  _DonutPainter({required this.ratio, required this.color, required this.track});

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 8.0;
    final rect = Offset(stroke / 2, stroke / 2) &
        Size(size.width - stroke, size.height - stroke);
    final bg = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..color = track;
    canvas.drawArc(rect, 0, 2 * math.pi, false, bg);
    final fg = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi * ratio.clamp(0.0, 1.0), false, fg);
  }

  @override
  bool shouldRepaint(_DonutPainter old) =>
      old.ratio != ratio || old.color != color || old.track != track;
}
