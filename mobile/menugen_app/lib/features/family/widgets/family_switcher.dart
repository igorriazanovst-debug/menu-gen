// MG_ACTIVEFAMILY + MG_FAMINVITE: за каким столом человек сидит и кто его зовёт.
//
// Два блока наверху экрана «Семья»:
//
//   * входящие приглашения — их показываем первыми, они требуют ответа;
//   * список семей, где человек состоит, с пометкой активной.
//
// Оба живут своим состоянием и ходят в сервер сами, не через FamilyBloc: блок
// занят одной семьёй — той, в которой человек сейчас, — и знать про остальные
// ему незачем.
//
// Самое важное здесь не рисование, а то, что происходит после смены стола: два
// кэша чистятся и дерево приложения пересобирается. Иначе на экране остались бы
// холодильник, меню и список покупок прежней семьи — то есть чужие. Подробности
// в core/app_restart.dart.
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/app_restart.dart';
import '../../../core/cache/http_cache_store.dart';
import '../../../core/cache/shopping_cache.dart';
import '../bloc/family_bloc.dart';

class FamilySwitcher extends StatefulWidget {
  const FamilySwitcher({super.key});

  @override
  State<FamilySwitcher> createState() => _FamilySwitcherState();
}

class _FamilySwitcherState extends State<FamilySwitcher> {
  List<Map<String, dynamic>> _choices = const [];
  List<Map<String, dynamic>> _invites = const [];
  int? _busyFamilyId;
  int? _busyInviteId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  List<Map<String, dynamic>> _asRows(dynamic raw) {
    if (raw is! List) return const [];
    return raw.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<void> _load() async {
    final api = context.read<FamilyBloc>().apiClient;
    // Ни один из двух списков не обязателен для экрана: не пришли — просто не
    // показываем блок. Ронять из-за них «Семью» нельзя.
    try {
      final rows = _asRows(await api.get('/family/choices/'));
      if (mounted) setState(() => _choices = rows);
    } catch (_) {/* блок не покажем */}
    try {
      final rows = _asRows(await api.get('/family/invites/'));
      if (mounted) setState(() => _invites = rows);
    } catch (_) {/* блок не покажем */}
  }

  /// Выбросить всё, что осталось от прежней семьи, и пересобрать дерево.
  Future<void> _resetAndRestart() async {
    // Оба кэша забираем до первого await: после него трогать context нельзя —
    // виджет к этому моменту может быть уже снят.
    final httpCache = context.read<HttpCacheStore>();
    final shoppingCache = context.read<ShoppingCache>();
    await httpCache.clearAll();
    await shoppingCache.clearAll();
    if (!mounted) return;
    AppRestart.restart(context);
  }

  Future<void> _switchTo(Map<String, dynamic> row) async {
    final id = row['id'] as int;
    setState(() => _busyFamilyId = id);
    try {
      await context.read<FamilyBloc>().apiClient.post(
            '/family/switch/',
            data: {'family_id': id},
          );
      await _resetAndRestart();
    } catch (e) {
      if (!mounted) return;
      setState(() => _busyFamilyId = null);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось перейти: $e')),
      );
    }
  }

  Future<void> _respond(Map<String, dynamic> invite, bool accept) async {
    final id = invite['id'] as int;
    setState(() => _busyInviteId = id);
    try {
      await context.read<FamilyBloc>().apiClient.post(
            '/family/invites/$id/respond/',
            data: {'accept': accept},
          );
      if (accept) {
        // Согласие сажает за новый стол — значит всё то же, что при переходе.
        await _resetAndRestart();
        return;
      }
      if (!mounted) return;
      setState(() {
        _invites = _invites.where((row) => row['id'] != id).toList();
        _busyInviteId = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _busyInviteId = null);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось ответить: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final blocks = <Widget>[];
    if (_invites.isNotEmpty) blocks.add(_invitesCard(context));
    // Переключатель показываем, только когда есть из чего выбирать: одна семья
    // у большинства людей, и лишний блок им ни о чём не говорит.
    if (_choices.length > 1) blocks.add(_choicesCard(context));
    if (blocks.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final block in blocks) ...[block, const SizedBox(height: 16)],
      ],
    );
  }

  Widget _invitesCard(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.35),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Вас приглашают в семью',
                style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(
              'Если примете — общими станут холодильник, список покупок и меню, '
              'а глава семьи сможет видеть и менять ваши нормы КБЖУ. Дневник '
              'питания, вода и вес останутся вашими. Пока не ответите, ничего '
              'не меняется.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            ..._invites.map((invite) {
              final busy = _busyInviteId == invite['id'];
              final by = (invite['invited_by_name'] as String?) ?? '';
              return ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text((invite['family_name'] as String?) ?? 'Семья'),
                subtitle: Text(
                  '${by.isEmpty ? 'Глава семьи' : by} · участников: ${invite['members_count'] ?? 0}',
                ),
                trailing: busy
                    ? const SizedBox(
                        width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          TextButton(
                            onPressed: () => _respond(invite, true),
                            child: const Text('Принять'),
                          ),
                          TextButton(
                            onPressed: () => _respond(invite, false),
                            child: const Text('Отклонить'),
                          ),
                        ],
                      ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _choicesCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('В какой семье вы сейчас',
                style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(
              'Холодильник, меню, список покупок и подписка — общие для той семьи, '
              'в которой вы сейчас. Дневник, вода и вес остаются вашими в любой из них.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            ..._choices.map((row) {
              final isActive = row['is_active'] == true;
              final busy = _busyFamilyId == row['id'];
              final role = row['role'] == 'head' ? 'Глава' : 'Участник';
              final premium =
                  row['has_premium'] == true ? 'премиум' : 'без премиума';
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  isActive ? Icons.check_circle : Icons.circle_outlined,
                  color: isActive ? Theme.of(context).colorScheme.primary : null,
                ),
                title: Text(
                  '${row['name'] ?? 'Семья'}${row['is_own'] == true ? ' · своя' : ''}',
                ),
                subtitle: Text('$role · участников: ${row['members_count'] ?? 0} · $premium'),
                trailing: isActive
                    ? const Text('Сейчас здесь')
                    : busy
                        ? const SizedBox(
                            width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                        : TextButton(
                            onPressed: () => _switchTo(row),
                            child: const Text('Перейти'),
                          ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
