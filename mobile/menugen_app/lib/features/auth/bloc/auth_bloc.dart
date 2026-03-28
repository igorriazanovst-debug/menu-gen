import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/token_storage.dart';

abstract class AuthEvent extends Equatable {
  const AuthEvent();
  @override List<Object?> get props => [];
}
class AuthCheckRequested extends AuthEvent { const AuthCheckRequested(); }
class AuthLoginRequested extends AuthEvent {
  final String email; final String password;
  const AuthLoginRequested({required this.email, required this.password});
  @override List<Object?> get props => [email, password];
}
class AuthLogoutRequested extends AuthEvent { const AuthLogoutRequested(); }

abstract class AuthState extends Equatable {
  const AuthState();
  @override List<Object?> get props => [];
}
class AuthLoading extends AuthState { const AuthLoading(); }
class AuthAuthenticated extends AuthState {
  final Map<String, dynamic> user;
  const AuthAuthenticated(this.user);
  @override List<Object?> get props => [user];
}
class AuthUnauthenticated extends AuthState { const AuthUnauthenticated(); }
class AuthError extends AuthState {
  final String message;
  const AuthError(this.message);
  @override List<Object?> get props => [message];
}

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final ApiClient apiClient;
  final TokenStorage tokenStorage;

  AuthBloc({required this.apiClient, required this.tokenStorage})
      : super(const AuthUnauthenticated()) {
    on<AuthCheckRequested>(_onCheck);
    on<AuthLoginRequested>(_onLogin);
    on<AuthLogoutRequested>(_onLogout);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onCheck(AuthCheckRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final hasToken = await tokenStorage.hasToken();
      if (!hasToken) { emit(const AuthUnauthenticated()); return; }
      final resp = await apiClient.get('/users/me/');
      emit(AuthAuthenticated(Map<String, dynamic>.from(_data(resp) as Map)));
    } catch (_) {
      await tokenStorage.clearTokens();
      emit(const AuthUnauthenticated());
    }
  }

  Future<void> _onLogin(AuthLoginRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final resp = await apiClient.post('/auth/login/',
          data: {'email': e.email, 'password': e.password});
      final data = Map<String, dynamic>.from(_data(resp) as Map);
      await tokenStorage.saveTokens(
          access: data['access'] as String, refresh: data['refresh'] as String);
      final me = await apiClient.get('/users/me/');
      emit(AuthAuthenticated(Map<String, dynamic>.from(_data(me) as Map)));
    } catch (e) { emit(AuthError(e.toString())); }
  }

  Future<void> _onLogout(AuthLogoutRequested e, Emitter<AuthState> emit) async {
    await tokenStorage.clearTokens();
    emit(const AuthUnauthenticated());
  }
}