import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';

/// Горизонтальный календарь дат меню. Tap по дате — onSelected(date).
class MenuDayStrip extends StatelessWidget {
  final List<DateTime> days;
  final DateTime selected;
  final ValueChanged<DateTime> onSelected;

  const MenuDayStrip({
    super.key,
    required this.days,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 76,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: days.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final d = days[i];
          final active = d.year == selected.year &&
              d.month == selected.month &&
              d.day == selected.day;
          final today = DateTime.now();
          final isToday = d.year == today.year &&
              d.month == today.month &&
              d.day == today.day;
          return _DayChip(
            date: d,
            active: active,
            isToday: isToday,
            onTap: () => onSelected(d),
          );
        },
      ),
    );
  }
}

class _DayChip extends StatelessWidget {
  final DateTime date;
  final bool active;
  final bool isToday;
  final VoidCallback onTap;

  const _DayChip({
    required this.date,
    required this.active,
    required this.isToday,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dow = DateFormat('E', 'ru').format(date).toUpperCase();
    final day = DateFormat('d', 'ru').format(date);
    final bg = active ? AppColors.primary : AppColors.surface;
    final fg = active ? Colors.white : AppColors.textPrimary;
    final borderColor = active
        ? AppColors.primary
        : (isToday ? AppColors.primary : Colors.grey.shade300);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        width: 56,
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: borderColor, width: isToday && !active ? 1.5 : 1),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              dow,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: active ? Colors.white.withOpacity(0.85) : Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              day,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: fg,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
