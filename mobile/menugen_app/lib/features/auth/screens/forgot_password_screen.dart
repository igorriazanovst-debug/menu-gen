// MG_PWDRESET: «забыли пароль» — запрос ссылки на смену.
//
// Два способа, потому что аккаунты бывают двух видов. Зарегистрированному по
// e-mail ссылка уходит письмом. Зарегистрированному по телефону письмо слать
// некуда — адреса у него может не быть вовсе, — поэтому ссылка уходит в тот
// мессенджер, где он подтверждал номер при регистрации. Отдельного
// доказательства владения для этого не понадобилось: диалог с ботом, в котором
// человек делился контактом, и есть доказательство.
//
// Экран только просит ссылку. Новый пароль задаётся на странице сайта, как и
// подтверждение удаления аккаунта. Так сделано не из лени: чтобы задать пароль
// в приложении, пришлось бы просить человека перенести из письма длинный токен
// руками, а ссылка открывается пальцем.
//
// Ответ сервера одинаков для существующего и несуществующего адреса (номера),
// поэтому и экран показывает одно и то же: иначе форма стала бы способом
// проверять, кто у нас зарегистрирован.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/phone_field.dart'; // MG_PHONECODE

class ForgotPasswordScreen extends StatefulWidget {
  final ApiClient apiClient;

  /// С экрана входа приходим уже в нужной вкладке: тот, кто вводил телефон,
  /// ищет восстановление по телефону, а не по адресу.
  final bool byPhone;

  const ForgotPasswordScreen({super.key, required this.apiClient, this.byPhone = false});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _email = TextEditingController();
  final _phone = TextEditingController(text: defaultPhoneCode);
  late bool _byPhone = widget.byPhone;
  bool _sending = false;
  bool _sent = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _email.text.trim();
    final phone = _phone.text.trim();
    if (_byPhone) {
      if (phone.replaceAll(RegExp(r'\D'), '').length < 10) {
        setState(() => _error = 'Введите номер, на который зарегистрирован аккаунт.');
        return;
      }
    } else if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Введите адрес, на который зарегистрирован аккаунт.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await widget.apiClient.post('/auth/password-reset/request/',
          data: _byPhone ? {'phone': phone} : {'email': email});
      if (!mounted) return;
      setState(() => _sent = true);
    } catch (e) {
      if (!mounted) return;
      // Сетевую ошибку показываем — это не разглашение: она случается и с
      // несуществующим адресом. Скрывать надо ответ сервера, а не отсутствие
      // связи, иначе человек будет ждать письмо, которого никто не отправлял.
      setState(() => _error = e is ApiException && e.isNetwork
          ? 'Нет связи с сервером. Проверьте интернет и попробуйте снова.'
          : 'Не удалось отправить ссылку. Попробуйте позже.');
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
          Text(
            _byPhone
                ? 'Укажите номер, на который зарегистрирован аккаунт. Пришлём ссылку '
                    'в мессенджер, где вы подтверждали номер.'
                : 'Укажите адрес, на который зарегистрирован аккаунт. Пришлём письмо '
                    'со ссылкой — по ней можно будет задать новый пароль.',
            style: const TextStyle(fontSize: 15),
          ),
          const SizedBox(height: 24),
          SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: false, label: Text('E-mail')),
              ButtonSegment(value: true, label: Text('Телефон')),
            ],
            selected: {_byPhone},
            onSelectionChanged: (s) => setState(() {
              _byPhone = s.first;
              _error = null;
            }),
          ),
          const SizedBox(height: 24),
          if (_byPhone)
            // MG_PHONECODE: код страны выбирается, а не набирается вручную
            PhoneField(controller: _phone)
          else
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
          Icon(_byPhone ? Icons.forum_outlined : Icons.mark_email_read_outlined,
              size: 56, color: context.cs.primary),
          const SizedBox(height: 16),
          Text(_byPhone ? 'Ссылка отправлена' : 'Письмо отправлено',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Text(
            _byPhone
                ? 'Если аккаунт с номером ${_phone.text.trim()} существует, мы отправили ссылку '
                    'для смены пароля в мессенджер, где вы подтверждали номер. '
                    'Ссылка действует 2 часа.'
                : 'Если аккаунт с адресом ${_email.text.trim()} существует, мы отправили на него '
                    'ссылку для смены пароля. Ссылка действует 2 часа.',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 15),
          ),
          const SizedBox(height: 12),
          Text(
            _byPhone
                ? 'Сообщения нет? Проверьте, что бот не заблокирован, и что номер тот же, '
                    'с которым вы регистрировались.'
                : 'Письма нет? Проверьте папку «Спам» и убедитесь, что адрес тот же, '
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
            child: Text(_byPhone ? 'Ввести другой номер' : 'Ввести другой адрес'),
          ),
        ],
      );
}
