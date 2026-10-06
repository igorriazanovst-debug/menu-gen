// MG_SUGGEST: список подсказок под полем поиска — один на всё приложение.
//
// Был в трёх местах своей копией: дневник, добавление в список покупок,
// добавление в холодильник. Везде одинаково: контейнер с рамкой, внутри
// плотные строки. И везде одинаково непонятно — ни фона, ни тени, рамка
// `Colors.black12` почти не видна. Строки висели на фоне окна и читались как
// обычный текст: человек не понимал, что это всплывшая подсказка и что по ней
// нажимают.
//
// Что изменилось по существу:
//
// * Список стал слоем: поверхность, тень, скруглённые углы. Так его видно как
//   то, что всплыло над страницей, а не как её часть.
// * Совпавшая часть запроса выделена. Сразу видно, почему строка нашлась, —
//   особенно когда совпало в середине слова («творожная масса» по «творог»).
// * Полоса прокрутки видна всегда, пока список прокручивается. До этого список
//   обрезался на высоте и ничем не показывал, что ниже ещё есть.
// * Действие («Добавить „X“ как новый») прижато вниз и выделено цветом. В
//   списке покупок оно стояло последней строкой среди находок и терялось.
// * Цвета — из токенов скина. Литералы `Colors.black12` и `Colors.grey` второй
//   скин не переживали: рамка там оставалась от первого.
//
// Чего здесь намеренно НЕТ: подсветки первой строки. В макете она была, но на
// телефоне нет наведения, и постоянно выделенная первая строка читается как
// «уже выбрано» — а это неправда, порядок находок не означает выбора.
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Одна подсказка.
class SuggestionItem {
  /// Название. По нему же считается подсветка совпадения.
  final String title;

  /// Вторая строка под названием: «своё», название категории.
  final String? subtitle;

  /// Короткое значение справа: «121 ккал». Не переносится и не ужимается —
  /// место ему выделяется до того, как ужимать название.
  final String? trailing;

  final VoidCallback onTap;

  const SuggestionItem({
    required this.title,
    required this.onTap,
    this.subtitle,
    this.trailing,
  });
}

/// Действие внизу списка — «Добавить „X“ как новый».
class SuggestionAction {
  final String label;
  final IconData icon;
  final VoidCallback onTap;

  const SuggestionAction({
    required this.label,
    required this.onTap,
    this.icon = Icons.add,
  });
}

class SuggestionList extends StatelessWidget {
  final List<SuggestionItem> items;

  /// Строка поиска — по ней подсвечивается совпадение. Пустая — без подсветки.
  final String query;

  /// Сколько найдено всего, если это больше показанного. Пусто — берётся длина.
  final int? totalCount;

  /// Нижнее действие. Показывается, даже когда находок нет вовсе.
  final SuggestionAction? action;

  /// Что сказать, когда искали и не нашли. Пусто — список просто не рисуется.
  final String? emptyText;

  final double maxHeight;

  const SuggestionList({
    super.key,
    required this.items,
    this.query = '',
    this.totalCount,
    this.action,
    this.emptyText,
    this.maxHeight = 220,
  });

  /// Разбить название на части: до совпадения, совпадение, после.
  ///
  /// Сравнение без учёта регистра и с «ё» как «е»: в каталоге соседствуют
  /// «Свёкла» и «Свекла», и подсветка не должна зависеть от того, как человек
  /// набрал. Возвращается `null`, когда подсвечивать нечего.
  static List<String>? splitMatch(String title, String query) {
    final q = _fold(query);
    if (q.isEmpty) return null;
    final idx = _fold(title).indexOf(q);
    if (idx < 0) return null;
    return [
      title.substring(0, idx),
      title.substring(idx, idx + q.length),
      title.substring(idx + q.length),
    ];
  }

  static String _fold(String s) => s.toLowerCase().replaceAll('ё', 'е').trim();

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final cs = context.cs;

    if (items.isEmpty && action == null && (emptyText == null || emptyText!.isEmpty)) {
      return const SizedBox.shrink();
    }

    final shown = totalCount ?? items.length;

    return Container(
      margin: const EdgeInsets.only(top: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        border: Border.all(color: tokens.border),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: cs.onSurface.withOpacity(0.12),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (items.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              color: tokens.surfaceAlt,
              child: Text(
                'Найдено $shown',
                style: TextStyle(fontSize: 12, color: tokens.textSecondary),
              ),
            ),
          if (items.isNotEmpty)
            Flexible(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxHeight: maxHeight),
                child: Scrollbar(
                  thumbVisibility: true,
                  child: ListView.separated(
                    shrinkWrap: true,
                    padding: EdgeInsets.zero,
                    itemCount: items.length,
                    separatorBuilder: (_, __) => Divider(height: 1, thickness: 1, color: tokens.border),
                    itemBuilder: (_, i) => _row(context, items[i]),
                  ),
                ),
              ),
            ),
          if (items.isEmpty && emptyText != null && emptyText!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
              child: Text(
                emptyText!,
                style: TextStyle(fontSize: 13, color: tokens.textSecondary),
              ),
            ),
          if (action != null) _actionRow(context, action!),
        ],
      ),
    );
  }

  Widget _row(BuildContext context, SuggestionItem item) {
    final tokens = context.tokens;
    final parts = splitMatch(item.title, query);

    final title = parts == null
        ? Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis)
        : Text.rich(
            TextSpan(children: [
              TextSpan(text: parts[0]),
              TextSpan(
                text: parts[1],
                style: TextStyle(fontWeight: FontWeight.w700, color: context.cs.primary),
              ),
              TextSpan(text: parts[2]),
            ]),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          );

    return InkWell(
      onTap: item.onTap,
      child: Padding(
        // Справа больше: там идёт полоса прокрутки, и текст не должен под неё заезжать.
        padding: const EdgeInsets.fromLTRB(14, 10, 20, 10),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  DefaultTextStyle.merge(
                    style: const TextStyle(fontSize: 15),
                    child: title,
                  ),
                  if (item.subtitle != null && item.subtitle!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        item.subtitle!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 12, color: tokens.textSecondary),
                      ),
                    ),
                ],
              ),
            ),
            if (item.trailing != null && item.trailing!.isNotEmpty) ...[
              const SizedBox(width: 8),
              Text(
                item.trailing!,
                style: TextStyle(fontSize: 12, color: tokens.textSecondary),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _actionRow(BuildContext context, SuggestionAction a) {
    final tokens = context.tokens;
    // Текст поверх акцента — тёмный: акцент светлый, и белым по нему не прочесть.
    const onAccent = Color(0xFF3A2A12);
    return InkWell(
      onTap: a.onTap,
      child: Container(
        width: double.infinity,
        color: tokens.accent,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Icon(a.icon, size: 18, color: onAccent),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                a.label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 14, color: onAccent),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
