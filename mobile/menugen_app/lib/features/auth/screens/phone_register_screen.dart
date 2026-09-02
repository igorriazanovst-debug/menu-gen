// MG_PHONEVERIFY: регистрация по номеру телефона с подтверждением в мессенджере.
//
// Шаги: (1) номер + мессенджер — создаём заявку; (2) пользователь открывает бота
// по deep-link и делится контактом, приложение опрашивает статус; (3) имя и
// пароль — аккаунт создан, вход выполнен.
//
// Подтверждение разовое: дальше вход по телефону и паролю на экране входа.
// Бот сверяет номер, введённый здесь, с номером из мессенджера — если они
// разные, приходит статус mismatch (номер чужой либо в мессенджере другой).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/phone_field.dart'; // MG_PHONECODE
import '../bloc/auth_bloc.dart';

/// Пауза между опросами статуса. Тот же интервал, что в вебе.
const _pollInterval = Duration(seconds: 3);

enum _Step { phone, confirm, finish }

class PhoneRegisterScreen extends StatefulWidget {
  final ApiClient apiClient;

  const PhoneRegisterScreen({super.key, required this.apiClient});

  @override
  State<PhoneRegisterScreen> createState() => _PhoneRegisterScreenState();
}

class _PhoneRegisterScreenState extends State<PhoneRegisterScreen> {
  // MG_PHONECODE: поле не пустое, а с уже подставленным кодом страны.
  final _phone = TextEditingController(text: defaultPhoneCode);
  final _name = TextEditingController();
  final _pass = TextEditingController();
  final _pass2 = TextEditingController();

  _Step _step = _Step.phone;
  String _provider = 'telegram';
  bool _starting = false;
  String? _error;

  String? _token;
  String? _deepLink;
  String _status = 'pending';
  String? _messengerPhone;
  Timer? _poll;

  @override
  void dispose() {
    _poll?.cancel();
    _phone.dispose();
    _name.dispose();
    _pass.dispose();
    _pass2.dispose();
    super.dispose();
  }

  // ── шаг 1: заявка ────────────────────────────────────────────────────────
  Future<void> _start() async {
    final digits = _phone.text.replaceAll(RegExp(r'\D'), '');
    if (digits.length < 10) {
      setState(() => _error = 'Введите корректный номер телефона.');
      return;
    }
    setState(() {
      _starting = true;
      _error = null;
    });
    try {
      final resp = await widget.apiClient.post('/auth/phone/start/',
          data: {'phone': _phone.text.trim(), 'provider': _provider});
      final data = Map<String, dynamic>.from(resp as Map);
      if (!mounted) return;
      setState(() {
        _token = data['token'] as String?;
        _deepLink = data['deep_link'] as String?;
        _status = 'pending';
        _step = _Step.confirm;
      });
      _startPolling();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = _startError(e));
    } finally {
      if (mounted) setState(() => _starting = false);
    }
  }

  /// Коды ошибок бэкенда → понятный текст.
  String _startError(Object e) {
    final text = e.toString();
    if (text.contains('phone_taken')) {
      return 'Аккаунт с таким телефоном уже есть. Войдите по паролю.';
    }
    if (text.contains('provider_unavailable')) {
      return 'Подтверждение через этот мессенджер пока недоступно.';
    }
    return 'Не удалось начать подтверждение. Попробуйте позже.';
  }

  // ── шаг 2: опрос статуса ─────────────────────────────────────────────────
  void _startPolling() {
    _poll?.cancel();
    _poll = Timer.periodic(_pollInterval, (_) => _checkStatus());
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    final token = _token;
    if (token == null) return;
    try {
      final resp = await widget.apiClient.get('/auth/phone/status/', params: {'token': token});
      final data = Map<String, dynamic>.from(resp as Map);
      if (!mounted) return;
      setState(() {
        _status = (data['status'] as String?) ?? 'pending';
        _messengerPhone = data['messenger_phone'] as String?;
      });
      if (_status == 'verified') {
        _poll?.cancel();
        setState(() => _step = _Step.finish);
      } else if (_status == 'expired') {
        _poll?.cancel();
      }
    } catch (_) {
      // Сеть моргнула — попробуем на следующем тике, статус не трогаем.
    }
  }

  // MG_TGLINK: открыть бота.
  //
  // Раньше здесь стоял `if (await canLaunchUrl(uri))` — и на Android 11+ он
  // отвечал «нельзя» просто потому, что приложение не видит установленные
  // мессенджеры без <queries> в манифесте. Ссылка при этом рабочая. Поэтому
  // теперь пробуем открыть, а не спрашиваем разрешения: сначала во внешнем
  // приложении (Telegram перехватит t.me сам), затем — обычным способом, если
  // внешнего обработчика не нашлось.
  //
  // Если не вышло и так, ссылку даём скопировать: подтверждение упирается в
  // один переход, и упереться в него насмерть нельзя.
  Future<void> _openMessenger() async {
    final link = _deepLink;
    if (link == null) return;
    final uri = Uri.parse(link);
    for (final mode in [LaunchMode.externalApplication, LaunchMode.platformDefault]) {
      try {
        if (await launchUrl(uri, mode: mode)) return;
      } catch (_) {
        // Обработчика для этого режима нет — пробуем следующий.
      }
    }
    if (!mounted) return;
    setState(() => _error = 'Не удалось открыть мессенджер — скопируйте ссылку и '
        'откройте её вручную.');
  }

  Future<void> _copyLink() async {
    final link = _deepLink;
    if (link == null) return;
    await Clipboard.setData(ClipboardData(text: link));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Ссылка скопирована')),
    );
  }

  void _restart() {
    _poll?.cancel();
    setState(() {
      _step = _Step.phone;
      _token = null;
      _deepLink = null;
      _status = 'pending';
      _messengerPhone = null;
      _error = null;
    });
  }

  // ── шаг 3: имя и пароль ──────────────────────────────────────────────────
  void _finish() {
    if (_name.text.trim().isEmpty) {
      setState(() => _error = 'Введите имя.');
      return;
    }
    if (_pass.text.length < 8) {
      setState(() => _error = 'Пароль должен быть не короче 8 символов.');
      return;
    }
    if (_pass.text != _pass2.text) {
      setState(() => _error = 'Пароли не совпадают.');
      return;
    }
    setState(() => _error = null);
    context.read<AuthBloc>().add(AuthPhoneRegisterRequested(
          token: _token!,
          name: _name.text.trim(),
          password: _pass.text,
          password2: _pass2.text,
        ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Регистрация по телефону')),
      body: BlocListener<AuthBloc, AuthState>(
        listener: (context, state) {
          if (state is AuthError) setState(() => _error = state.message);
        },
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              _StepHeader(step: _step),
              const SizedBox(height: 24),
              if (_step == _Step.phone) ..._phoneStep(),
              if (_step == _Step.confirm) ..._confirmStep(),
              if (_step == _Step.finish) ..._finishStep(),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _phoneStep() => [
        // MG_PHONECODE: код страны выбирается, а не набирается вручную
        PhoneField(
          controller: _phone,
          label: 'Номер телефона',
          helperText: 'Номер, привязанный к вашему мессенджеру',
        ),
        const SizedBox(height: 16),
        const Text('Где подтвердить номер', style: TextStyle(fontSize: 13, color: Colors.grey)),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'telegram', label: Text('Telegram')),
            ButtonSegment(value: 'max', label: Text('Max')),
          ],
          selected: {_provider},
          onSelectionChanged: (s) => setState(() => _provider = s.first),
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: _starting ? null : _start,
            child: _starting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Продолжить'),
          ),
        ),
      ];

  List<Widget> _confirmStep() {
    final expired = _status == 'expired';
    final mismatch = _status == 'mismatch';
    return [
      Text(
        'Откройте бота и нажмите «Поделиться номером». Мы сверим его с тем, '
        'что вы ввели — это подтвердит, что номер ваш.',
        style: TextStyle(color: Colors.grey.shade700),
      ),
      const SizedBox(height: 20),
      SizedBox(
        width: double.infinity,
        child: FilledButton.icon(
          onPressed: expired ? null : _openMessenger,
          icon: const Icon(Icons.open_in_new),
          label: Text(_provider == 'telegram' ? 'Открыть Telegram' : 'Открыть Max'),
        ),
      ),
      // MG_TGLINK: запасной путь, если переход не сработал.
      TextButton.icon(
        onPressed: expired ? null : _copyLink,
        icon: const Icon(Icons.copy, size: 18),
        label: const Text('Скопировать ссылку'),
      ),
      const SizedBox(height: 16),
      if (mismatch)
        _Note(
          color: Colors.orange,
          text: _messengerPhone == null || _messengerPhone!.isEmpty
              ? 'Номер в мессенджере не совпал с введённым.'
              : 'Номер в мессенджере ($_messengerPhone) не совпал с введённым.',
        )
      else if (expired)
        const _Note(color: Colors.red, text: 'Время подтверждения истекло.')
      else
        const Row(
          children: [
            SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
            SizedBox(width: 12),
            Expanded(child: Text('Ждём подтверждения…', style: TextStyle(color: Colors.grey))),
          ],
        ),
      const SizedBox(height: 16),
      TextButton(onPressed: _restart, child: const Text('Изменить номер')),
    ];
  }

  List<Widget> _finishStep() => [
        const _Note(color: Colors.green, text: 'Номер подтверждён.'),
        const SizedBox(height: 20),
        TextField(
          controller: _name,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Имя', prefixIcon: Icon(Icons.person_outline)),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _pass,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Пароль', prefixIcon: Icon(Icons.lock_outline)),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _pass2,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Повторите пароль', prefixIcon: Icon(Icons.lock_outline)),
        ),
        const SizedBox(height: 24),
        BlocBuilder<AuthBloc, AuthState>(
          builder: (context, state) {
            final loading = state is AuthLoading;
            return SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: loading ? null : _finish,
                child: loading
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Создать аккаунт'),
              ),
            );
          },
        ),
      ];
}

class _StepHeader extends StatelessWidget {
  final _Step step;

  const _StepHeader({required this.step});

  @override
  Widget build(BuildContext context) {
    const titles = ['Номер телефона', 'Подтверждение', 'Аккаунт'];
    final index = _Step.values.indexOf(step);
    return Row(
      children: [
        for (var i = 0; i < titles.length; i++) ...[
          if (i > 0) const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  height: 4,
                  decoration: BoxDecoration(
                    color: i <= index ? context.cs.primary : Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  titles[i],
                  style: TextStyle(
                    fontSize: 11,
                    color: i <= index ? context.cs.primary : Colors.grey,
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _Note extends StatelessWidget {
  final Color color;
  final String text;

  const _Note({required this.color, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text, style: TextStyle(color: color, fontSize: 13)),
    );
  }
}
