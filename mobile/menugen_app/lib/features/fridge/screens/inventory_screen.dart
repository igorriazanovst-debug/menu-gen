import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../bloc/fridge_bloc.dart';
import 'consume_sheet.dart';

/// MG_WRITEOFF: инвентаризация — пройти холодильник и сверить его с правдой.
///
/// Обычный список холодильника отвечает на вопрос «что у меня есть». Этот
/// экран отвечает на другой: «что из этого кончилось». Разница в том, что
/// здесь позиции не ищут — их проходят подряд, и каждая уходит из очереди,
/// как только про неё сказали. Иначе человек на третьей строке забывает, где
/// остановился, и до конца списка не доходит никогда.
///
/// Три ответа на позицию: «есть» (оставить как есть), «кончилось» (списать
/// целиком) и «осталось меньше» (сказать, сколько ушло). Удаления здесь нет
/// намеренно: инвентаризация — про расход, а не про ошибки в списке. Ошибки
/// правятся в самом холодильнике.
class InventoryScreen extends StatefulWidget {
  final ApiClient apiClient;

  const InventoryScreen({super.key, required this.apiClient});

  @override
  State<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends State<InventoryScreen> {
  /// Позиции, про которые в этом проходе уже сказали «есть».
  ///
  /// Списанные уходят из списка сами — их убирает перезагрузка холодильника.
  /// А «есть» ничего не меняет на сервере, и без своей памяти такая позиция
  /// осталась бы в очереди навсегда.
  final Set<int> _kept = {};
  int _consumed = 0;

  String _fmtQty(Object? raw) {
    final s = (raw ?? '').toString();
    if (!s.contains('.')) return s;
    return s.replaceFirst(RegExp(r'\.?0+$'), '');
  }

  void _reload() {
    if (mounted) context.read<FridgeBloc>().add(const FridgeLoadRequested());
  }

  Future<void> _consumeAll(Map<String, dynamic> item) async {
    final id = item['id'] as int?;
    if (id == null) return;
    dynamic resp;
    try {
      resp = await widget.apiClient.post('/fridge/$id/consume/', data: const <String, dynamic>{});
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e is ApiException ? e.message : 'Не удалось списать')),
      );
      return;
    }
    if (!mounted) return;
    setState(() => _consumed += 1);
    _reload();

    final writeOffId = (resp is Map ? resp['write_off_id'] : null) as int?;
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      SnackBar(
        content: Text('${item['name'] ?? 'Позиция'}: списано'),
        action: writeOffId == null
            ? null
            : SnackBarAction(
                label: 'Отменить',
                onPressed: () async {
                  try {
                    await widget.apiClient.delete('/fridge/write-offs/$writeOffId/');
                    if (mounted) setState(() => _consumed -= 1);
                    _reload();
                  } catch (_) {
                    messenger.showSnackBar(
                      const SnackBar(content: Text('Не удалось отменить списание')),
                    );
                  }
                },
              ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Инвентаризация')),
      body: BlocBuilder<FridgeBloc, FridgeState>(
        builder: (context, state) {
          if (state is FridgeLoading) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state is FridgeError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(state.message, textAlign: TextAlign.center),
              ),
            );
          }
          final all = state is FridgeLoaded ? state.items : const <Map<String, dynamic>>[];
          final queue = all.where((i) => !_kept.contains(i['id'] as int?)).toList();

          if (all.isEmpty) {
            return const _Done(text: 'Холодильник пуст — сверять нечего.');
          }
          if (queue.isEmpty) {
            return _Done(
              text: _consumed == 0
                  ? 'Всё на месте. Холодильник сходится.'
                  : 'Готово. Списано позиций: $_consumed.',
            );
          }

          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Осталось пройти: ${queue.length} из ${all.length}',
                        style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
                      ),
                    ),
                    if (_consumed > 0)
                      Text(
                        'списано: $_consumed',
                        style: TextStyle(fontSize: 13, color: cs.primary),
                      ),
                  ],
                ),
              ),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(8, 4, 8, 24),
                  itemCount: queue.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final item = queue[i];
                    final id = item['id'] as int?;
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  (item['name'] ?? '').toString(),
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: cs.onSurface,
                                  ),
                                ),
                              ),
                              Text(
                                '${_fmtQty(item['quantity'])} ${item['unit'] ?? ''}',
                                style: TextStyle(fontSize: 14, color: cs.onSurfaceVariant),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              OutlinedButton.icon(
                                onPressed: id == null ? null : () => setState(() => _kept.add(id)),
                                icon: const Icon(Icons.check, size: 18),
                                label: const Text('Есть'),
                              ),
                              OutlinedButton.icon(
                                onPressed: () => showConsumeSheet(
                                  context,
                                  apiClient: widget.apiClient,
                                  item: item,
                                  onDone: () {
                                    if (mounted) setState(() => _consumed += 1);
                                    _reload();
                                  },
                                ),
                                icon: const Icon(Icons.edit_outlined, size: 18),
                                label: const Text('Осталось меньше'),
                              ),
                              FilledButton.tonalIcon(
                                onPressed: () => _consumeAll(item),
                                icon: const Icon(Icons.remove_circle_outline, size: 18),
                                label: const Text('Кончилось'),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _Done extends StatelessWidget {
  final String text;

  const _Done({required this.text});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.fact_check_outlined, size: 64, color: cs.primary),
            const SizedBox(height: 16),
            Text(
              text,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: cs.onSurface),
            ),
          ],
        ),
      ),
    );
  }
}
