// MG_NOCUT: строка еды в дневнике.
//
// Вынесена из экрана отдельным виджетом, чтобы её можно было проверять: на
// телефоне с крупным системным шрифтом от названия оставалось «куриное …», а
// от БЖУ — «Б 19 · Ж 2.1…», и поймать это можно только померив настоящую
// строку на настоящей ширине.
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/display/nutrition_detail.dart'; // MG_NUTRIDETAIL
import '../../../core/display/display_prefs_cubit.dart'; // MG_NUTRIDETAIL
import '../models/diary_entry.dart';

class DiaryEntryTile extends StatelessWidget {
  final DiaryEntry entry;
  final Color? accent; // DIARY_COLOR
  final void Function(bool)? onToggleEaten;
  final VoidCallback onDelete;
  final VoidCallback? onEdit; // DIARY_EDIT

  const DiaryEntryTile({
    super.key,
    required this.entry,
    this.accent,
    required this.onToggleEaten,
    required this.onDelete,
    this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    // Множитель показываем, только когда он не единица: «×1» у каждой строки —
    // шум, за которым теряется то, ради чего в дневник и смотрят.
    final showQty = entry.quantity != 1;
    final qty = '×${entry.quantity.toStringAsFixed(entry.quantity == entry.quantity.roundToDouble() ? 0 : 1)}';
    // MG_DIARYKCAL: калорийность самой записи. Считается тем же способом, что и
    // итог приёма (nutrition × quantity), поэтому сумма в заголовке приёма
    // всегда сходится со строками под ним.
    final kcal = entry.calories > 0 ? '${entry.calories.round()} ккал' : '';
    // MG_NUTRIDETAIL: подробность строки — выбор человека, один на приложение
    // и веб. Названия приёма здесь больше нет: оно стоит в заголовке раздела,
    // прямо над этой же строкой, и повторять его значит тратить ту ширину,
    // где должны быть БЖУ.
    final detail = context.watch<DisplayPrefsCubit>().state.detail;
    final macros = detail.showMacros
        ? macrosShort(
            proteins: entry.proteins,
            fats: entry.fats,
            carbs: entry.carbs,
          )
        : '';
    final subtitle = [
      // Вес порции — только в подробном режиме, как и договаривались:
      // «кратко» — калории, «обычно» — калории и БЖУ, «подробно» — ещё и вес.
      if (entry.grams != null && detail.showGrams) '${entry.grams} г',
      if (macros.isNotEmpty) macros,
      // MG_HEADKEEPS: кто внёс, если не сам владелец.
      if (entry.addedByName != null) 'внёс(ла) ${entry.addedByName}',
    ].join(' · ');
    return Dismissible(
      key: ValueKey('diary-${entry.id}'),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => onDelete(),
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: 4),
        clipBehavior: Clip.antiAlias,
        child: Container(
          // DIARY_COLOR: цветная левая полоса по цвету приёма.
          decoration: BoxDecoration(
            border: Border(
              left: BorderSide(color: accent ?? Colors.transparent, width: 5),
            ),
          ),
          // MG_NOCUT: не ListTile.
          //
          // ListTile отдаёт названию остаток ширины после чекбокса, калорий и
          // кнопки меню, и на телефоне с крупным системным шрифтом от
          // названия оставалось «куриное …», а от БЖУ — «Б 19 · Ж 2.1…».
          // Обрезанное название и обрезанные числа — это ровно то, ради чего
          // строку и читают.
          //
          // Теперь название занимает всю ширину строки и переносится на вторую
          // строку, если не влезло, а БЖУ и калории делят строку под ним.
          child: Padding(
            padding: const EdgeInsets.fromLTRB(4, 6, 4, 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Checkbox(
                  value: entry.isEaten,
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  onChanged: onToggleEaten == null
                      ? null
                      : (v) => onToggleEaten!(v ?? false),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text.rich(
                        TextSpan(children: [
                          TextSpan(
                            text: entry.displayTitle.isNotEmpty ? entry.displayTitle : '—',
                          ),
                          // Множитель — частью названия: «×2» отдельной
                          // колонкой съедало ширину у самого названия.
                          if (showQty)
                            TextSpan(
                              text: ' $qty',
                              style: TextStyle(color: Colors.grey.shade600),
                            ),
                          // MG_HEADKEEPS: запись внёс не сам человек.
                          if (entry.addedByName != null)
                            const TextSpan(text: ' 👑', style: TextStyle(fontSize: 13)),
                        ]),
                        // Предела по числу строк нет вовсе: название блюда
                        // обрезать нельзя. Любой предел — это многоточие на
                        // чьём-то длинном названии при крупном шрифте, и
                        // проверка это каждый раз и показывала: сперва на
                        // двух строках, потом на трёх.
                        style: const TextStyle(fontSize: 15),
                      ),
                      if (subtitle.isNotEmpty || kcal.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          // Wrap, а не Row: когда БЖУ и калорийность рядом не
                          // помещаются (крупный шрифт, длинные числа),
                          // калорийность уезжает на свою строку, а не режет
                          // соседа. Ни у строки БЖУ, ни у калорийности предела
                          // по числу строк нет вовсе — обрезать тут нечего.
                          child: Wrap(
                            alignment: WrapAlignment.spaceBetween,
                            crossAxisAlignment: WrapCrossAlignment.end,
                            spacing: 8,
                            runSpacing: 2,
                            children: [
                              if (subtitle.isNotEmpty)
                                Text(
                                  subtitle,
                                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                                ),
                              if (kcal.isNotEmpty)
                                Text(
                                  kcal,
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: accent ?? Colors.grey.shade700,
                                  ),
                                ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.more_vert, size: 20),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  tooltip: 'Действия',
                  onSelected: (v) {
                    if (v == 'edit') {
                      onEdit?.call();
                    } else if (v == 'delete') {
                      onDelete();
                    }
                  },
                  itemBuilder: (_) => const [
                    PopupMenuItem<String>(value: 'edit', child: Text('Изменить')),
                    PopupMenuItem<String>(value: 'delete', child: Text('Удалить')),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
