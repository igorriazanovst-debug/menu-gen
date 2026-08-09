// MG_SHOP2FRIDGE / MG_SHOPIMG / MG_SHAREERR — изменения в списке покупок.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/core/widgets/full_image_viewer.dart';
import 'package:menugen_app/features/shopping/fridge_transfer.dart';
import 'package:menugen_app/features/shopping/models/shopping_models.dart';
import 'package:menugen_app/features/shopping/share_error_text.dart';
import 'package:menugen_app/features/shopping/widgets/item_photo_thumb.dart';

ShoppingItem _item({
  int id = 1,
  String name = 'Молоко',
  bool purchased = true,
  bool inFridge = false,
  bool eligible = true,
}) =>
    ShoppingItem(
      id: id,
      name: name,
      quantity: null,
      unit: '',
      category: '',
      isPurchased: purchased,
      inFridge: inFridge,
      fridgeEligible: eligible,
    );

void main() {
  group('что уедет в холодильник', () {
    test('только купленное', () {
      final items = [_item(id: 1), _item(id: 2, purchased: false)];

      expect(fridgeCandidates(items).map((i) => i.id), [1]);
    });

    test('без того, что уже там', () {
      expect(fridgeCandidates([_item(inFridge: true)]), isEmpty);
    });

    test('без несъедобного — корма, химии, гигиены', () {
      expect(fridgeCandidates([_item(eligible: false)]), isEmpty);
    });

    test('пустой список ничего не предлагает', () {
      expect(fridgeCandidates(const []), isEmpty);
    });
  });

  group('текст подтверждения', () {
    test('перечисляет позиции', () {
      final text = fridgeConfirmText([_item(name: 'Молоко'), _item(id: 2, name: 'Сыр')]);

      expect(text, 'Молоко, Сыр');
    });

    test('длинный список сворачивается', () {
      final many = List.generate(8, (i) => _item(id: i, name: 'Товар$i'));

      expect(fridgeConfirmText(many), contains('и ещё 3'));
    });
  });

  group('подтверждение переноса', () {
    Future<void> pump(WidgetTester tester, void Function(BuildContext) onTap) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(
          body: Builder(
            builder: (ctx) => TextButton(onPressed: () => onTap(ctx), child: const Text('go')),
          ),
        ),
      ));
      await tester.tap(find.text('go'));
      await tester.pumpAndSettle();
    }

    testWidgets('спрашивает и показывает, что именно уедет', (tester) async {
      bool? answer;
      await pump(tester, (ctx) async {
        answer = await confirmAddToFridge(ctx, [_item(name: 'Молоко'), _item(id: 2, name: 'Сыр')]);
      });

      expect(find.text('Добавить в холодильник: 2?'), findsOneWidget);
      expect(find.text('Молоко, Сыр'), findsOneWidget);

      await tester.tap(find.text('Отмена'));
      await tester.pumpAndSettle();
      expect(answer, isFalse);
    });

    testWidgets('согласие возвращает true', (tester) async {
      bool? answer;
      await pump(tester, (ctx) async {
        answer = await confirmAddToFridge(ctx, [_item()]);
      });

      await tester.tap(find.text('Добавить'));
      await tester.pumpAndSettle();
      expect(answer, isTrue);
    });
  });

  group('фото товара', () {
    testWidgets('по нажатию открывается во весь экран', (tester) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: const Scaffold(
          body: Center(child: ItemPhotoThumb(url: 'https://example.org/milk.jpg')),
        ),
      ));
      await tester.pump();

      await tester.tap(find.byType(ItemPhotoThumb));
      // Не pumpAndSettle: пока картинка «грузится», крутится индикатор —
      // анимация не заканчивается никогда.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.byType(FullImageViewer), findsOneWidget);
    });
  });

  group('почему не выдался доступ', () {
    test('незнакомый адрес объясняется, а не прячется за «проверьте email»', () {
      final text = grantErrorText(
        const ApiException(message: 'Пользователь не найден.', statusCode: 400),
        byPhone: false,
      );

      expect(text, contains('адресом'));
      expect(text, contains('зарегистрирован'));
    });

    test('для телефона формулировка своя', () {
      final text = grantErrorText(
        const ApiException(message: 'Пользователь с таким телефоном не найден.', statusCode: 400),
        byPhone: true,
      );

      expect(text, contains('номером'));
    });

    test('нет прав — так и говорим', () {
      expect(
        grantErrorText(const ApiException(message: 'Нет прав.', statusCode: 403), byPhone: false),
        contains('Нет прав'),
      );
    });

    test('нет сети — про сеть, а не про адрес', () {
      expect(
        grantErrorText(const ApiException(message: 'Нет подключения к интернету'), byPhone: false),
        contains('Нет связи с сервером'),
      );
    });

    test('имя класса наружу не выходит', () {
      expect(grantErrorText(Exception('boom'), byPhone: false), isNot(contains('Exception')));
    });
  });
}
