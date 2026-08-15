// MG_EMAILVERIFY_MOBILE: регистрация заканчивается письмом, а не входом.
//
// При включённом EMAIL_VERIFICATION_REQUIRED бэкенд отвечает 201-м без токенов.
// Приложение читало `data['access'] as String` безусловно — падало на null, и
// человек видел «Не удалось войти», хотя аккаунт создан и письмо отправлено.
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/api_exception.dart';
import 'package:menugen_app/core/api/token_storage.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/auth/bloc/auth_bloc.dart';
import 'package:menugen_app/features/auth/email_verification.dart';
import 'package:menugen_app/features/auth/screens/login_screen.dart';
import 'package:menugen_app/features/auth/screens/register_screen.dart';
import 'package:menugen_app/features/auth/widgets/verify_email_panel.dart';

class _MockApi extends Mock implements ApiClient {}

class _MockTokens extends Mock implements TokenStorage {}

class _MockAuthBloc extends MockBloc<AuthEvent, AuthState> implements AuthBloc {}

class _Resp {
  final dynamic data;
  _Resp(this.data);
}

const _gateResponse = {
  'detail': 'Регистрация почти завершена. Подтвердите e-mail по ссылке из письма.',
  'email': 'new@example.com',
  'requires_email_verification': true,
};

void main() {
  group('needsEmailVerification', () {
    test('гейт включён — токенов нет', () {
      expect(needsEmailVerification(Map<String, dynamic>.from(_gateResponse)), isTrue);
    });

    test('гейт выключен — пришли токены, вход обычный', () {
      expect(
        needsEmailVerification({'access': 'a.b.c', 'refresh': 'd.e.f'}),
        isFalse,
      );
    });

    test('токенов нет и без явного флага — всё равно входить нечем', () {
      // Страховка: поле могут переименовать, а отсутствие access — факт.
      expect(needsEmailVerification({'detail': 'что-то'}), isTrue);
      expect(needsEmailVerification({'access': ''}), isTrue);
      expect(needsEmailVerification({'access': null}), isTrue);
    });
  });

  group('verificationEmail', () {
    test('берём адрес из ответа', () {
      expect(verificationEmail(Map<String, dynamic>.from(_gateResponse), 'x@y.z'),
          'new@example.com');
    });

    test('бэкенд не прислал — показываем введённый', () {
      expect(verificationEmail(const {}, 'typed@example.com'), 'typed@example.com');
      expect(verificationEmail(const {'email': ''}, 'typed@example.com'),
          'typed@example.com');
    });
  });

  group('AuthBloc: регистрация под гейтом', () {
    late _MockApi api;
    late _MockTokens tokens;

    setUp(() {
      api = _MockApi();
      tokens = _MockTokens();
      registerFallbackValue(<String, dynamic>{});
    });

    blocTest<AuthBloc, AuthState>(
      'ответ без токенов — состояние «ждём подтверждения», а не ошибка',
      build: () {
        when(() => api.post('/auth/email/register/', data: any(named: 'data')))
            .thenAnswer((_) async => _Resp(Map<String, dynamic>.from(_gateResponse)));
        return AuthBloc(apiClient: api, tokenStorage: tokens);
      },
      act: (bloc) => bloc.add(const AuthRegisterRequested(
        name: 'Новый',
        email: 'new@example.com',
        password: 'pass12345',
        password2: 'pass12345',
      )),
      expect: () => [
        const AuthLoading(),
        const AuthEmailVerificationPending('new@example.com'),
      ],
    );

    blocTest<AuthBloc, AuthState>(
      'токены под гейтом не сохраняем — сохранять нечего',
      build: () {
        when(() => api.post('/auth/email/register/', data: any(named: 'data')))
            .thenAnswer((_) async => _Resp(Map<String, dynamic>.from(_gateResponse)));
        return AuthBloc(apiClient: api, tokenStorage: tokens);
      },
      act: (bloc) => bloc.add(const AuthRegisterRequested(
        name: 'Новый',
        email: 'new@example.com',
        password: 'pass12345',
        password2: 'pass12345',
      )),
      verify: (_) {
        verifyNever(() => tokens.saveTokens(
            access: any(named: 'access'), refresh: any(named: 'refresh')));
        // и профиль не запрашиваем — запрос ушёл бы без авторизации
        verifyNever(() => api.get('/users/me/'));
      },
    );

    blocTest<AuthBloc, AuthState>(
      'гейт выключен — регистрация по-прежнему логинит',
      build: () {
        when(() => api.post('/auth/email/register/', data: any(named: 'data')))
            .thenAnswer((_) async => _Resp({'access': 'a.b.c', 'refresh': 'd.e.f'}));
        when(() => tokens.saveTokens(
            access: any(named: 'access'),
            refresh: any(named: 'refresh'))).thenAnswer((_) async {});
        when(() => api.get('/users/me/'))
            .thenAnswer((_) async => _Resp({'id': 1, 'name': 'Новый'}));
        return AuthBloc(apiClient: api, tokenStorage: tokens);
      },
      act: (bloc) => bloc.add(const AuthRegisterRequested(
        name: 'Новый',
        email: 'new@example.com',
        password: 'pass12345',
        password2: 'pass12345',
      )),
      expect: () => [const AuthLoading(), isA<AuthAuthenticated>()],
    );

    blocTest<AuthBloc, AuthState>(
      'вход с неподтверждённым адресом — то же состояние, что и регистрация',
      build: () {
        when(() => api.post('/auth/login/', data: any(named: 'data'))).thenThrow(
          const ApiException(
            message: 'Подтвердите e-mail по ссылке из письма.',
            statusCode: 403,
            errorCode: 'email_not_verified',
            body: {'code': 'email_not_verified', 'email': 'old@example.com'},
          ),
        );
        return AuthBloc(apiClient: api, tokenStorage: tokens);
      },
      act: (bloc) => bloc.add(
          const AuthLoginRequested(email: 'old@example.com', password: 'pass12345')),
      expect: () => [
        const AuthLoading(),
        const AuthEmailVerificationPending('old@example.com'),
      ],
    );

    blocTest<AuthBloc, AuthState>(
      'неверный пароль остаётся обычной ошибкой',
      build: () {
        when(() => api.post('/auth/login/', data: any(named: 'data'))).thenThrow(
          const ApiException(message: 'Неверные учётные данные.', statusCode: 400),
        );
        return AuthBloc(apiClient: api, tokenStorage: tokens);
      },
      act: (bloc) => bloc.add(
          const AuthLoginRequested(email: 'old@example.com', password: 'wrong')),
      expect: () => [const AuthLoading(), isA<AuthError>()],
    );
  });

  group('pendingVerificationEmail', () {
    test('адрес берём из тела ответа', () {
      const err = ApiException(
        message: 'x',
        statusCode: 403,
        errorCode: 'email_not_verified',
        body: {'email': 'from@body.ru'},
      );
      expect(pendingVerificationEmail(err, 'typed@example.com'), 'from@body.ru');
    });

    test('тела нет — показываем введённый адрес', () {
      const err = ApiException(
        message: 'x', statusCode: 403, errorCode: 'email_not_verified');
      expect(pendingVerificationEmail(err, 'typed@example.com'), 'typed@example.com');
    });

    test('прочие отказы сюда не попадают', () {
      expect(
        pendingVerificationEmail(
            const ApiException(message: 'x', statusCode: 400), 'a@b.c'),
        isNull,
      );
      expect(pendingVerificationEmail('не исключение вовсе', 'a@b.c'), isNull);
    });
  });

  group('Экран входа', () {
    Future<void> pump(WidgetTester tester, AuthBloc bloc, ApiClient api) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: BlocProvider<AuthBloc>.value(
          value: bloc,
          child: LoginScreen(apiClient: api),
        ),
      ));
      await tester.pump();
    }

    testWidgets('«подтвердите e-mail» показывается блоком с кнопкой отправки',
        (tester) async {
      final bloc = _MockAuthBloc();
      // Состояние, а не разовое событие: смена AuthState пересоздаёт роутер и
      // экран, так что панель обязана переживать собственную причину.
      whenListen(
        bloc,
        Stream<AuthState>.fromIterable(const [
          AuthLoading(),
          AuthEmailVerificationPending('old@example.com'),
        ]),
        initialState: const AuthUnauthenticated(),
      );

      await pump(tester, bloc, _MockApi());
      await tester.pump();

      expect(find.byType(VerifyEmailPanel), findsOneWidget);
      expect(find.text('Выслать письмо снова'), findsOneWidget);
      expect(find.textContaining('old@example.com'), findsOneWidget);
      // раньше здесь предлагали «написать в поддержку» — и всё
      expect(find.textContaining('поддержку'), findsNothing);
    });

    testWidgets('панель переживает пересоздание экрана', (tester) async {
      // Роутер пересоздаётся на каждой смене AuthState (main.dart) — экран
      // строится заново. Состояние в блоке остаётся, значит и панель тоже.
      final bloc = _MockAuthBloc();
      whenListen(
        bloc,
        const Stream<AuthState>.empty(),
        initialState: const AuthEmailVerificationPending('old@example.com'),
      );

      await pump(tester, bloc, _MockApi());
      await pump(tester, bloc, _MockApi()); // «новый» экран, тот же блок

      expect(find.byType(VerifyEmailPanel), findsOneWidget);
    });

    testWidgets('прочие отказы блок не показывают', (tester) async {
      final bloc = _MockAuthBloc();
      whenListen(
        bloc,
        Stream<AuthState>.fromIterable(const [
          AuthLoading(),
          AuthError('Неверный e-mail (телефон) или пароль.'),
        ]),
        initialState: const AuthUnauthenticated(),
      );

      await pump(tester, bloc, _MockApi());
      await tester.pump();

      expect(find.byType(VerifyEmailPanel), findsNothing);
      expect(find.text('Неверный e-mail (телефон) или пароль.'), findsOneWidget);
    });
  });

  group('Экран регистрации', () {
    Future<void> pump(WidgetTester tester, AuthBloc bloc) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: BlocProvider<AuthBloc>.value(
          value: bloc,
          child: RegisterScreen(apiClient: _MockApi()),
        ),
      ));
      await tester.pump();
    }

    testWidgets('под гейтом форма уступает место объяснению', (tester) async {
      final bloc = _MockAuthBloc();
      whenListen(
        bloc,
        const Stream<AuthState>.empty(),
        initialState: const AuthEmailVerificationPending('new@example.com'),
      );

      await pump(tester, bloc);

      expect(find.text('Аккаунт создан'), findsOneWidget);
      expect(find.byType(VerifyEmailPanel), findsOneWidget);
      // форму убрали: повторная отправка её же данных ничего не даст
      expect(find.text('Зарегистрироваться'), findsNothing);
    });

    testWidgets('без гейта видна обычная форма', (tester) async {
      final bloc = _MockAuthBloc();
      whenListen(
        bloc,
        const Stream<AuthState>.empty(),
        initialState: const AuthUnauthenticated(),
      );

      await pump(tester, bloc);

      expect(find.text('Зарегистрироваться'), findsOneWidget);
      expect(find.byType(VerifyEmailPanel), findsNothing);
    });
  });

  group('VerifyEmailPanel', () {
    Future<void> pump(WidgetTester tester, ApiClient api) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(
          body: VerifyEmailPanel(apiClient: api, email: 'new@example.com'),
        ),
      ));
    }

    testWidgets('кнопка шлёт письмо повторно и подтверждает это', (tester) async {
      final api = _MockApi();
      when(() => api.post('/auth/email/resend/', data: any(named: 'data')))
          .thenAnswer((_) async => _Resp({'detail': 'ok'}));

      await pump(tester, api);
      await tester.tap(find.text('Выслать письмо снова'));
      await tester.pump();
      await tester.pump();

      verify(() => api.post('/auth/email/resend/',
          data: {'email': 'new@example.com'})).called(1);
      expect(find.text('Письмо отправлено повторно.'), findsOneWidget);
    });

    testWidgets('без связи причина названа отдельно', (tester) async {
      final api = _MockApi();
      when(() => api.post('/auth/email/resend/', data: any(named: 'data')))
          // сетевая ошибка — это отсутствие statusCode (см. ApiException.isNetwork)
          .thenThrow(const ApiException(message: 'нет сети'));

      await pump(tester, api);
      await tester.tap(find.text('Выслать письмо снова'));
      await tester.pump();
      await tester.pump();

      expect(find.textContaining('Нет связи с сервером'), findsOneWidget);
    });

    testWidgets('адрес и подсказка про спам на виду', (tester) async {
      await pump(tester, _MockApi());

      expect(find.textContaining('new@example.com'), findsOneWidget);
      expect(find.textContaining('Спам'), findsOneWidget);
    });
  });
}
