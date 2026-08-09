// MG_PHONESHARE: выдача доступа к списку покупок по e-mail или по телефону.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/features/shopping/screens/shopping_access_sheet.dart';

class _MockApi extends Mock implements ApiClient {}

Future<void> _pumpSheet(WidgetTester tester, ApiClient api) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: ShoppingAccessSheet(apiClient: api, listId: 5)),
  ));
  await tester.pumpAndSettle();
}

void main() {
  late _MockApi api;

  setUp(() {
    api = _MockApi();
    when(() => api.get('/shopping/lists/5/access/')).thenAnswer((_) async => const []);
    when(() => api.post(any(), data: any(named: 'data'))).thenAnswer((_) async => const {});
  });

  testWidgets('по умолчанию доступ выдаётся по e-mail', (tester) async {
    await _pumpSheet(tester, api);

    await tester.enterText(find.widgetWithText(TextField, 'email пользователя'), 'a@b.ru');
    await tester.tap(find.widgetWithText(FilledButton, 'Выдать доступ'));
    await tester.pumpAndSettle();

    final data = verify(() => api.post('/shopping/lists/5/access/', data: captureAny(named: 'data')))
        .captured
        .single as Map;
    expect(data['email'], 'a@b.ru');
    expect(data.containsKey('phone'), isFalse);
  });

  testWidgets('в режиме телефона уходит phone вместо email', (tester) async {
    await _pumpSheet(tester, api);

    await tester.tap(find.text('Телефон'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'телефон пользователя'), '+7 900 000-00-00');
    await tester.tap(find.widgetWithText(FilledButton, 'Выдать доступ'));
    await tester.pumpAndSettle();

    final data = verify(() => api.post('/shopping/lists/5/access/', data: captureAny(named: 'data')))
        .captured
        .single as Map;
    expect(data['phone'], '+7 900 000-00-00');
    expect(data.containsKey('email'), isFalse);
  });

  testWidgets('пустой телефон не уходит на бэкенд', (tester) async {
    await _pumpSheet(tester, api);

    await tester.tap(find.text('Телефон'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Выдать доступ'));
    await tester.pumpAndSettle();

    expect(find.text('Введите телефон.'), findsOneWidget);
    verifyNever(() => api.post(any(), data: any(named: 'data')));
  });

  // MG_SHAREERR: раньше на ЛЮБУЮ ошибку показывалось «пользователь должен быть
  // зарегистрирован» — и когда дело было в правах, и когда пропала сеть. Теперь
  // причину называет сервер, а клиент лишь поясняет самую частую из них.
  testWidgets('незнакомый номер объясняется словами сервера', (tester) async {
    when(() => api.post(any(), data: any(named: 'data'))).thenThrow(
      const ApiException(message: 'Пользователь с таким телефоном не найден.', statusCode: 400),
    );
    await _pumpSheet(tester, api);

    await tester.tap(find.text('Телефон'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'телефон пользователя'), '+79000000000');
    await tester.tap(find.widgetWithText(FilledButton, 'Выдать доступ'));
    await tester.pumpAndSettle();

    expect(find.textContaining('зарегистрирован'), findsWidgets);
  });

  testWidgets('нехватка прав не выдаётся за отсутствие пользователя', (tester) async {
    when(() => api.post(any(), data: any(named: 'data')))
        .thenThrow(const ApiException(message: 'Нет прав.', statusCode: 403));
    await _pumpSheet(tester, api);

    await tester.enterText(find.widgetWithText(TextField, 'email пользователя'), 'a@b.ru');
    await tester.tap(find.widgetWithText(FilledButton, 'Выдать доступ'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Нет прав управлять доступом'), findsOneWidget);
  });

  // Ограничение видно до попытки — самая частая причина отказа.
  testWidgets('в форме сказано, что доступ только для зарегистрированных', (tester) async {
    await _pumpSheet(tester, api);

    expect(find.textContaining('уже зарегистрирован в MenuGen'), findsOneWidget);
  });
}
