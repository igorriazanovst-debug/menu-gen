import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/api/token_storage.dart';
import 'package:menugen_app/features/auth/bloc/auth_bloc.dart';

class MockApiClient   extends Mock implements ApiClient {}
class MockTokenStorage extends Mock implements TokenStorage {}

void main() {
  late MockApiClient apiClient;
  late MockTokenStorage tokenStorage;

  setUp(() {
    apiClient    = MockApiClient();
    tokenStorage = MockTokenStorage();
  });

  group('AuthBloc', () {
    blocTest<AuthBloc, AuthState>(
      'emits [Loading, Unauthenticated] when no token',
      build: () {
        when(() => tokenStorage.hasToken()).thenAnswer((_) async => false);
        return AuthBloc(apiClient: apiClient, tokenStorage: tokenStorage);
      },
      act: (bloc) => bloc.add(const AuthCheckRequested()),
      expect: () => [const AuthLoading(), const AuthUnauthenticated()],
    );

    blocTest<AuthBloc, AuthState>(
      'emits [Loading, Authenticated] when token valid',
      build: () {
        when(() => tokenStorage.hasToken()).thenAnswer((_) async => true);
        when(() => apiClient.get('/users/me/')).thenAnswer((_) async =>
            MockResponse({'id': 1, 'name': 'Test', 'email': 'test@example.com'}));
        return AuthBloc(apiClient: apiClient, tokenStorage: tokenStorage);
      },
      act: (bloc) => bloc.add(const AuthCheckRequested()),
      expect: () => [
        const AuthLoading(),
        isA<AuthAuthenticated>(),
      ],
    );
  });
}

class MockResponse {
  final dynamic data;
  MockResponse(this.data);
}
