import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../core/models/menu.dart';
import '../../../core/theme/app_theme.dart';

const _mealLabels = {
  'breakfast': 'Завтрак',
  'lunch':     'Обед',
  'dinner':    'Ужин',
  'snack':     'Перекус',
};

const _mealIcons = {
  'breakfast': Icons.wb_sunny_outlined,
  'lunch':     Icons.wb_cloudy_outlined,
  'dinner':    Icons.nights_stay_outlined,
  'snack':     Icons.apple,
};

class MenuDayCard extends StatelessWidget {
  final DateTime date;
  final List<MenuItem> items;
  final int menuId;

  const MenuDayCard({super.key, required this.date, required this.items, required this.menuId});

  @override
  Widget build(BuildContext context) {
    final dayLabel = DateFormat('EEEE, d MMMM', 'ru').format(date);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(dayLabel, style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
            const SizedBox(height: 12),
            ...['breakfast', 'lunch', 'dinner', 'snack'].map((meal) {
              final item = items.where((i) => i.mealType == meal).firstOrNull;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(children: [
                  Icon(_mealIcons[meal], size: 20, color: AppColors.secondary),
                  const SizedBox(width: 8),
                  SizedBox(width: 70,
                    child: Text(_mealLabels[meal] ?? meal,
                        style: const TextStyle(fontSize: 12, color: Colors.grey))),
                  Expanded(child: item == null
                      ? const Text('—', style: TextStyle(color: Colors.grey))
                      : Text(item.recipe.title,
                          style: const TextStyle(fontWeight: FontWeight.w500),
                          maxLines: 1, overflow: TextOverflow.ellipsis)),
                ]),
              );
            }),
          ],
        ),
      ),
    );
  }
}
