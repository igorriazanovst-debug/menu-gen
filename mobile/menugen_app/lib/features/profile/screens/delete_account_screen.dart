// MG_ACCDEL: удаление аккаунта из приложения.
//
// Google Play не публикует обновление приложения, которое даёт завести аккаунт,
// но не даёт удалить его изнутри. Отдельный экран, а не диалог из одной кнопки:
// перед необратимым действием человек должен увидеть, что именно исчезнет, — и
// увидеть это про СВОЙ аккаунт, а не общими словами. Что уедет вместе с ним,
// знает только сервер (GET /users/me/delete/): один ли он в семье, кому она
// достанется.
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../auth/bloc/auth_bloc.dart';

class DeleteAccountScreen extends StatefulWidget {
  const DeleteAccountScreen({super.key, required this.apiClient});

  final ApiClient apiClient;

  @override
  State<DeleteAccountScreen> createState() => _DeleteAccountScreenState();
}

class _DeleteAccountScreenState extends State<DeleteAccountScreen> {
  final _password = TextEditingController();

  bool _loading = true;
  bool _submitting = false;
  String? _error;

  int _graceDays = 30;
  bool _familyWillBeDeleted = false;
  List<String> _familiesToDelete = const [];
  List<String> _newOwners = const [];

  @override
  void initState() {
    super.initState();
    _loadConsequences();
  }

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  Future<void> _loadConsequences() async {
    try {
      final r = await widget.apiClient.get('/users/me/delete/');
      if (!mounted) return;
      setState(() {
        _graceDays = (r['grace_days'] as num?)?.toInt() ?? 30;
        _familyWillBeDeleted = r['family_data_will_be_deleted'] == true;
        _familiesToDelete = List<String>.from(r['families_to_delete'] ?? const []);
        _newOwners = List<String>.from(r['new_owners'] ?? const []);
        _loading = false;
      });
    } catch (_) {
      // Не показываем экран без последствий: человек согласился бы вслепую.
      if (!mounted) return;
      setState(() {
        _error = 'Не удалось загрузить данные. Проверьте соединение.';
        _loading = false;
      });
    }
  }

  Future<void> _confirmAndDelete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить аккаунт?'),
        content: Text(
          'Войти в аккаунт сразу станет нельзя. Данные будут удалены '
          'безвозвратно через $_graceDays дней.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Отмена'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.apiClient.post(
        '/users/me/delete/',
        data: {'password': _password.text},
      );
      if (!mounted) return;
      // Итог показываем диалогом, а не снекбаром: сразу после этого приложение
      // уходит на экран входа, и снекбар уехал бы вместе с деревом — человек
      // увидел бы форму входа без единого слова о том, что произошло.
      await showDialog<void>(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => AlertDialog(
          title: const Text('Аккаунт заблокирован'),
          content: Text(
            'Данные будут удалены через $_graceDays дней. Если передумаете — '
            'войдите в приложение до этого срока, и удаление отменится.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Понятно'),
            ),
          ],
        ),
      );
      if (!mounted) return;
      // Токен с этого момента недействителен: аккаунт заморожен, и сервер его
      // больше не пускает. Выходим сами, чтобы приложение не билось в 401.
      context.read<AuthBloc>().add(const AuthLogoutRequested());
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = 'Не удалось выполнить запрос. Попробуйте ещё раз.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Удаление аккаунта')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text(
                  'Что будет удалено',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Профиль, цели по КБЖУ, дневники питания и веса, избранные '
                  'рецепты и загруженные фотографии блюд.',
                ),
                const SizedBox(height: 16),

                if (_familyWillBeDeleted)
                  _Note(
                    icon: Icons.warning_amber_rounded,
                    color: Colors.red,
                    text: 'Вместе с аккаунтом будет удалена семья '
                        '«${_familiesToDelete.join('», «')}» со всеми её меню, '
                        'холодильником и списками покупок: кроме вас, в ней '
                        'никого нет.',
                  )
                else if (_newOwners.isNotEmpty)
                  _Note(
                    icon: Icons.people_outline,
                    color: Colors.blueGrey,
                    text: 'Семья и её данные сохранятся — они перейдут к '
                        '${_newOwners.join(', ')}.',
                  ),

                const SizedBox(height: 16),
                _Note(
                  icon: Icons.history,
                  color: Colors.blueGrey,
                  text: 'Удаление можно отменить в течение $_graceDays дней: '
                      'войдите в приложение обычным способом, и всё вернётся '
                      'на место. После этого срока данные удаляются '
                      'безвозвратно.',
                ),
                const SizedBox(height: 8),
                const _Note(
                  icon: Icons.receipt_long_outlined,
                  color: Colors.blueGrey,
                  text: 'Опубликованные вами рецепты остаются в общем каталоге '
                      'без указания автора. Сведения об оплатах сохраняются '
                      'без привязки к вам — этого требует бухгалтерский учёт.',
                ),

                const SizedBox(height: 24),
                TextField(
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Пароль',
                    helperText: 'Подтвердите, что это вы',
                    border: OutlineInputBorder(),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: _submitting ? null : _confirmAndDelete,
                  style: FilledButton.styleFrom(backgroundColor: Colors.red),
                  child: _submitting
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Удалить аккаунт'),
                ),
              ],
            ),
    );
  }
}

class _Note extends StatelessWidget {
  const _Note({required this.icon, required this.color, required this.text});

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
      ],
    );
  }
}
