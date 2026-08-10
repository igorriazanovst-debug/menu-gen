// MG_SHOPDEL: удаление товара долгим нажатием по строке списка.
//
// Раньше удалить позицию можно было только через режим редактирования: войти в
// него, найти строку, нажать корзину, выйти. Для одной случайно добавленной
// позиции это долго, а на телефоне долгое нажатие — привычный способ добраться
// до действий над строкой.
//
// Удаление необратимо, а долгое нажатие легко сделать случайно, поэтому оно
// только открывает подтверждение — само по себе ничего не удаляет.
//
// Право проверяет и бэкенд: DELETE позиции разрешён владельцу списка (главе
// семьи), остальным — 403. Клиент лишь не показывает того, что всё равно не
// сработает.
import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import 'models/shopping_models.dart';

/// Спрашивает подтверждение на удаление позиции. true — согласие.
Future<bool> confirmDeleteItem(BuildContext context, ShoppingItem item) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Удалить товар?'),
      content: Text('«${item.name}» будет убран из списка.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: Theme.of(ctx).colorScheme.error),
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Удалить'),
        ),
      ],
    ),
  );
  return ok ?? false;
}

/// Спрашивает и удаляет. Возвращает true, если позиция удалена.
/// Ошибку запроса пробрасывает — показать её должен экран.
Future<bool> deleteShoppingItem({
  required BuildContext context,
  required ApiClient api,
  required int listId,
  required ShoppingItem item,
}) async {
  if (!await confirmDeleteItem(context, item)) return false;
  await api.delete('/shopping/lists/$listId/items/${item.id}/');
  return true;
}
