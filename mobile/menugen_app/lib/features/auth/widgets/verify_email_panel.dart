// MG_EMAILVERIFY_MOBILE: «письмо отправлено — подтвердите адрес».
//
// Один и тот же блок нужен в двух местах: после регистрации (аккаунт создан,
// но входа ещё нет) и на входе, когда бэкенд отвечает `email_not_verified`.
// Раньше во втором случае мобильное предлагало «написать в поддержку» — при
// том что письмо высылается одной кнопкой.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';

class VerifyEmailPanel extends StatefulWidget {
  final ApiClient apiClient;
  final String email;

  /// Заголовок: после регистрации и на входе повод разный.
  final String title;

  const VerifyEmailPanel({
    super.key,
    required this.apiClient,
    required this.email,
    this.title = 'Подтвердите e-mail',
  });

  @override
  State<VerifyEmailPanel> createState() => _VerifyEmailPanelState();
}

class _VerifyEmailPanelState extends State<VerifyEmailPanel> {
  bool _sending = false;
  String? _note;
  bool _failed = false;

  Future<void> _resend() async {
    setState(() {
      _sending = true;
      _note = null;
      _failed = false;
    });
    try {
      await widget.apiClient
          .post('/auth/email/resend/', data: {'email': widget.email});
      if (!mounted) return;
      setState(() => _note = 'Письмо отправлено повторно.');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _failed = true;
        // Причина важна: «слишком часто» и «нет связи» лечатся по-разному.
        _note = e is ApiException && e.isNetwork
            ? 'Нет связи с сервером. Проверьте интернет.'
            : 'Не удалось отправить письмо. Попробуйте позже.';
      });
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.mark_email_unread_outlined, color: context.cs.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Text(widget.title,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ),
          ]),
          const SizedBox(height: 8),
          Text(
            'Мы отправили письмо на ${widget.email}. Перейдите по ссылке из '
            'письма — после этого можно войти.',
            style: TextStyle(fontSize: 13, color: context.cs.onSurfaceVariant),
          ),
          const SizedBox(height: 4),
          Text(
            'Письма нет — проверьте папку «Спам».',
            style: TextStyle(fontSize: 12, color: context.cs.outline),
          ),
          if (_note != null) ...[
            const SizedBox(height: 12),
            Text(
              _note!,
              style: TextStyle(
                fontSize: 13,
                color: _failed ? context.cs.error : context.cs.primary,
              ),
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: _sending ? null : _resend,
              child: _sending
                  ? const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Выслать письмо снова'),
            ),
          ),
        ],
      ),
    );
  }
}
