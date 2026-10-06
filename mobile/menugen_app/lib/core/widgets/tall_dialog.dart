// MG_TALLDIALOG: диалог, который не сжимается поднятой клавиатурой.
//
// Обычный `AlertDialog` с содержимым фиксированной высоты ведёт себя на
// телефоне плохо, и выглядит это не как ошибка вёрстки, а как сломанная
// функция. Клавиатура забирает примерно треть экрана; диалог ужимается в
// остаток, содержимое не влезает, и от списка подсказок под полем поиска
// остаётся полторы строки, обрезанные посередине. Человек видит поле, видит
// обрывок строки и не понимает, что ниже есть ещё двенадцать находок.
//
// Отсюда два правила этого виджета:
//
// * Высота считается от ТОГО, ЧТО ОСТАЛОСЬ, а не задаётся числом. Клавиатура
//   появилась — диалог стал ниже на её высоту, но занял весь остаток, а не
//   сжался до крошки. Клавиатура ушла — занял почти весь экран.
// * Шапка и кнопки прижаты, середина растягивается. Всё, что отдано в `child`,
//   получает ровно остаток по высоте, и список может честно сказать «мне
//   столько», а не упираться в выдуманные 220 точек.
//
// Поля вокруг намеренно маленькие: на телефоне каждая отданная рамке точка —
// это минус строка списка.
import 'dart:math' as math;

import 'package:flutter/material.dart';

class TallDialog extends StatelessWidget {
  /// Заголовок. Намеренно мелкий: заголовок из трёх слов не стоит двух строк
  /// списка.
  final String title;

  /// Содержимое. Получает всю высоту, оставшуюся от шапки и кнопок, —
  /// растягиваться внутри него уже его забота.
  final Widget child;

  /// Кнопки внизу, одной строкой справа.
  final List<Widget> actions;

  /// Ниже этого не ужимаемся даже на маленьком экране с большой клавиатурой:
  /// лучше дать диалогу уехать под клавиатуру, чем показать щель.
  final double minHeight;

  const TallDialog({
    super.key,
    required this.title,
    required this.child,
    this.actions = const [],
    this.minHeight = 260,
  });

  /// Поля диалога от краёв экрана.
  static const EdgeInsets _inset = EdgeInsets.symmetric(horizontal: 12, vertical: 12);

  /// Коробка диалога. По ней тест меряет высоту: проверять надо само число,
  /// а не «на глаз по скриншоту» — именно так эта поломка и доехала до
  /// телефона.
  static const Key boxKey = Key('tall-dialog-box');

  /// Сколько высоты диалог может занять здесь и сейчас.
  ///
  /// Вынесено отдельно и сделано статическим, потому что это и есть то, что
  /// ломалось: число считается из `MediaQuery`, и проверять его надо прямо,
  /// а не через догадки по скриншоту.
  static double availableHeight(BuildContext context) {
    final media = MediaQuery.of(context);
    final free = media.size.height -
        media.viewInsets.bottom -
        media.padding.top -
        media.padding.bottom -
        _inset.vertical;
    return math.max(0, free);
  }

  @override
  Widget build(BuildContext context) {
    final height = math.max(minHeight, availableHeight(context));

    return Dialog(
      insetPadding: _inset,
      clipBehavior: Clip.antiAlias,
      child: SizedBox(
        key: boxKey,
        height: height,
        width: double.infinity,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
              child: Text(
                title,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: child,
              ),
            ),
            if (actions.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: actions,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
