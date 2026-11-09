// MG_WORKOUT: физнагрузки за день — список, запись и удаление.
//
// Живёт во вкладке «Тело», рядом с весом и обхватами: это всё про тело, а не
// про еду. Тренеру без этого не на что смотреть — он видел в дневнике одну
// еду, и вопрос «что человек делал на этом калораже» ответа не имел.
//
// Чего карточка НЕ делает: не трогает дневную норму. Норма уже содержит
// коэффициент активности («умеренные нагрузки 3–5 раз в неделю» — множитель
// 1,55), и прибавка за каждую тренировку посчитала бы его дважды. Человеку на
// похудении приложение разрешило бы съесть лишние полтысячи калорий — это
// работа против его цели, а не мелкая неточность. Поэтому расход показывается
// отдельным числом и нигде не вычитается.
//
// Отличие от веса: записей на день МНОГО. Пробежка утром и зал вечером — два
// занятия, а не перезапись одного.
import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/widgets/tall_dialog.dart';
import '../models/workout.dart';

class WorkoutsCard extends StatefulWidget {
  final ApiClient api;
  final String date;
  final int? memberId;

  /// Занятия записаны — «Итогам» нужно перечитать расход за день.
  final VoidCallback? onChanged;

  const WorkoutsCard({
    super.key,
    required this.api,
    required this.date,
    this.memberId,
    this.onChanged,
  });

  @override
  State<WorkoutsCard> createState() => _WorkoutsCardState();
}

class _WorkoutsCardState extends State<WorkoutsCard> {
  List<WorkoutLog> _rows = const [];
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant WorkoutsCard old) {
    super.didUpdateWidget(old);
    // Сменили день или участника — показывать надо их занятия, а не прежние.
    if (old.date != widget.date || old.memberId != widget.memberId) _load();
  }

  Future<void> _load() async {
    try {
      final params = <String, String>{'date': widget.date};
      if (widget.memberId != null) params['member_id'] = '${widget.memberId}';
      final r = await widget.api.get('/diary/workouts/', params: params);
      if (!mounted) return;
      setState(() {
        _rows = (r is List ? r : const [])
            .whereType<Map>()
            .map((e) => WorkoutLog.fromJson(Map<String, dynamic>.from(e)))
            .toList();
      });
    } catch (_) {
      // Занятий может не быть вовсе — это не ошибка, список просто пуст.
      if (mounted) setState(() => _rows = const []);
    }
  }

  Future<void> _add() async {
    final data = await showDialog<Map<String, dynamic>?>(
      context: context,
      builder: (_) => _AddWorkoutDialog(api: widget.api),
    );
    if (data == null || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final path = widget.memberId == null
          ? '/diary/workouts/'
          : '/diary/workouts/?member_id=${widget.memberId}';
      await widget.api.post(path, data: {...data, 'date': widget.date});
      await _load();
      widget.onChanged?.call();
    } catch (e) {
      // Причину отказа говорим словами сервера: он отвечает по делу, и общее
      // «не удалось» заставляет человека гадать, что именно не так.
      final why = e is ApiException ? e.message : null;
      if (mounted) {
        setState(() => _error = (why != null && why.isNotEmpty) ? why : 'Не удалось записать занятие.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove(WorkoutLog row) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.delete('/diary/workouts/${row.id}/');
      await _load();
      widget.onChanged?.call();
    } catch (_) {
      if (mounted) setState(() => _error = 'Не удалось убрать занятие.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Суммарный расход за день. Занятия без калорий в сумму не входят.
  int get _burned => _rows.fold(0, (sum, r) => sum + (r.calories ?? 0));

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 2, 12, 2),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('🏃', style: TextStyle(fontSize: 16)),
                const SizedBox(width: 8),
                const Text('Занятия', style: TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                if (_burned > 0)
                  Text('$_burned ккал',
                      style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
              ],
            ),
            if (_rows.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text('За этот день занятий не записано',
                    style: TextStyle(fontSize: 13, color: Colors.grey.shade500)),
              )
            else
              for (final r in _rows)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Flexible(
                                  child: Text(r.title,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(fontSize: 14)),
                                ),
                                // MG_HEADKEEPS: занятие записал не сам человек.
                                if (r.addedByName != null) ...[
                                  const SizedBox(width: 4),
                                  Tooltip(
                                    message: 'Записал(а) ${r.addedByName}',
                                    child: const Text('👑', style: TextStyle(fontSize: 12)),
                                  ),
                                ],
                              ],
                            ),
                            Text(
                              r.calories == null
                                  ? r.durationLabel
                                  // «≈» говорит, что это наша оценка по
                                  // справочному MET и весу, а не показание
                                  // прибора. Без этого знака человек сверит
                                  // число с пульсометром и решит, что мы врём.
                                  : '${r.durationLabel} · ${r.caloriesEstimated ? '≈' : ''}${r.calories} ккал',
                              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        iconSize: 18,
                        visualDensity: VisualDensity.compact,
                        tooltip: 'Убрать',
                        onPressed: _busy ? null : () => _remove(r),
                        icon: const Icon(Icons.close),
                      ),
                    ],
                  ),
                ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 12)),
              ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: _busy ? null : _add,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Добавить занятие'),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  visualDensity: VisualDensity.compact,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Запись занятия: выбор из справочника или своё название.
///
/// В TallDialog, а не в обычном: список занятий — пятьдесят строк с поиском, и
/// поднятая клавиатура в фиксированном диалоге оставляла бы от него полторы
/// строки (MG_TALLDIALOG).
class _AddWorkoutDialog extends StatefulWidget {
  final ApiClient api;
  const _AddWorkoutDialog({required this.api});

  @override
  State<_AddWorkoutDialog> createState() => _AddWorkoutDialogState();
}

class _AddWorkoutDialogState extends State<_AddWorkoutDialog> {
  final _search = TextEditingController();
  final _duration = TextEditingController(text: '30');
  final _calories = TextEditingController();
  final _custom = TextEditingController();

  List<ActivityType> _catalog = const [];
  ActivityType? _picked;
  bool _loading = true;
  bool _own = false; // своё название вместо справочника

  @override
  void initState() {
    super.initState();
    _loadCatalog();
    _search.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _search.dispose();
    _duration.dispose();
    _calories.dispose();
    _custom.dispose();
    super.dispose();
  }

  Future<void> _loadCatalog() async {
    try {
      final r = await widget.api.get('/diary/activities/');
      if (!mounted) return;
      setState(() {
        _catalog = (r is List ? r : const [])
            .whereType<Map>()
            .map((e) => ActivityType.fromJson(Map<String, dynamic>.from(e)))
            .toList();
        _loading = false;
      });
    } catch (_) {
      // Справочник не загрузился — остаётся своё название со своими
      // калориями. Это хуже, но лучше, чем пустой диалог.
      if (mounted) {
        setState(() {
          _loading = false;
          _own = true;
        });
      }
    }
  }

  List<ActivityType> get _found {
    final q = _search.text.trim().toLowerCase();
    if (q.isEmpty) return _catalog;
    return _catalog.where((a) => a.name.toLowerCase().contains(q)).toList();
  }

  void _submit() {
    final minutes = int.tryParse(_duration.text.trim());
    if (minutes == null || minutes <= 0 || minutes > 1440) return;
    final kcal = int.tryParse(_calories.text.trim());
    final out = <String, dynamic>{'duration_min': minutes};
    if (kcal != null) out['calories'] = kcal;
    if (_own) {
      final name = _custom.text.trim();
      if (name.isEmpty) return;
      out['custom_name'] = name;
    } else {
      if (_picked == null) return;
      out['activity'] = _picked!.id;
    }
    Navigator.of(context).pop(out);
  }

  bool get _canSubmit {
    final minutes = int.tryParse(_duration.text.trim());
    if (minutes == null || minutes <= 0 || minutes > 1440) return false;
    return _own ? _custom.text.trim().isNotEmpty : _picked != null;
  }

  @override
  Widget build(BuildContext context) {
    return TallDialog(
      title: 'Занятие',
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Отмена')),
        TextButton(onPressed: _canSubmit ? _submit : null, child: const Text('Записать')),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Переключатель «из списка / своё» стоит первым: от него зависит,
          // что человек увидит ниже, и прятать его под список нельзя.
          SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: false, label: Text('Из списка')),
              ButtonSegment(value: true, label: Text('Своё')),
            ],
            selected: {_own},
            onSelectionChanged: (s) => setState(() => _own = s.first),
            style: const ButtonStyle(visualDensity: VisualDensity.compact),
          ),
          const SizedBox(height: 8),
          if (_own)
            TextField(
              controller: _custom,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Название',
                hintText: 'Сенокос',
                isDense: true,
              ),
              onChanged: (_) => setState(() {}),
            )
          else ...[
            TextField(
              controller: _search,
              decoration: const InputDecoration(
                labelText: 'Занятие',
                hintText: 'бег, зал, плавание',
                prefixIcon: Icon(Icons.search, size: 18),
                isDense: true,
              ),
            ),
            if (_picked != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(_picked!.name,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                    ),
                    TextButton(
                      onPressed: () => setState(() => _picked = null),
                      child: const Text('выбрать другое'),
                    ),
                  ],
                ),
              ),
          ],
          const SizedBox(height: 8),
          Row(
            children: [
              SizedBox(
                width: 92,
                child: TextField(
                  controller: _duration,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Минут', isDense: true),
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _calories,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Калории',
                    // Пустое поле — не пропуск, а нормальный путь: посчитаем
                    // по справочному MET и последнему весу. Введённое руками
                    // не перебиваем: человек мог смотреть на пульсометр.
                    hintText: 'посчитаем сами',
                    isDense: true,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          // Список занимает весь остаток высоты: это и есть смысл TallDialog —
          // список говорит «мне столько», а не упирается в выдуманное число.
          if (!_own && _picked == null)
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _found.isEmpty
                      ? Center(
                          child: Text(
                            'Ничего не нашлось. Впишите своё название.',
                            textAlign: TextAlign.center,
                            style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
                          ),
                        )
                      : ListView.builder(
                          itemCount: _found.length,
                          itemBuilder: (_, i) {
                            final a = _found[i];
                            // Заголовок группы — только там, где группа
                            // сменилась: справочник уже отсортирован сервером.
                            final showGroup = i == 0 || _found[i - 1].group != a.group;
                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                if (showGroup && a.groupLabel.isNotEmpty)
                                  Padding(
                                    padding: const EdgeInsets.fromLTRB(0, 8, 0, 2),
                                    child: Text(
                                      a.groupLabel.toUpperCase(),
                                      style: TextStyle(
                                        fontSize: 10,
                                        letterSpacing: 0.6,
                                        fontWeight: FontWeight.w700,
                                        color: Colors.grey.shade500,
                                      ),
                                    ),
                                  ),
                                InkWell(
                                  onTap: () => setState(() {
                                    _picked = a;
                                    FocusScope.of(context).unfocus();
                                  }),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(vertical: 8),
                                    child: Text(a.name, style: const TextStyle(fontSize: 14)),
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
            ),
        ],
      ),
    );
  }
}
