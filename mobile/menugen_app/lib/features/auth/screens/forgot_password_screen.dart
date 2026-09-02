// MG_PWDRESET: «забыли пароль» — запрос письма со ссылкой.
//
// Экран только просит письмо. Новый пароль задаётся на странице сайта, куда
// ведёт ссылка из письма, — как и подтверждение удаления аккаунта. Так сделано
// не из лени: чтобы задать пароль в приложении, пришлось бы просить человека
// перенести из письма длинный токен руками, а ссылка открывается пальцем.
//
// Ответ сервера одинаков для существующего и несуществующего адреса, поэтому и
// экран показывает одно и то же: иначе форма стала бы способом проверять, кто у
// нас зарегистрирован.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';

class ForgotPasswordScreen extends StatefulWidget {
  final ApiClient apiClient;
  const ForgotPasswordScreen({super.key, required this.apiClient});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _email = TextEditingController();
  bool _sending = false;
  bool _sent = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _email.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Введите адрес, на который зарегистрирован аккаунт.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await widget.apiClient.post('/auth/password-reset/request/', data: {'email': email});
      if (!mounted) return;
      setState(() => _sent = true);
    } catch (e) {
      if (!mounted) return;
      // Сетевую ошибку показываем — это не разглашение: она случается и с
      // несуществующим адресом. Скрывать надо ответ сервера, а не отсутствие
      // связи, иначе человек будет ждать письмо, которого никто не отправлял.
      setState(() => _error = e is ApiException && e.isNetwork
          ? 'Нет связи с сервером. Проверьте интернет и попробуйте снова.'
          : 'Не удалось отправить письмо. Попробуйте позже.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Восстановление пароля')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: _sent ? _sentBlock(context) : _formBlock(context),
        ),
      ),
    );
  }

  Widget _formBlock(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Укажите адрес, на который зарегистрирован аккаунт. Пришлём письмо '
            'со ссылкой — по ней можно будет задать новый пароль.',
            style: TextStyle(fontSize: 15),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Email',
              prefixIcon: Icon(Icons.email_outlined),
            ),
            onSubmitted: (_) => _submit(),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: TextStyle(color: context.cs.error, fontSize: 13)),
          ],
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _sending ? null : _submit,
            child: _sending
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Прислать ссылку'),
          ),
        ],
      );

  Widget _sentBlock(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Icon(Icons.mark_email_read_outlined, size: 56, color: context.cs.primary),
          const SizedBox(height: 16),
          const Text('Письмо отправлено',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Text(
            'Если аккаунт с адресом ${_email.text.trim()} существует, мы отправили на него '
            'ссылку для смены пароля. Ссылка действует 2 часа.',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 15),
          ),
          const SizedBox(height: 12),
          Text(
            'Письма нет? Проверьте папку «Спам» и убедитесь, что адрес тот же, '
            'с которым вы регистрировались.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: context.cs.outline),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Вернуться ко входу'),
          ),
          TextButton(
            onPressed: () => setState(() => _sent = false),
            child: const Text('Ввести другой адрес'),
          ),
        ],
      );
}
