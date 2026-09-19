import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';

/// MG_WRITEOFF: отметка «Приготовил» у блюда меню.
///
/// Холодильник до сих пор только пополнялся: купленное в него перекладывалось,
/// а убирать приходилось руками. Съеденное оставалось лежать, и список покупок
/// честно вычитал из потребности фарш, съеденный неделю назад.
///
/// Нажатие сразу списывает продукты, а лист показывает, что именно ушло.
/// Спрашивать подтверждение заранее незачем: человек уже сказал, что
/// приготовил, а ошибку снимает «Отменить списание» в том же листе.
///
/// Нехватку не додумываем за человека. Раз он отметил, что блюдо приготовлено,
/// значит недостающее он как-то достал, — поэтому там кнопка «Докупил»,
/// которая просто закрывает лист, а не заводит ничего в холодильник.
/// [onChanged] зовётся с новым состоянием блюда: `true` — продукты списаны,
/// `false` — списание отменено. Флаг, а не голый «обновись», нужен карточке:
/// перечитывание меню идёт своим ходом и приходит позже нажатия.
Future<void> showCookedSheet(
  BuildContext context, {
  required ApiClient apiClient,
  required int menuId,
  required int itemId,
  required String dishTitle,
  ValueChanged<bool>? onChanged,
}) async {
  Map<String, dynamic> data;
  try {
    final resp = await apiClient.post('/menu/$menuId/items/$itemId/cooked/');
    data = resp is Map ? Map<String, dynamic>.from(resp) : <String, dynamic>{};
  } catch (e) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(e is ApiException ? e.message : 'Не удалось списать продукты'),
      ),
    );
    return;
  }

  onChanged?.call(true);
  if (!context.mounted) return;

  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (sheetCtx) => _CookedResultSheet(
      apiClient: apiClient,
      menuId: menuId,
      itemId: itemId,
      dishTitle: dishTitle,
      data: data,
      onChanged: onChanged,
    ),
  );
}

List<Map<String, dynamic>> _lines(dynamic raw) {
  if (raw is! List) return const [];
  return raw
      .whereType<Map>()
      .map((e) => Map<String, dynamic>.from(e))
      .toList(growable: false);
}

String _amount(Map<String, dynamic> line) {
  final qty = (line['quantity'] ?? '').toString();
  final unit = (line['unit'] ?? '').toString();
  // Хвостовые нули в «200.00» человеку ни о чём не говорят.
  final trimmed = qty.contains('.')
      ? qty.replaceFirst(RegExp(r'\.?0+$'), '')
      : qty;
  return unit.isEmpty ? trimmed : '$trimmed $unit';
}

class _CookedResultSheet extends StatefulWidget {
  final ApiClient apiClient;
  final int menuId;
  final int itemId;
  final String dishTitle;
  final Map<String, dynamic> data;
  final ValueChanged<bool>? onChanged;

  const _CookedResultSheet({
    required this.apiClient,
    required this.menuId,
    required this.itemId,
    required this.dishTitle,
    required this.data,
    required this.onChanged,
  });

  @override
  State<_CookedResultSheet> createState() => _CookedResultSheetState();
}

class _CookedResultSheetState extends State<_CookedResultSheet> {
  bool _undoing = false;

  Future<void> _undo() async {
    if (_undoing) return;
    setState(() => _undoing = true);
    try {
      await widget.apiClient.delete('/menu/${widget.menuId}/items/${widget.itemId}/cooked/');
    } catch (e) {
      if (!mounted) return;
      setState(() => _undoing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e is ApiException ? e.message : 'Не удалось отменить списание'),
        ),
      );
      return;
    }
    widget.onChanged?.call(false);
    if (!mounted) return;
    // Мессенджер берём до pop: после закрытия листа этот context уже мёртв, и
    // сообщение об удачной отмене падало бы вместо того, чтобы показаться.
    final messenger = ScaffoldMessenger.of(context);
    Navigator.of(context).pop();
    messenger.showSnackBar(
      const SnackBar(content: Text('Списание отменено — продукты вернулись в холодильник.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final written = _lines(widget.data['written_off']);
    final missing = _lines(widget.data['shortfall']);
    final repeated = widget.data['created'] == false;

    return Container(
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 10),
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: context.tokens.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
                child: Row(
                  children: [
                    Icon(Icons.restaurant_menu, color: cs.primary),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        widget.dishTitle,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: cs.onSurface,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (repeated)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 0),
                  child: Text(
                    'Блюдо уже было отмечено — второй раз продукты не списались.',
                    style: TextStyle(fontSize: 13, color: context.tokens.textSecondary),
                  ),
                ),
              if (written.isEmpty && missing.isEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                  child: Text(
                    'Списывать было нечего: у блюда не указаны продукты.',
                    style: TextStyle(fontSize: 15, color: context.tokens.textSecondary),
                  ),
                ),
              if (written.isNotEmpty)
                _Section(
                  title: 'Списано из холодильника',
                  icon: Icons.kitchen,
                  color: cs.primary,
                  lines: written,
                ),
              if (written.isEmpty && missing.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                  child: Text(
                    'Из холодильника ничего не списалось — этих продуктов там не было.',
                    style: TextStyle(fontSize: 15, color: context.tokens.textSecondary),
                  ),
                ),
              if (missing.isNotEmpty)
                _Section(
                  title: 'Не хватило дома',
                  icon: Icons.shopping_basket_outlined,
                  color: cs.error,
                  lines: missing,
                ),
              const SizedBox(height: 20),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: FilledButton(
                  onPressed: _undoing ? null : () => Navigator.of(context).pop(),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(48),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                  child: Text(missing.isEmpty ? 'Готово' : 'Докупил'),
                ),
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: TextButton.icon(
                  onPressed: _undoing ? null : _undo,
                  icon: _undoing
                      ? const SizedBox(
                          width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.undo, size: 18),
                  label: const Text('Отменить списание'),
                  style: TextButton.styleFrom(foregroundColor: context.tokens.textSecondary),
                ),
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;
  final List<Map<String, dynamic>> lines;

  const _Section({
    required this.title,
    required this.icon,
    required this.color,
    required this.lines,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: color),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: color),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (final line in lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      (line['name'] ?? '').toString(),
                      style: TextStyle(fontSize: 15, color: cs.onSurface),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _amount(line),
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: context.tokens.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
