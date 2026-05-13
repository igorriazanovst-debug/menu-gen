import 'package:flutter/material.dart';

import '../models/diary_stats.dart';

/// Compact card showing planned vs actual KБЖУ for the selected day.
class DiaryStatsCard extends StatelessWidget {
  final DiaryDayStats stats;
  const DiaryStatsCard({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('КБЖУ за день',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 8),
            Row(children: [
              _bucketColumn(label: 'План', bucket: stats.planned, color: Colors.blue.shade600),
              const SizedBox(width: 16),
              _bucketColumn(label: 'Факт', bucket: stats.actual, color: Colors.green.shade700),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _bucketColumn({
    required String label,
    required NutritionBucket bucket,
    required Color color,
  }) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          _row('ккал', bucket.calories),
          _row('Б',   bucket.proteins),
          _row('Ж',   bucket.fats),
          _row('У',   bucket.carbs),
        ],
      ),
    );
  }

  Widget _row(String k, double v) {
    final s = v == 0 ? '0' : v.toStringAsFixed(v >= 10 ? 0 : 1);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(children: [
        SizedBox(width: 36, child: Text(k, style: const TextStyle(fontSize: 12, color: Colors.grey))),
        Text(s, style: const TextStyle(fontSize: 13)),
      ]),
    );
  }
}
