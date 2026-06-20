import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';

/// MG_SKIN: матрица меню «приёмы × дни» (редизайн меню, mobile).
/// Слева — липкая колонка приёмов, справа — горизонтально-скроллящиеся
/// колонки-дни. Ячейка = крупное фото блюда + бейдж «+N» при нескольких
/// блюдах в приёме. Тап по ячейке отдаёт наружу выбранный день+приём.
typedef CellItemsResolver = List<Map<String, dynamic>> Function(
    int dayOffset, String slot);

String? _heroImage(List<Map<String, dynamic>> items) {
  for (final it in items) {
    final r = it['recipe'];
    if (r is Map) {
      final u = r['image_url'];
      if (u is String && u.isNotEmpty) return u;
    }
  }
  return null;
}

String _cap(String s) => s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';

class MenuMatrix extends StatelessWidget {
  final List<DateTime> days;
  final DateTime start;
  final List<String> mealSlots;
  final Map<String, String> labels;
  final Map<String, IconData> icons;
  final DateTime selected;
  final CellItemsResolver cellItems;
  final ValueChanged<DateTime> onDaySelected;
  final void Function(DateTime date, String slot, List<Map<String, dynamic>> items)
      onCellTap;

  const MenuMatrix({
    super.key,
    required this.days,
    required this.start,
    required this.mealSlots,
    required this.labels,
    required this.icons,
    required this.selected,
    required this.cellItems,
    required this.onDaySelected,
    required this.onCellTap,
  });

  static const double _labelW = 76;
  static const double _headerH = 52;
  static const double _cellH = 92;
  static const double _rowGap = 10;

  int _offsetOf(DateTime d) {
    final a = DateTime(start.year, start.month, start.day);
    final b = DateTime(d.year, d.month, d.day);
    return b.difference(a).inDays;
  }

  bool _isSelected(DateTime d) =>
      d.year == selected.year && d.month == selected.month && d.day == selected.day;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final dayW =
            ((constraints.maxWidth - _labelW) / 3).clamp(108.0, 156.0).toDouble();
        return SingleChildScrollView(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _labelColumn(context),
              Expanded(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.only(right: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final d in days) _dayColumn(context, d, dayW),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _labelColumn(BuildContext context) {
    final tokens = context.tokens;
    return Column(
      children: [
        const SizedBox(height: _headerH),
        for (final slot in mealSlots)
          Padding(
            padding: const EdgeInsets.only(bottom: _rowGap),
            child: SizedBox(
              width: _labelW,
              height: _cellH,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icons[slot] ?? Icons.restaurant,
                      size: 22, color: context.cs.primary),
                  const SizedBox(height: 6),
                  Text(
                    labels[slot] ?? slot,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: tokens.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _dayColumn(BuildContext context, DateTime d, double w) {
    final off = _offsetOf(d);
    return SizedBox(
      width: w,
      child: Column(
        children: [
          SizedBox(
            height: _headerH,
            child: _DayHeader(
              date: d,
              selected: _isSelected(d),
              onTap: () => onDaySelected(d),
            ),
          ),
          ...mealSlots.map((slot) {
            final its = cellItems(off, slot);
            return Padding(
              padding: const EdgeInsets.fromLTRB(4, 0, 4, _rowGap),
              child: SizedBox(
                height: _cellH,
                child: _Cell(
                  items: its,
                  onTap: () => onCellTap(d, slot, its),
                ),
              ),
            );
          }),
        ],
      ),
    );
  }
}

class _DayHeader extends StatelessWidget {
  final DateTime date;
  final bool selected;
  final VoidCallback onTap;

  const _DayHeader({
    required this.date,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;
    final dow = _cap(DateFormat('E', 'ru').format(date));
    final day = DateFormat('d', 'ru').format(date);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? cs.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              dow,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: selected ? Colors.white.withOpacity(0.85) : tokens.textSecondary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              day,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
                color: selected ? Colors.white : cs.onSurface,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  final VoidCallback onTap;

  const _Cell({required this.items, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final radius = BorderRadius.circular(16);
    final empty = items.isEmpty;
    final img = _heroImage(items);
    final extra = items.length > 1 ? items.length - 1 : 0;

    Widget content;
    if (empty) {
      content = Center(
        child: Icon(Icons.add, color: tokens.textSecondary, size: 24),
      );
    } else {
      content = Stack(
        fit: StackFit.expand,
        children: [
          if (img == null)
            Center(
              child: Icon(Icons.restaurant, color: tokens.textSecondary, size: 28),
            )
          else
            CachedNetworkImage(
              imageUrl: img,
              fit: BoxFit.cover,
              placeholder: (_, __) => const Center(
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
              errorWidget: (_, __, ___) => Center(
                child: Icon(Icons.restaurant, color: tokens.textSecondary, size: 28),
              ),
            ),
          if (extra > 0)
            Positioned(
              right: 6,
              bottom: 6,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: context.cs.primary,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '+$extra',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
        ],
      );
    }

    return Material(
      color: tokens.surfaceAlt,
      borderRadius: radius,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: empty ? null : onTap,
        child: content,
      ),
    );
  }
}
