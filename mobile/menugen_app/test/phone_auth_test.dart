// MG_PHONEVERIFY: вход по телефону и регистрация после подтверждения в мессенджере.
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/token_storage.dart';
import 'package:menugen_app/features/auth/bloc/auth_bloc.dart';

class _MockApi extends Mock implements ApiClient {}

class _MockTokens extends Mock implements TokenStorage {}

const _me = {'id': 7, 'name': 'Пётр', 'phone': '+79000000000'};
const _tokens = {'access': 'a', 'refresh': 'r'};

void main() {
  late _MockApi api;
  late _MockTokens tokens;

  setUp(() {
    api = _MockApi();
    tokens = _MockTokens();
    when(() => tokens.saveTokens(access: any(named: 'access'), refresh: any(named: 'refresh')))
        .thenAnswer((_) async {});
    when(() => api.get('/users/me/')).thenAnswer((_) async => Map<String, dynamic>.from(_me));
  });

  group('вход', () {
    blocTest<AuthBloc, AuthState>(
      'по телефону уходит поле phone, а не пустой email',
      setUp: () {
        when(() => api.post('/auth/login/', data: any(named: 'data')))
            .thenAnswer((_) async => Map<String, dynamic>.from(_tokens));
      },
      build: () => AuthBloc(apiClient: api, tokenStorage: tokens),
      act: (b) => b.add(const AuthLoginRequested(phone: '+7 900 000-00-00', password: 'secret12')),
      wait: const Duration(milliseconds: 50),
      verify: (_) {
        final captured = verify(() => api.post('/auth/login/', data: captureAny(named: 'data')))
            .captured
            .single as Map;
        expect(captured['phone'], '+7 900 000-00-00');
        expect(captured.containsKey('email'), isFalse);
      },
    );

    blocTest<AuthBloc, AuthState>(
      'по e-mail поле phone не отправляется',
      setUp: () {
        when(() => api.post('/auth/login/', data: any(named: 'data')))
            .thenAnswer((_) async => Map<String, dynamic>.from(_tokens));
      },
      build: () => AuthBloc(apiClient: api, tokenStorage: tokens),
      act: (b) => b.add(const AuthLoginRequested(email: 'a@b.ru', password: 'secret12')),
      wait: const Duration(milliseconds: 50),
      verify: (_) {
        final captured = verify(() => api.post('/auth/login/', data: captureAny(named: 'data')))
            .captured
            .single as Map;
        expect(captured['email'], 'a@b.ru');
        expect(captured.containsKey('phone'), isFalse);
      },
    );
  });

  group('регистрация по телефону', () {
    blocTest<AuthBloc, AuthState>(
      'сохраняет токены и поднимает сессию',
      setUp: () {
        when(() => api.post('/auth/phone/register/', data: any(named: 'data')))
            .thenAnswer((_) async => Map<String, dynamic>.from(_tokens));
      },
      build: () => AuthBloc(apiClient: api, tokenStorage: tokens),
      act: (b) => b.add(const AuthPhoneRegisterRequested(
        token: 'tok-1',
        name: 'Пётр',
        password: 'secret12',
        password2: 'secret12',
      )),
      wait: const Duration(milliseconds: 50),
      expect: () => [
        isA<AuthLoading>(),
        isA<AuthAuthenticated>().having((s) => s.user['name'], 'name', 'Пётр'),
      ],
      verify: (_) {
        verify(() => tokens.saveTokens(access: 'a', refresh: 'r')).called(1);
        final captured = verify(() => api.post('/auth/phone/register/', data: captureAny(named: 'data')))
            .captured
            .single as Map;
        expect(captured['token'], 'tok-1');
        expect(captured['password2'], 'secret12');
      },
    );

    blocTest<AuthBloc, AuthState>(
      'ошибка бэкенда не оставляет пользователя залогиненным',
      setUp: () {
        when(() => api.post('/auth/phone/register/', data: any(named: 'data')))
            .thenThrow(Exception('not_verified'));
      },
      build: () => AuthBloc(apiClient: api, tokenStorage: tokens),
      act: (b) => b.add(const AuthPhoneRegisterRequested(
        token: 'tok-1',
        name: 'Пётр',
        password: 'secret12',
        password2: 'secret12',
      )),
      wait: const Duration(milliseconds: 50),
      expect: () => [isA<AuthLoading>(), isA<AuthError>()],
      verify: (_) {
        verifyNever(() => tokens.saveTokens(access: any(named: 'access'), refresh: any(named: 'refresh')));
      },
    );
  });
}
