import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart'; // MG_SKIN
import '../bloc/auth_bloc.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _pass = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() { _email.dispose(); _pass.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<AuthBloc, AuthState>(
        listener: (ctx, state) {
          if (state is AuthError) {
            ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(state.message)));
          }
        },
        child: SafeArea(
          child: LayoutBuilder(
            builder: (ctx, constraints) => SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              // MG_SKIN: слот логотипа (заменить на AppLogo, когда придёт ассет:
              // logo_mark ~72px высотой, цветной на светлом фоне).
              Icon(Icons.restaurant_menu, size: 72, color: context.cs.primary),
              const SizedBox(height: 8),
              Text('MenuGen', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: context.cs.primary)),
              const SizedBox(height: 48),
              TextField(controller: _email,
                decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.email_outlined)),
                keyboardType: TextInputType.emailAddress),
              const SizedBox(height: 16),
              TextField(controller: _pass, obscureText: _obscure,
                decoration: InputDecoration(
                  labelText: 'Пароль',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                )),
              const SizedBox(height: 32),
              BlocBuilder<AuthBloc, AuthState>(builder: (ctx, state) {
                final loading = state is AuthLoading;
                return SizedBox(width: double.infinity,
                  child: ElevatedButton(
                    onPressed: loading ? null : () => ctx.read<AuthBloc>().add(
                      AuthLoginRequested(email: _email.text.trim(), password: _pass.text)),
                    child: loading
                        ? const SizedBox(height: 20, width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Text('Войти'),
                  ),
                );
              }),
              const SizedBox(height: 12),
              TextButton(
                onPressed: () => context.push('/register'),
                child: const Text('Нет аккаунта? Зарегистрироваться'),
              ),
                  ]),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}