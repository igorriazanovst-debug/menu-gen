// MG_ACTIVEFAMILY: перезапуск дерева приложения без перезапуска процесса.
//
// Зачем. Смена семьи меняет содержимое всех разделов сразу: холодильник, меню,
// список покупок, дневник, подписка. В вебе на этом месте перезагружается
// страница, и вопрос закрыт. В приложении перезагружать нечего: блоки уже
// созданы и держат состояние прошлой семьи, кэш GET-ответов лежит в
// SharedPreferences, а ключи в нём про семью ничего не знают — путь запроса
// одинаков для любой.
//
// Обходить это по одному разделу — плохая затея. Разделов пять, добавится
// шестой, и однажды кто-нибудь забудет его сбросить: человек увидит на экране
// данные семьи, из которой уже вышел. Ошибка тихая и выглядит как утечка чужого.
//
// Поэтому после смены семьи дерево пересобирается целиком: ключ меняется, все
// блоки создаются заново и идут за данными на сервер. Процесс при этом живёт,
// токен и настройки на месте — выходить из аккаунта не требуется.
import 'package:flutter/material.dart';

class AppRestart extends StatefulWidget {
  final Widget child;
  const AppRestart({super.key, required this.child});

  /// Пересобрать дерево. Вызывать после того, как выбор семьи уже сохранён на
  /// сервере и кэши очищены, — иначе новые блоки успеют прочитать старое.
  static void restart(BuildContext context) {
    context.findAncestorStateOfType<_AppRestartState>()?._restart();
  }

  @override
  State<AppRestart> createState() => _AppRestartState();
}

class _AppRestartState extends State<AppRestart> {
  Key _key = UniqueKey();

  void _restart() => setState(() => _key = UniqueKey());

  @override
  Widget build(BuildContext context) => KeyedSubtree(key: _key, child: widget.child);
}
