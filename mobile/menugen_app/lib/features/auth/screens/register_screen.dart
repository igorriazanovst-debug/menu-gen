// MG_REG: экран регистрации. Бэкенд создаёт пользователя + семью + бесплатную
// подписку.
//
// MG_EMAILVERIFY_MOBILE: входом это заканчивается не всегда. При включённом
// подтверждении e-mail токенов в ответе нет — вместо перехода на главную
// показываем, что письмо ушло, и даём выслать его повторно.
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../bloc/auth_bloc.dart';
import '../widgets/verify_email_panel.dart';

class RegisterScreen extends StatefulWidget {
  final ApiClient apiClient;
  const RegisterScreen({super.key, required this.apiClient});
  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _pass = TextEditingController();
  final _pass2 = TextEditingController();
  bool _obscure = true;
  String? _localError;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _pass.dispose();
    _pass2.dispose();
    super.dispose();
  }

  void _submit() {
    final name = _name.text.trim();
    final email = _email.text.trim();
    final p1 = _pass.text;
    final p2 = _pass2.text;
    if (name.isEmpty || email.isEmpty) {
      setState(() => _localError = 'Заполните имя и email.');
      return;
    }
    if (p1.length < 5) {
      setState(() => _localError = 'Пароль — минимум 5 символов.');
      return;
    }
    if (p1 != p2) {
      setState(() => _localError = 'Пароли не совпадают.');
      return;
    }
    setState(() => _localError = null);
    context.read<AuthBloc>().add(AuthRegisterRequested(
          name: name,
          email: email,
          password: p1,
          password2: p2,
        ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Регистрация')),
      body: BlocListener<AuthBloc, AuthState>(
        listener: (ctx, state) {
          if (state is AuthError) {
            ScaffoldMessenger.of(ctx)
                .showSnackBar(SnackBar(content: Text(state.message)));
          }
          if (state is AuthAuthenticated) {
            // Успех — уходим на главную (редирект роутера тоже сработает).
            ctx.go('/');
          }
        },
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: BlocBuilder<AuthBloc, AuthState>(builder: (ctx, state) {
              // MG_EMAILVERIFY_MOBILE: аккаунт создан, но вход закрыт до
              // перехода по ссылке — форма уступает место объяснению.
              if (state is AuthEmailVerificationPending) {
                return _sentPanel(context, state.email);
              }
              return Column(children: [
              Icon(Icons.restaurant_menu, size: 56, color: context.cs.primary),
              const SizedBox(height: 24),
              TextField(
                controller: _name,
                decoration: const InputDecoration(
                    labelText: 'Имя', prefixIcon: Icon(Icons.person_outline)),
                textCapitalization: TextCapitalization.words,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _email,
                decoration: const InputDecoration(
                    labelText: 'Email', prefixIcon: Icon(Icons.email_outlined)),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _pass,
                obscureText: _obscure,
                decoration: InputDecoration(
                  labelText: 'Пароль',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _pass2,
                obscureText: _obscure,
                decoration: const InputDecoration(
                    labelText: 'Повторите пароль',
                    prefixIcon: Icon(Icons.lock_outline)),
              ),
              if (_localError != null) ...[
                const SizedBox(height: 12),
                Text(_localError!,
                    style: const TextStyle(color: Colors.red, fontSize: 13)),
              ],
              const SizedBox(height: 28),
              BlocBuilder<AuthBloc, AuthState>(builder: (ctx, state) {
                final loading = state is AuthLoading;
                return SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: loading ? null : _submit,
                    child: loading
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white))
                        : const Text('Зарегистрироваться'),
                  ),
                );
              }),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => context.pop(),
                child: const Text('Уже есть аккаунт? Войти'),
              ),
            ]);
            }),
          ),
        ),
      ),
    );
  }

  // MG_EMAILVERIFY_MOBILE: что видит человек вместо входа.
  Widget _sentPanel(BuildContext context, String email) {
    return Column(children: [
      Icon(Icons.mark_email_read_outlined, size: 56, color: context.cs.primary),
      const SizedBox(height: 16),
      const Text('Аккаунт создан',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      const SizedBox(height: 16),
      VerifyEmailPanel(
        apiClient: widget.apiClient,
        email: email,
        title: 'Остался один шаг',
      ),
      const SizedBox(height: 12),
      TextButton(
        onPressed: () => context.pop(),
        child: const Text('Перейти ко входу'),
      ),
    ]);
  }
}
