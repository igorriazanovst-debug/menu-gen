import 'package:flutter/foundation.dart' show kDebugMode; // MG_LOGINFIX
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_svg/flutter_svg.dart'; // MG_APPICON
import 'package:go_router/go_router.dart';
import '../../../core/config/app_config.dart'; // MG_LOGINFIX
import '../../../core/theme/app_theme.dart'; // MG_SKIN
import '../bloc/auth_bloc.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _pass = TextEditingController();
  bool _obscure = true;
  // MG_PHONEVERIFY: вход по e-mail или по телефону — как на вебе.
  bool _byPhone = false;

  @override
  void dispose() { _email.dispose(); _phone.dispose(); _pass.dispose(); super.dispose(); }

  void _submit(BuildContext ctx) {
    ctx.read<AuthBloc>().add(_byPhone
        ? AuthLoginRequested(phone: _phone.text.trim(), password: _pass.text)
        : AuthLoginRequested(email: _email.text.trim(), password: _pass.text));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<AuthBloc, AuthState>(
        listener: (ctx, state) {
          if (state is AuthError) {
            // MG_LOGINFIX: причина отказа бывает длинной («подтвердите e-mail»),
            // за две секунды её не прочитать.
            ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
              content: Text(state.message),
              duration: const Duration(seconds: 6),
            ));
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
              // MG_APPICON: фирменный знак — тот же SVG, из которого собраны
              // иконки приложения и фавикон сайта.
              SvgPicture.asset('assets/images/logo.svg', height: 96),
              const SizedBox(height: 12),
              Text('MenuGen Platform',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: context.cs.primary)),
              const SizedBox(height: 48),
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('E-mail')),
                  ButtonSegment(value: true, label: Text('Телефон')),
                ],
                selected: {_byPhone},
                onSelectionChanged: (s) => setState(() => _byPhone = s.first),
              ),
              const SizedBox(height: 24),
              if (_byPhone)
                TextField(controller: _phone,
                  decoration: const InputDecoration(
                      labelText: 'Телефон',
                      hintText: '+7 900 000-00-00',
                      prefixIcon: Icon(Icons.phone_outlined)),
                  keyboardType: TextInputType.phone)
              else
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
                    onPressed: loading ? null : () => _submit(ctx),
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
              // MG_PHONEVERIFY: регистрация без e-mail — номер подтверждается
              // в Telegram или Max.
              TextButton(
                onPressed: () => context.push('/register/phone'),
                child: const Text('Регистрация по телефону'),
              ),
              // MG_LOGINFIX: какой сервер обслуживает эту сборку. Только в
              // отладочных сборках (их и раздаём вручную) — в релизе не нужно.
              if (kDebugMode) ...[
                const SizedBox(height: 8),
                Text('сервер: ${AppConfig.apiHost}',
                    style: TextStyle(fontSize: 11, color: context.cs.outline)),
              ],
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