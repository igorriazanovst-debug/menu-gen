part of 'auth_bloc.dart';

abstract class AuthState extends Equatable {
  const AuthState();
  @override
  List<Object?> get props => [];
}

class AuthInitial         extends AuthState { const AuthInitial(); }
class AuthLoading         extends AuthState { const AuthLoading(); }
class AuthUnauthenticated extends AuthState { const AuthUnauthenticated(); }
class AuthAuthenticated   extends AuthState {
  final dynamic user;
  const AuthAuthenticated({required this.user});
  @override
  List<Object?> get props => [user];
}
class AuthError extends AuthState {
  final String message;
  const AuthError({required this.message});
  @override
  List<Object?> get props => [message];
}
