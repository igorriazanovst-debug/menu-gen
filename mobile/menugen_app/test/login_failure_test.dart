// MG_LOGINFIX: вход не должен ломаться из-за старого токена, а отказ должен
// быть понятен человеку.
//
// Симптом, с которого всё началось: «собрал apk — не работает логин под уже
// существующими аккаунтами». «Уже существующими» — это ровно те устройства, где
// от прошлой сессии остался токен в хранилище: клиент подставлял его в запрос
// входа, DRF проверяет токен до permission_classes и отвечал 401 ещё до того,
// как дело доходило до логина с паролем.
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/api/dio_api_client.dart';
import 'package:menugen_app/core/api/token_storage.dart';
import 'package:menugen_app/core/config/app_config.dart';
import 'package:menugen_app/features/auth/auth_error_text.dart';

class _MockTokens extends Mock implements TokenStorage {}

/// Перехватывает запрос до сети и отдаёт заранее заданный ответ, запоминая
/// заголовки — так видно, что реально ушло бы на сервер.
class _CapturingAdapter implements HttpClientAdapter {
  final Map<String, dynamic> statuses; // path -> код ответа
  final List<RequestOptions> seen = [];

  _CapturingAdapter({this.statuses = const {}});

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream,
      Future<void>? cancelFuture) async {
    seen.add(options);
    final code = (statuses[options.path] as int?) ?? 200;
    return ResponseBody.fromString('{"access":"new","refresh":"new"}', code,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType]
        });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  setUpAll(() {
    registerFallbackValue(RequestOptions(path: '/'));
  });

  group('какие пути считаются публичными', () {
    test('вход, регистрация и обновление токена — публичные', () {
      expect(isPublicAuthPath('/auth/login/'), isTrue);
      expect(isPublicAuthPath('/auth/refresh/'), isTrue);
      expect(isPublicAuthPath('/auth/email/register/'), isTrue);
      expect(isPublicAuthPath('/auth/phone/start/'), isTrue);
      expect(isPublicAuthPath('/auth/phone/register/'), isTrue);
    });

    test('выход и обычные запросы — нет: им токен нужен', () {
      expect(isPublicAuthPath('/auth/logout/'), isFalse);
      expect(isPublicAuthPath('/users/me/'), isFalse);
      expect(isPublicAuthPath('/recipes/'), isFalse);
    });
  });

  group('заголовок Authorization', () {
    late _MockTokens tokens;

    setUp(() {
      tokens = _MockTokens();
      when(() => tokens.getAccessToken()).thenAnswer((_) async => 'stale-token');
      when(() => tokens.getRefreshToken()).thenAnswer((_) async => 'stale-refresh');
      when(() => tokens.saveTokens(access: any(named: 'access'), refresh: any(named: 'refresh')))
          .thenAnswer((_) async {});
      when(() => tokens.clearTokens()).thenAnswer((_) async {});
    });

    test('на вход не уходит, даже если в хранилище есть старый токен', () async {
      final adapter = _CapturingAdapter();
      final client = DioApiClient(tokenStorage: tokens);
      client.httpClientAdapter = adapter;

      await client.post('/auth/login/', data: {'email': 'a@b.ru', 'password': 'secret12'});

      expect(adapter.seen.single.headers.containsKey('Authorization'), isFalse);
    });

    test('на обычный запрос уходит', () async {
      final adapter = _CapturingAdapter();
      final client = DioApiClient(tokenStorage: tokens);
      client.httpClientAdapter = adapter;

      await client.get('/users/me/');

      expect(adapter.seen.single.headers['Authorization'], 'Bearer stale-token');
    });

    test('401 на входе не запускает обновление токена', () async {
      final adapter = _CapturingAdapter(statuses: {'/auth/login/': 401});
      final client = DioApiClient(tokenStorage: tokens);
      client.httpClientAdapter = adapter;

      await expectLater(
        client.post('/auth/login/', data: {'email': 'a@b.ru', 'password': 'x'}),
        throwsA(isA<ApiException>()),
      );
      // один запрос — без повторной попытки и без похода за refresh
      expect(adapter.seen.length, 1);
      verifyNever(() => tokens.getRefreshToken());
    });
  });

  group('текст ошибки', () {
    test('ошибка сериализатора DRF читается из non_field_errors', () {
      expect(messageFromBody({'non_field_errors': ['Неверные учётные данные.']}),
          'Неверные учётные данные.');
      expect(messageFromBody({'detail': 'Подтвердите e-mail.'}), 'Подтвердите e-mail.');
      expect(messageFromBody({'email': ['Введите корректный адрес.']}), 'Введите корректный адрес.');
      expect(messageFromBody({'code': 'email_not_verified'}), isNull); // код — не текст
      expect(messageFromBody('строка'), isNull);
    });

    test('неподтверждённый e-mail объясняется словами, а не кодом', () {
      final text = authErrorText(const ApiException(
          message: 'Подтвердите e-mail по ссылке из письма.',
          statusCode: 403,
          errorCode: 'email_not_verified'));

      expect(text, contains('не подтверждён'));
      expect(text, isNot(contains('ApiException')));
    });

    test('причину отказа сервера показываем как есть', () {
      expect(authErrorText(const ApiException(message: 'Неверные учётные данные.', statusCode: 400)),
          'Неверные учётные данные.');
    });

    test('нет сети — говорим про сеть, а не про сервер', () {
      expect(authErrorText(const ApiException(message: 'Нет подключения к интернету')),
          contains('Нет связи с сервером'));
    });

    test('слишком много попыток', () {
      expect(authErrorText(const ApiException(message: 'x', statusCode: 429)),
          contains('Слишком много попыток'));
    });

    test('в тексте никогда не всплывает имя класса', () {
      final texts = [
        authErrorText(const ApiException(message: 'x', statusCode: 500)),
        authErrorText(const ApiException(message: 'x', statusCode: 418)),
        authErrorText(Exception('boom')),
      ];
      for (final t in texts) {
        expect(t, isNot(contains('ApiException')));
      }
    });
  });

  group('адрес сервера в сборке', () {
    test('показывается хостом с портом', () {
      // значение по умолчанию — эмулятор; в сборках задаётся --dart-define
      expect(AppConfig.apiHost, '10.0.2.2:8000');
    });
  });
}
