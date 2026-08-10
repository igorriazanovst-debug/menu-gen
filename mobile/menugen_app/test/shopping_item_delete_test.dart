// MG_SHOPDEL: удаление товара из списка покупок долгим нажатием.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/shopping/item_delete.dart';
import 'package:menugen_app/features/shopping/models/shopping_models.dart';

class _MockApi extends Mock implements ApiClient {}

const _milk = ShoppingItem(
  id: 42,
  name: 'Молоко',
  quantity: null,
  unit: '',
  category: '',
  isPurchased: false,
);

/// Строка ровно как в списке: жест снаружи, отмечаемый чекбокс внутри. Важно
/// именно так: у чекбокса свой обработчик нажатия, и долгое нажатие должно
/// выиграть у него, а не отметить покупку.
Future<void> _pumpRow(
  WidgetTester tester, {
  required ApiClient api,
  required bool canManage,
  void Function(Object error)? onError,
  void Function(bool value)? onToggle,
}) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: Scaffold(
      body: Builder(
        builder: (ctx) => GestureDetector(
          behavior: HitTestBehavior.opaque,
          onLongPress: canManage
              ? () async {
                  try {
                    await deleteShoppingItem(
                      context: ctx,
                      api: api,
                      listId: 5,
                      item: _milk,
                    );
                  } catch (e) {
                    onError?.call(e);
                  }
                }
              : null,
          child: CheckboxListTile(
            value: false,
            onChanged: (v) => onToggle?.call(v ?? false),
            title: const Text('Молоко'),
          ),
        ),
      ),
    ),
  ));
  await tester.pump();
}

void main() {
  setUpAll(() => registerFallbackValue(''));

  late _MockApi api;

  setUp(() {
    api = _MockApi();
    when(() => api.delete(any())).thenAnswer((_) async => null);
  });

  testWidgets('долгое нажатие спрашивает подтверждение, а не удаляет сразу', (tester) async {
    await _pumpRow(tester, api: api, canManage: true);

    await tester.longPress(find.text('Молоко'));
    await tester.pumpAndSettle();

    expect(find.text('Удалить товар?'), findsOneWidget);
    expect(find.textContaining('«Молоко»'), findsOneWidget);
    verifyNever(() => api.delete(any()));
  });

  testWidgets('согласие удаляет позицию на бэкенде', (tester) async {
    await _pumpRow(tester, api: api, canManage: true);

    await tester.longPress(find.text('Молоко'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Удалить'));
    await tester.pumpAndSettle();

    verify(() => api.delete('/shopping/lists/5/items/42/')).called(1);
  });

  testWidgets('отмена оставляет товар на месте', (tester) async {
    await _pumpRow(tester, api: api, canManage: true);

    await tester.longPress(find.text('Молоко'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Отмена'));
    await tester.pumpAndSettle();

    verifyNever(() => api.delete(any()));
  });

  testWidgets('без прав на список долгое нажатие ничего не открывает', (tester) async {
    await _pumpRow(tester, api: api, canManage: false);

    await tester.longPress(find.text('Молоко'));
    await tester.pumpAndSettle();

    expect(find.text('Удалить товар?'), findsNothing);
    verifyNever(() => api.delete(any()));
  });

  testWidgets('отказ сервера (403) не проглатывается', (tester) async {
    when(() => api.delete(any())).thenThrow(Exception('403'));
    Object? seen;
    await _pumpRow(tester, api: api, canManage: true, onError: (e) => seen = e);

    await tester.longPress(find.text('Молоко'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Удалить'));
    await tester.pumpAndSettle();

    expect(seen, isNotNull);
  });

  testWidgets('долгое нажатие не отмечает покупку', (tester) async {
    bool? toggled;
    await _pumpRow(tester, api: api, canManage: true, onToggle: (v) => toggled = v);

    await tester.longPress(find.text('Молоко'));
    await tester.pumpAndSettle();

    expect(find.text('Удалить товар?'), findsOneWidget);
    expect(toggled, isNull);
  });

  testWidgets('подтверждение возвращает выбор пользователя', (tester) async {
    bool? answer;
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: Scaffold(
        body: Builder(
          builder: (ctx) => TextButton(
            onPressed: () async => answer = await confirmDeleteItem(ctx, _milk),
            child: const Text('go'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, 'Удалить'));
    await tester.pumpAndSettle();

    expect(answer, isTrue);
  });
}
