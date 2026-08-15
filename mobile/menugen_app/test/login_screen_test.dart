// MG_LOGINFIX: экран входа должен объяснять отказ и показывать, с каким
// сервером работает сборка.
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/config/app_config.dart';
import 'package:menugen_app/core/deeplink/verified_notice_cubit.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/auth/bloc/auth_bloc.dart';
import 'package:menugen_app/features/auth/screens/login_screen.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

class _MockAuthBloc extends MockBloc<AuthEvent, AuthState> implements AuthBloc {}

// MG_EMAILVERIFY_MOBILE: экран сам переотправляет письмо подтверждения,
// поэтому ему нужен клиент.
class _MockApi extends Mock implements ApiClient {}

Future<void> _pump(WidgetTester tester, AuthBloc bloc) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: MultiBlocProvider(
      providers: [
        BlocProvider<AuthBloc>.value(value: bloc),
        // MG_VERIFYDEEPLINK: экран входа читает отметку о подтверждении
        BlocProvider<VerifiedNoticeCubit>(create: (_) => VerifiedNoticeCubit()),
      ],
      child: LoginScreen(apiClient: _MockApi()),
    ),
  ));
  await tester.pump();
}

void main() {
  testWidgets('видно, к какому серверу подключена сборка', (tester) async {
    final bloc = _MockAuthBloc();
    whenListen(bloc, const Stream<AuthState>.empty(), initialState: const AuthUnauthenticated());

    await _pump(tester, bloc);

    expect(find.text('сервер: ${AppConfig.apiHost}'), findsOneWidget);
  });

  testWidgets('причина отказа показывается человеческим текстом', (tester) async {
    final bloc = _MockAuthBloc();
    whenListen(
      bloc,
      Stream<AuthState>.fromIterable(const [
        AuthLoading(),
        AuthError('E-mail не подтверждён — вход закрыт.'),
      ]),
      initialState: const AuthUnauthenticated(),
    );

    await _pump(tester, bloc);
    await tester.pump();

    expect(find.text('E-mail не подтверждён — вход закрыт.'), findsOneWidget);
  });
}
