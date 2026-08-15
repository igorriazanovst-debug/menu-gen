// MG_VERIFYDEEPLINK: после подтверждения в браузере человек возвращается в
// приложение по menugen://verified?email=…
//
// Раньше ссылка из письма оставляла его в мобильном вебе — при том что
// регистрировался он в приложении.
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/deeplink/verified_link.dart';
import 'package:menugen_app/core/deeplink/verified_notice_cubit.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/auth/bloc/auth_bloc.dart';
import 'package:menugen_app/features/auth/screens/login_screen.dart';

class _MockApi extends Mock implements ApiClient {}

class _MockAuthBloc extends MockBloc<AuthEvent, AuthState> implements AuthBloc {}

void main() {
  group('verifiedEmailFromLink', () {
    test('ссылка подтверждения отдаёт адрес', () {
      expect(
        verifiedEmailFromLink(Uri.parse('menugen://verified?email=a%40b.ru')),
        'a@b.ru',
      );
    });

    test('адрес не передали — это всё равно подтверждение', () {
      // Открыть приложение и показать отметку нужно и без адреса.
      expect(verifiedEmailFromLink(Uri.parse('menugen://verified')), '');
    });

    test('форма со слэшем тоже понимается', () {
      // Браузеры нормализуют такие ссылки по-разному.
      expect(
        verifiedEmailFromLink(Uri.parse('menugen:///verified?email=a%40b.ru')),
        'a@b.ru',
      );
    });

    test('чужая схема и чужая цель игнорируются', () {
      expect(verifiedEmailFromLink(Uri.parse('https://menugen.ru/verified')), isNull);
      expect(verifiedEmailFromLink(Uri.parse('menugen://paywall')), isNull);
      expect(verifiedEmailFromLink(null), isNull);
    });
  });

  group('VerifiedNoticeCubit', () {
    test('чужая ссылка состояние не трогает', () {
      final cubit = VerifiedNoticeCubit();
      cubit.handleLink(Uri.parse('menugen://something-else'));
      expect(cubit.state, isNull);
    });

    test('ссылка подтверждения запоминается, clear убирает', () {
      final cubit = VerifiedNoticeCubit();
      cubit.handleLink(Uri.parse('menugen://verified?email=a%40b.ru'));
      expect(cubit.state, 'a@b.ru');
      cubit.clear();
      expect(cubit.state, isNull);
    });
  });

  group('Экран входа после возврата из браузера', () {
    Future<void> pump(
      WidgetTester tester,
      AuthBloc auth,
      VerifiedNoticeCubit notice,
    ) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: MultiBlocProvider(
          providers: [
            BlocProvider<AuthBloc>.value(value: auth),
            BlocProvider<VerifiedNoticeCubit>.value(value: notice),
          ],
          child: LoginScreen(apiClient: _MockApi()),
        ),
      ));
      await tester.pump();
    }

    _MockAuthBloc idleAuth() {
      final bloc = _MockAuthBloc();
      whenListen(
        bloc,
        const Stream<AuthState>.empty(),
        initialState: const AuthUnauthenticated(),
      );
      return bloc;
    }

    testWidgets('отметка и подставленный адрес', (tester) async {
      final notice = VerifiedNoticeCubit();
      await pump(tester, idleAuth(), notice);

      notice.handleLink(Uri.parse('menugen://verified?email=new%40example.com'));
      await tester.pump(); // событие кубита доезжает микрозадачей
      await tester.pump();

      expect(find.text('E-mail подтверждён — введите пароль'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'new@example.com'), findsOneWidget);
    });

    testWidgets('без ссылки экран прежний', (tester) async {
      await pump(tester, idleAuth(), VerifiedNoticeCubit());

      expect(find.text('E-mail подтверждён — введите пароль'), findsNothing);
      expect(find.text('Войти'), findsOneWidget);
    });

    testWidgets('ссылка без адреса: отметка есть, поле не трогаем',
        (tester) async {
      final notice = VerifiedNoticeCubit();
      await pump(tester, idleAuth(), notice);

      notice.handleLink(Uri.parse('menugen://verified'));
      await tester.pump();
      await tester.pump();

      expect(find.text('E-mail подтверждён — введите пароль'), findsOneWidget);
    });

    testWidgets('вход гасит отметку — при выходе она не всплывёт',
        (tester) async {
      // Отметка уже стоит к моменту открытия экрана: подтвердили в браузере,
      // вернулись, ввели пароль.
      final notice = VerifiedNoticeCubit();
      notice.handleLink(Uri.parse('menugen://verified?email=a%40b.ru'));
      final auth = _MockAuthBloc();
      whenListen(
        auth,
        Stream<AuthState>.fromIterable([
          const AuthAuthenticated({'id': 1}),
        ]),
        initialState: const AuthUnauthenticated(),
      );

      await pump(tester, auth, notice);
      await tester.pump();

      expect(notice.state, isNull);
    });
  });
}
