// MG_LEGAL: разбор ответа /legal/ и экраны документов.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/router/app_router.dart';
import 'package:menugen_app/features/legal/legal_repository.dart';
import 'package:menugen_app/features/legal/models/legal_info.dart';
import 'package:menugen_app/features/legal/screens/legal_document_screen.dart';

class _MockApi extends Mock implements ApiClient {}

const _payload = {
  'company_name': 'ИП Иванов И.И.',
  'inn': '770000000000',
  'ogrnip': '320000000000000',
  'legal_address': 'Москва, ул. Тестовая, 1',
  'email': 'info@menugen.ru',
  'phone': '+7 900 000-00-00',
  'bank_name': 'АО «Банк»',
  'bank_bik': '044525000',
  'bank_account': '40802810000000000000',
  'corr_account': '30101810000000000000',
  'requisites_extra': 'Дополнительно',
  'offer_text': 'Текст оферты',
  'privacy_text': 'Текст политики',
  'logo_url': null,
  'updated_at': '2026-08-01T00:00:00Z',
};

void main() {
  group('LegalInfo.fromJson', () {
    test('разбирает полный ответ', () {
      final info = LegalInfo.fromJson(Map<String, dynamic>.from(_payload));

      expect(info.companyName, 'ИП Иванов И.И.');
      expect(info.inn, '770000000000');
      expect(info.offerText, 'Текст оферты');
      expect(info.privacyText, 'Текст политики');
      expect(info.logoUrl, isNull);
      expect(info.hasRequisites, isTrue);
    });

    test('пустой ответ не роняет разбор', () {
      final info = LegalInfo.fromJson(const {});

      expect(info.companyName, '');
      expect(info.offerText, '');
      expect(info.hasRequisites, isFalse);
    });

    test('числовые поля приводятся к строке', () {
      final info = LegalInfo.fromJson(const {'inn': 770000000000, 'bank_bik': 44525000});

      expect(info.inn, '770000000000');
      expect(info.bankBik, '44525000');
    });

    test('пустой logo_url считается отсутствующим', () {
      final info = LegalInfo.fromJson(const {'logo_url': ''});

      expect(info.logoUrl, isNull);
    });
  });

  group('legalDocFromSlug', () {
    test('узнаёт известные документы', () {
      expect(legalDocFromSlug('offer'), LegalDoc.offer);
      expect(legalDocFromSlug('privacy'), LegalDoc.privacy);
      expect(legalDocFromSlug('requisites'), LegalDoc.requisites);
    });

    test('неизвестный slug открывает политику, а не падает', () {
      expect(legalDocFromSlug('какая-то-чушь'), LegalDoc.privacy);
      expect(legalDocFromSlug(null), LegalDoc.privacy);
    });
  });

  group('LegalRepository', () {
    test('загружает документ с бэкенда', () async {
      final api = _MockApi();
      when(() => api.get('/legal/')).thenAnswer((_) async => Map<String, dynamic>.from(_payload));

      final info = await LegalRepository(api).load();

      expect(info.offerText, 'Текст оферты');
      verify(() => api.get('/legal/')).called(1);
    });

    test('неожиданный формат ответа даёт ошибку, а не молчаливый пустой документ', () async {
      final api = _MockApi();
      when(() => api.get('/legal/')).thenAnswer((_) async => 'не объект');

      expect(() => LegalRepository(api).load(), throwsA(isA<FormatException>()));
    });
  });

  group('LegalDocumentScreen', () {
    testWidgets('показывает текст оферты из preloaded без запроса к API', (tester) async {
      final api = _MockApi();

      await tester.pumpWidget(MaterialApp(
        home: LegalDocumentScreen(
          apiClient: api,
          doc: LegalDoc.offer,
          preloaded: LegalInfo.fromJson(Map<String, dynamic>.from(_payload)),
        ),
      ));

      expect(find.text('Текст оферты'), findsOneWidget);
      verifyNever(() => api.get(any()));
    });

    testWidgets('грузит документ сам, если пришли по прямой ссылке', (tester) async {
      final api = _MockApi();
      when(() => api.get('/legal/')).thenAnswer((_) async => Map<String, dynamic>.from(_payload));

      await tester.pumpWidget(MaterialApp(
        home: LegalDocumentScreen(apiClient: api, doc: LegalDoc.privacy),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Текст политики'), findsOneWidget);
      verify(() => api.get('/legal/')).called(1);
    });

    testWidgets('незаполненные реквизиты показывают заглушку, а не пустой экран', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: LegalDocumentScreen(
          apiClient: _MockApi(),
          doc: LegalDoc.requisites,
          preloaded: LegalInfo.fromJson(const {}),
        ),
      ));

      expect(find.text('Реквизиты пока не заполнены.'), findsOneWidget);
    });

    testWidgets('ошибка загрузки предлагает повторить', (tester) async {
      final api = _MockApi();
      when(() => api.get('/legal/')).thenThrow(Exception('нет сети'));

      await tester.pumpWidget(MaterialApp(
        home: LegalDocumentScreen(apiClient: api, doc: LegalDoc.offer),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Не удалось загрузить документ.'), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'Повторить'), findsOneWidget);
    });
  });

  // MG_LEGAL: раздел закрытый — только после входа в аккаунт.
  group('доступ к документам', () {
    test('гостя с документов уводит на вход', () {
      expect(authRedirect(isLoggedIn: false, location: '/legal'), '/login');
      expect(authRedirect(isLoggedIn: false, location: '/legal/privacy'), '/login');
    });

    test('вошедшему документы открыты', () {
      expect(authRedirect(isLoggedIn: true, location: '/legal'), isNull);
      expect(authRedirect(isLoggedIn: true, location: '/legal/offer'), isNull);
    });

    test('вход и регистрация остаются доступны гостю', () {
      for (final path in ['/login', '/register', '/register/phone']) {
        expect(authRedirect(isLoggedIn: false, location: path), isNull, reason: path);
      }
    });

    test('вошедшего с экранов входа уводит в меню', () {
      expect(authRedirect(isLoggedIn: true, location: '/login'), '/menu');
      expect(authRedirect(isLoggedIn: true, location: '/register/phone'), '/menu');
    });

    test('премиум-ограничение осталось на месте', () {
      expect(authRedirect(isLoggedIn: true, location: '/fridge', premiumLocked: true), '/paywall');
      expect(authRedirect(isLoggedIn: true, location: '/legal', premiumLocked: true), isNull,
          reason: 'документы не должны требовать подписки');
    });
  });
}
