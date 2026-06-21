import 'package:flutter/material.dart';

import '../models/diary_stats.dart';

/// MG_SKIN: компактная сводка КБЖУ за день — две строки (План/Факт),
/// втрое ниже прежней версии.
class DiaryStatsCard extends StatelessWidget {
  final DiaryDayStats stats;
  const DiaryStatsCard({super.key, required this.stats});

  static String _n(double v) =>
      v == 0 ? '0' : v.toStringAsFixed(v >= 10 ? 0 : 1);

  static String _fmt(NutritionBucket b) =>
      '${_n(b.calories)} ккал · ${_n(b.proteins)}Б · ${_n(b.fats)}Ж · ${_n(b.carbs)}У';

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 2),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _line('План', stats.planned, Colors.blue.shade600),
            const SizedBox(height: 3),
            _line('Факт', stats.actual, Colors.green.shade700),
          ],
        ),
      ),
    );
  }

  Widget _line(String label, NutritionBucket b, Color color) {
    return Row(
      children: [
        SizedBox(
          width: 40,
          child: Text(label,
              style: TextStyle(
                  color: color, fontWeight: FontWeight.w700, fontSize: 12)),
        ),
        Expanded(
          child: Text(
            _fmt(b),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }
}
