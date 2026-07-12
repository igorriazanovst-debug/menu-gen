import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/cache/recipe_image_cache.dart';
import '../../../core/theme/app_theme.dart';

/// MG_SKIN: матрица меню «приёмы × дни» (редизайн меню, mobile).
///
/// Раскладка «замороженные» строка и столбец:
///  • левая колонка приёмов — липкая при ГОРИЗОНТАЛЬНОМ скролле;
///  • строка дней/дат сверху — липкая при ВЕРТИКАЛЬНОМ скролле;
///  • ячейки скроллятся в обе стороны.
/// Горизонталь общая (заголовок дней и ячейки в одном гориз-скролле),
/// вертикаль синхронизируется: левые подписи следуют за прокруткой ячеек.
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

class MenuMatrix extends StatefulWidget {
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

  @override
  State<MenuMatrix> createState() => _MenuMatrixState();
}

class _MenuMatrixState extends State<MenuMatrix> {
  static const double _labelW = 72;
  static const double _headerH = 46;
  static const double _cellH = 96;
  static const double _rowGap = 10;

  final ScrollController _hCtrl = ScrollController();
  final ScrollController _vCells = ScrollController();
  final ScrollController _vLabels = ScrollController();

  @override
  void initState() {
    super.initState();
    _vCells.addListener(_syncLabels);
  }

  // Левые подписи приёмов следуют за вертикальной прокруткой ячеек.
  void _syncLabels() {
    if (!_vLabels.hasClients) return;
    final target = _vCells.offset.clamp(0.0, _vLabels.position.maxScrollExtent);
    if ((_vLabels.offset - target).abs() > 0.5) _vLabels.jumpTo(target);
  }

  @override
  void dispose() {
    _vCells.removeListener(_syncLabels);
    _hCtrl.dispose();
    _vCells.dispose();
    _vLabels.dispose();
    super.dispose();
  }

  int _offsetOf(DateTime d) {
    final a = DateTime(widget.start.year, widget.start.month, widget.start.day);
    final b = DateTime(d.year, d.month, d.day);
    return b.difference(a).inDays;
  }

  bool _isSelected(DateTime d) =>
      d.year == widget.selected.year &&
      d.month == widget.selected.month &&
      d.day == widget.selected.day;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final dayW =
            ((constraints.maxWidth - _labelW) / 3).clamp(108.0, 156.0).toDouble();
        final daysWidth = widget.days.length * dayW;
        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── Левый «замороженный» столбец: угол + подписи приёмов ──
            SizedBox(
              width: _labelW,
              child: Column(
                children: [
                  const SizedBox(height: _headerH),
                  Expanded(
                    child: SingleChildScrollView(
                      controller: _vLabels,
                      physics: const NeverScrollableScrollPhysics(),
                      child: Column(
                        children: [
                          for (final slot in widget.mealSlots) _labelBox(context, slot),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // ── Правая область: липкая строка дней + скроллящиеся ячейки ──
            Expanded(
              child: SingleChildScrollView(
                controller: _hCtrl,
                scrollDirection: Axis.horizontal,
                child: SizedBox(
                  width: daysWidth,
                  child: Column(
                    children: [
                      // Липкая строка дней/дат (вне вертикального скролла).
                      SizedBox(
                        height: _headerH,
                        child: Row(
                          children: [
                            for (final d in widget.days)
                              SizedBox(
                                width: dayW,
                                child: _DayHeader(
                                  date: d,
                                  selected: _isSelected(d),
                                  onTap: () => widget.onDaySelected(d),
                                ),
                              ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: SingleChildScrollView(
                          controller: _vCells,
                          child: Column(
                            children: [
                              for (final slot in widget.mealSlots)
                                Row(
                                  children: [
                                    for (final d in widget.days)
                                      _cellBox(context, d, slot, dayW),
                                  ],
                                ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _labelBox(BuildContext context, String slot) {
    final tokens = context.tokens;
    return Padding(
      padding: const EdgeInsets.only(bottom: _rowGap),
      child: SizedBox(
        height: _cellH,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(widget.icons[slot] ?? Icons.restaurant,
                size: 22, color: context.cs.primary),
            const SizedBox(height: 6),
            Text(
              widget.labels[slot] ?? slot,
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
    );
  }

  Widget _cellBox(BuildContext context, DateTime d, String slot, double w) {
    final its = widget.cellItems(_offsetOf(d), slot);
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 0, 4, _rowGap),
      child: SizedBox(
        width: w - 8,
        height: _cellH,
        child: _Cell(items: its, onTap: () => widget.onCellTap(d, slot, its)),
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
      borderRadius: BorderRadius.circular(12),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
        decoration: BoxDecoration(
          color: selected ? cs.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              dow,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: selected ? Colors.white.withOpacity(0.85) : tokens.textSecondary,
              ),
            ),
            const SizedBox(height: 1),
            Text(
              day,
              style: TextStyle(
                fontSize: 16,
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
              cacheManager: RecipeImageCache.instance,
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
