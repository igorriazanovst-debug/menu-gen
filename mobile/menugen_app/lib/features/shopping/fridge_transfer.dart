// MG_SHOP2FRIDGE: перенос купленного из списка в холодильник.
//
// Кнопка отправляет в холодильник всё купленное разом, и до сих пор делала это
// молча — по одному нажатию, без возможности передумать. Отменить перенос
// нечем: убирать позиции придётся вручную из холодильника. Поэтому сначала
// спрашиваем и показываем, что именно уедет.
//
// Отбор кандидатов — отдельная функция: тем же правилом решается, показывать ли
// кнопку вообще, и раньше это условие было выписано в двух местах.
import 'package:flutter/material.dart';

import 'models/shopping_models.dart';

/// Что уедет в холодильник: купленное, ещё не добавленное и съедобное
/// (корм, химия и гигиена в холодильник не кладутся).
List<ShoppingItem> fridgeCandidates(List<ShoppingItem> items) =>
    items.where((it) => it.isPurchased && !it.inFridge && it.fridgeEligible).toList();

/// Текст подтверждения: сколько позиций и какие именно.
String fridgeConfirmText(List<ShoppingItem> candidates, {int maxNames = 5}) {
  final names = candidates.map((it) => it.name).toList();
  final shown = names.take(maxNames).join(', ');
  final rest = names.length - maxNames;
  return rest > 0 ? '$shown и ещё $rest' : shown;
}

/// Спрашивает подтверждение. true — пользователь согласился.
Future<bool> confirmAddToFridge(BuildContext context, List<ShoppingItem> candidates) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('Добавить в холодильник: ${candidates.length}?'),
      content: Text(fridgeConfirmText(candidates)),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Добавить')),
      ],
    ),
  );
  return ok ?? false;
}
