import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/token_storage.dart';
import '../../../core/premium/premium_gate_cubit.dart';
import '../auth_error_text.dart'; // MG_LOGINFIX

abstract class AuthEvent extends Equatable {
  const AuthEvent();
  @override List<Object?> get props => [];
}
class AuthCheckRequested extends AuthEvent { const AuthCheckRequested(); }
/// Вход по e-mail либо по телефону (MG_PHONEVERIFY): бэкенд принимает любой из
/// двух идентификаторов, поэтому событие одно, а заполняется что-то одно.
class AuthLoginRequested extends AuthEvent {
  final String email; final String password; final String phone;
  const AuthLoginRequested({this.email = '', this.phone = '', required this.password});
  @override List<Object?> get props => [email, phone, password];
}
// MG_REG: регистрация (email). Бэкенд создаёт пользователя + семью + free-подписку.
class AuthRegisterRequested extends AuthEvent {
  final String name; final String email; final String password; final String password2;
  const AuthRegisterRequested({
    required this.name, required this.email, required this.password, required this.password2,
  });
  @override List<Object?> get props => [name, email, password, password2];
}
// MG_PHONEVERIFY: завершение регистрации по телефону. Номер уже подтверждён в
// мессенджере, заявка опознаётся по token — остаётся задать имя и пароль.
class AuthPhoneRegisterRequested extends AuthEvent {
  final String token; final String name; final String password; final String password2;
  const AuthPhoneRegisterRequested({
    required this.token, required this.name, required this.password, required this.password2,
  });
  @override List<Object?> get props => [token, name, password, password2];
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
  // MG-profile-premium: seed proactive premium status from /users/me/.
  final PremiumGateCubit? premiumGate;

  AuthBloc({
    required this.apiClient,
    required this.tokenStorage,
    this.premiumGate,
  })
      : super(const AuthUnauthenticated()) {
    on<AuthCheckRequested>(_onCheck);
    on<AuthLoginRequested>(_onLogin);
    on<AuthRegisterRequested>(_onRegister);
    on<AuthPhoneRegisterRequested>(_onPhoneRegister); // MG_PHONEVERIFY
    on<AuthLogoutRequested>(_onLogout);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onCheck(AuthCheckRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final hasToken = await tokenStorage.hasToken();
      if (!hasToken) { emit(const AuthUnauthenticated()); return; }
      final resp = await apiClient.get('/users/me/');
      final me = Map<String, dynamic>.from(_data(resp) as Map);
      premiumGate?.bootstrap(me);
      emit(AuthAuthenticated(me));
    } catch (_) {
      await tokenStorage.clearTokens();
      emit(const AuthUnauthenticated());
    }
  }

  Future<void> _onLogin(AuthLoginRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      // Отправляем ровно один идентификатор: пустой email бэкенд отклонит как
      // некорректный, а не проигнорирует.
      final resp = await apiClient.post('/auth/login/',
          data: e.phone.isNotEmpty
              ? {'phone': e.phone, 'password': e.password}
              : {'email': e.email, 'password': e.password});
      final data = Map<String, dynamic>.from(_data(resp) as Map);
      await tokenStorage.saveTokens(
          access: data['access'] as String, refresh: data['refresh'] as String);
      final me = await apiClient.get('/users/me/');
      final meMap = Map<String, dynamic>.from(_data(me) as Map);
      premiumGate?.bootstrap(meMap);
      emit(AuthAuthenticated(meMap));
    } catch (e) { emit(AuthError(authErrorText(e))); }
  }

  Future<void> _onRegister(AuthRegisterRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final resp = await apiClient.post('/auth/email/register/', data: {
        'name': e.name,
        'email': e.email,
        'password': e.password,
        'password2': e.password2,
      });
      final data = Map<String, dynamic>.from(_data(resp) as Map);
      await tokenStorage.saveTokens(
          access: data['access'] as String, refresh: data['refresh'] as String);
      final me = await apiClient.get('/users/me/');
      final meMap = Map<String, dynamic>.from(_data(me) as Map);
      premiumGate?.bootstrap(meMap);
      emit(AuthAuthenticated(meMap));
    } catch (e) {
      emit(AuthError(authErrorText(e)));
    }
  }

  // MG_PHONEVERIFY: номер уже подтверждён ботом, здесь создаётся аккаунт.
  Future<void> _onPhoneRegister(AuthPhoneRegisterRequested e, Emitter<AuthState> emit) async {
    emit(const AuthLoading());
    try {
      final resp = await apiClient.post('/auth/phone/register/', data: {
        'token': e.token,
        'name': e.name,
        'password': e.password,
        'password2': e.password2,
      });
      final data = Map<String, dynamic>.from(_data(resp) as Map);
      await tokenStorage.saveTokens(
          access: data['access'] as String, refresh: data['refresh'] as String);
      final me = await apiClient.get('/users/me/');
      final meMap = Map<String, dynamic>.from(_data(me) as Map);
      premiumGate?.bootstrap(meMap);
      emit(AuthAuthenticated(meMap));
    } catch (e) {
      emit(AuthError(authErrorText(e)));
    }
  }

  Future<void> _onLogout(AuthLogoutRequested e, Emitter<AuthState> emit) async {
    await tokenStorage.clearTokens();
    premiumGate?.reset();
    emit(const AuthUnauthenticated());
  }
}