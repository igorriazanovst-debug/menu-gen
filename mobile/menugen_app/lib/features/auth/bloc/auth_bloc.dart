import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/api/token_storage.dart';

part 'auth_event.dart';
part 'auth_state.dart';

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final ApiClient apiClient;
  final TokenStorage tokenStorage;

  AuthBloc({required this.apiClient, required this.tokenStorage})
      : super(const AuthInitial()) {
    on<AuthCheckRequested>(_onCheck);
    on<AuthLoginRequested>(_onLogin);
    on<AuthLogoutRequested>(_onLogout);
  }

  Future<void> _onCheck(AuthCheckRequested event, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    final hasToken = await tokenStorage.hasToken();
    if (hasToken) {
      try {
        final resp = await apiClient.get('/users/me/');
        emit(AuthAuthenticated(user: resp.data));
      } catch (_) {
        await tokenStorage.clearTokens();
        emit(const AuthUnauthenticated());
      }
    } else {
      emit(const AuthUnauthenticated());
    }
  }

  Future<void> _onLogin(AuthLoginRequested event, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final resp = await apiClient.post('/auth/login/', data: {
        'email': event.email,
        'password': event.password,
      });
      await tokenStorage.saveTokens(
        access: resp.data['access'],
        refresh: resp.data['refresh'],
      );
      final me = await apiClient.get('/users/me/');
      emit(AuthAuthenticated(user: me.data));
    } catch (e) {
      emit(AuthError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onLogout(AuthLogoutRequested event, Emitter<AuthState> emit) async {
    try {
      final refresh = await tokenStorage.getRefreshToken();
      await apiClient.post('/auth/logout/', data: {'refresh': refresh});
    } finally {
      await tokenStorage.clearTokens();
      emit(const AuthUnauthenticated());
    }
  }
}
