import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';

/// MG_WRITEOFF: «Израсходовал» — ручное списание позиции холодильника.
///
/// Съеденное убиралось из холодильника только удалением позиции целиком, и то
/// безымянным долгим нажатием. Початую пачку это не описывает никак: съели
/// половину — либо удали всё, либо правь количество руками в отдельном экране.
///
/// Количество здесь — в единице самой позиции, и ни во что не переводится.
/// Человек смотрит на конкретную пачку и говорит, сколько ушло из неё; перевод
/// штук и упаковок в граммы всё равно делать нечем (BACKLOG T-36).
///
/// Ошибочное нажатие снимается «Отменить» в сообщении: списание — запись, и
/// вернуть её можно целиком.
Future<void> showConsumeSheet(
  BuildContext context, {
  required ApiClient apiClient,
  required Map<String, dynamic> item,
  VoidCallback? onDone,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _ConsumeSheet(apiClient: apiClient, item: item, onDone: onDone),
  );
}

String _fmtQty(Object? raw) {
  final s = (raw ?? '').toString();
  if (!s.contains('.')) return s;
  return s.replaceFirst(RegExp(r'\.?0+$'), '');
}

class _ConsumeSheet extends StatefulWidget {
  final ApiClient apiClient;
  final Map<String, dynamic> item;
  final VoidCallback? onDone;

  const _ConsumeSheet({
    required this.apiClient,
    required this.item,
    required this.onDone,
  });

  @override
  State<_ConsumeSheet> createState() => _ConsumeSheetState();
}

class _ConsumeSheetState extends State<_ConsumeSheet> {
  late final TextEditingController _qty =
      TextEditingController(text: _fmtQty(widget.item['quantity']));
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _qty.dispose();
    super.dispose();
  }

  String get _unit => (widget.item['unit'] ?? '').toString();

  Future<void> _send({required bool all}) async {
    if (_sending) return;
    final raw = _qty.text.trim().replaceAll(',', '.');
    if (!all && (raw.isEmpty || (double.tryParse(raw) ?? 0) <= 0)) {
      setState(() => _error = 'Укажите количество больше нуля');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });

    final id = widget.item['id'];
    dynamic resp;
    try {
      resp = await widget.apiClient.post(
        '/fridge/$id/consume/',
        data: all ? <String, dynamic>{} : {'quantity': raw},
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _error = e is ApiException ? e.message : 'Не удалось списать';
      });
      return;
    }

    widget.onDone?.call();
    if (!mounted) return;
    // Мессенджер берём до pop: после закрытия листа этот context уже мёртв.
    final messenger = ScaffoldMessenger.of(context);
    final writeOffId = (resp is Map ? resp['write_off_id'] : null) as int?;
    Navigator.of(context).pop();
    messenger.showSnackBar(
      SnackBar(
        content: Text('${widget.item['name'] ?? 'Позиция'}: списано'),
        action: writeOffId == null
            ? null
            : SnackBarAction(
                label: 'Отменить',
                onPressed: () async {
                  try {
                    await widget.apiClient.delete('/fridge/write-offs/$writeOffId/');
                    widget.onDone?.call();
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
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: cs.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SafeArea(
          top: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text(
                  (widget.item['name'] ?? '').toString(),
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: cs.onSurface),
                ),
              ),
              const SizedBox(height: 4),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text(
                  'В холодильнике: ${_fmtQty(widget.item['quantity'])} $_unit',
                  style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
                ),
              ),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: TextField(
                  controller: _qty,
                  autofocus: true,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
                  decoration: InputDecoration(
                    labelText: 'Израсходовано',
                    suffixText: _unit,
                    errorText: _error,
                    border: const OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _sending ? null : () => _send(all: true),
                        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                        child: const Text('Списать всё'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: _sending ? null : () => _send(all: false),
                        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                        child: _sending
                            ? const SizedBox(
                                width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Text('Списать'),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}
