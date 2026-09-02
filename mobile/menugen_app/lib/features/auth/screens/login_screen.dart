import 'package:flutter/foundation.dart' show kDebugMode; // MG_LOGINFIX
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_svg/flutter_svg.dart'; // MG_APPICON
import 'package:go_router/go_router.dart';
import '../../../core/api/api_client.dart'; // MG_EMAILVERIFY_MOBILE
import '../../../core/config/app_config.dart'; // MG_LOGINFIX
import '../../../core/deeplink/verified_notice_cubit.dart'; // MG_VERIFYDEEPLINK
import '../../../core/theme/app_theme.dart'; // MG_SKIN
import '../../../core/widgets/phone_field.dart'; // MG_PHONECODE
import '../bloc/auth_bloc.dart';
import '../widgets/verify_email_panel.dart'; // MG_EMAILVERIFY_MOBILE

class LoginScreen extends StatefulWidget {
  final ApiClient apiClient;
  const LoginScreen({super.key, required this.apiClient});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  // MG_PHONECODE: поле не пустое, а с уже подставленным кодом страны.
  final _phone = TextEditingController(text: defaultPhoneCode);
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
      // MG_VERIFYDEEPLINK: пришли из браузера по menugen://verified — подставим
      // адрес, чтобы человек только ввёл пароль. Слушатель, а не поле в build:
      // перебивать уже набранный текст при каждой перерисовке нельзя.
      body: BlocListener<VerifiedNoticeCubit, String?>(
        listenWhen: (prev, curr) => curr != null && curr != prev,
        listener: (ctx, email) {
          if (email != null && email.isNotEmpty) {
            setState(() {
              _byPhone = false;
              _email.text = email;
            });
          }
        },
        child: BlocListener<AuthBloc, AuthState>(
        listener: (ctx, state) {
          // Вошли — отметка своё отработала и не должна всплыть при выходе.
          if (state is AuthAuthenticated) ctx.read<VerifiedNoticeCubit>().clear();
          if (state is AuthError) {
            // MG_LOGINFIX: причина отказа бывает длинной, за две секунды её не
            // прочитать.
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
              // MG_VERIFYDEEPLINK: подтверждение состоялось в браузере — здесь
              // об этом надо сказать, иначе непонятно, зачем нас вернули.
              BlocBuilder<VerifiedNoticeCubit, String?>(builder: (ctx, email) {
                if (email == null) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.check_circle_outline, size: 18, color: context.cs.primary),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text('E-mail подтверждён — введите пароль',
                          style: TextStyle(fontSize: 13, color: context.cs.primary)),
                    ),
                  ]),
                );
              }),
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
                // MG_PHONECODE: код страны выбирается, а не набирается вручную
                PhoneField(controller: _phone)
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
              // MG_EMAILVERIFY_MOBILE: адрес ждёт подтверждения — либо только
              // что зарегистрировались, либо вход отклонён по этой причине.
              //
              // Состояние берём у блока, а не из setState: смена AuthState
              // пересоздаёт роутер (main.dart), а с ним и этот экран — локальное
              // поле не пережило бы собственную причину появления.
              BlocBuilder<AuthBloc, AuthState>(builder: (ctx, state) {
                if (state is! AuthEmailVerificationPending) {
                  return const SizedBox.shrink();
                }
                return Padding(
                  padding: const EdgeInsets.only(top: 24),
                  child: VerifyEmailPanel(
                    apiClient: widget.apiClient,
                    email: state.email,
                    title: 'Подтвердите e-mail',
                  ),
                );
              }),
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
              // MG_PWDRESET: у телефонного аккаунта ссылка уходит в мессенджер,
              // где он подтверждал номер, — поэтому вкладку открываем сразу
              // нужную, чтобы человек не искал её сам.
              TextButton(
                onPressed: () => context.push(
                    _byPhone ? '/forgot-password?mode=phone' : '/forgot-password'),
                child: const Text('Забыли пароль?'),
              ),
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
      ),
    );
  }
}