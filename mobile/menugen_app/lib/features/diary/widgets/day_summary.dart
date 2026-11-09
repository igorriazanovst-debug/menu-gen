// MG_DAYSUM: вкладка «Итоги дня».
//
// Отвечает на главный вопрос дня одним взглядом: сколько съедено из нормы и
// сколько осталось. До этого ответа не было вовсе — дневник показывал, ЧТО
// съедено, а чтобы понять, много это или мало, надо было считать в голове.
//
// Четыре правила, по которым здесь считается:
//
// **Сравниваем с нормой человека, а не с планом меню.** Сводка над списком еды
// сравнивает факт с запланированным — это другой вопрос («выполнил ли план»).
// Здесь вопрос «сколько мне ещё можно», и ответ на него даёт `calorie_target`
// из профиля. Нормы нет — кольца нет: нарисовать его от выдуманной нормы
// значит соврать в самом заметном месте экрана.
//
// **Факт — это съеденное.** Плановая запись без галочки показана бледной
// частью полосы: видно, что день ещё не закрыт, но в сумму она не идёт.
//
// **Расход не вычитается.** Норма уже содержит коэффициент активности, и
// прибавка за тренировку посчитала бы его дважды (см.
// backend/apps/diary/workout_calories.py). Потраченное стоит отдельной
// плиткой — его видно, но на остаток оно не влияет.
//
// **Проценты БЖУ считаются от съеденного, а не от нормы.** Вопрос «чего в моём
// рационе больше» не зависит от того, задана ли норма.
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../models/diary_entry.dart';
import '../models/diary_stats.dart';

/// Калорийность грамма: белок и углеводы по 4 ккал, жир 9. Числа
/// общепринятые (коэффициенты Атуотера) — не наши.
const _kcalPerGram = {'proteins': 4.0, 'fats': 9.0, 'carbs': 4.0};

const _proteinColor = Color(0xFF588157);
const _fatColor = Color(0xFFF4A261);
const _carbColor = Color(0xFF7CB342);

class DaySummaryTab extends StatefulWidget {
  final ApiClient api;
  final String date;
  final int? memberId;
  final DiaryDayStats stats;
  final List<DiaryEntry> entries;
  final int waterMl;

  /// MG_MEALSLOT: раскладка дня — три приёма или пять. Пустые разделы своей
  /// раскладки показываем: в пустом видно, что туда ничего не записано.
  final String mealPlanType;

  /// Норма из профиля. null — не задана, и тогда вместо кольца стоит
  /// приглашение её посчитать.
  final int? calorieTarget;
  final double? proteinTarget;
  final double? fatTarget;
  final double? carbTarget;

  /// Открыть калькулятор КБЖУ — когда норма не задана.
  final VoidCallback onCalcTarget;

  const DaySummaryTab({
    super.key,
    required this.api,
    required this.date,
    required this.memberId,
    required this.stats,
    required this.entries,
    required this.waterMl,
    required this.mealPlanType,
    required this.calorieTarget,
    required this.proteinTarget,
    required this.fatTarget,
    required this.carbTarget,
    required this.onCalcTarget,
  });

  @override
  State<DaySummaryTab> createState() => _DaySummaryTabState();
}

class _DaySummaryTabState extends State<DaySummaryTab> {
  /// Вес за этот день. Только показ: правится на вкладке «Тело», и второго
  /// места ввода здесь нет намеренно — два поля для одного числа расходятся.
  String? _weight;

  @override
  void initState() {
    super.initState();
    _loadWeight();
  }

  @override
  void didUpdateWidget(covariant DaySummaryTab old) {
    super.didUpdateWidget(old);
    if (old.date != widget.date || old.memberId != widget.memberId) _loadWeight();
  }

  Future<void> _loadWeight() async {
    try {
      final params = <String, String>{'days': '90'};
      if (widget.memberId != null) params['member_id'] = '${widget.memberId}';
      final r = await widget.api.get('/diary/weight/', params: params);
      if (!mounted) return;
      String? found;
      for (final row in (r is List ? r : const [])) {
        if (row is Map && row['date'] == widget.date) found = '${row['weight_kg']}';
      }
      setState(() => _weight = found);
    } catch (_) {
      if (mounted) setState(() => _weight = null);
    }
  }

  /// Съеденное за приём. Считается из тех же записей, что показаны на вкладке
  /// «Приёмы»: отдельный запрос за суммой означал бы, что она может разойтись
  /// с тем, что видно.
  double _eatenIn(MealSlot slot) => widget.entries
      .where((e) => e.mealSlot == slot && e.isEaten)
      .fold(0.0, (sum, e) => sum + e.calories);

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final eaten = widget.stats.actual.calories;
    final planned = widget.stats.planned.calories;
    final target = widget.calorieTarget;

    return ListView(
      key: const PageStorageKey('diary-summary'),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 96),
      children: [
        _card(
          context,
          child: target == null
              ? _noTarget(context, eaten)
              : _ring(context, eaten: eaten, target: target.toDouble()),
        ),
        _card(
          context,
          title: 'Белки, жиры, углеводы',
          child: Column(
            children: [
              _macroLine(context, 'Белки', 'proteins', widget.stats.actual.proteins,
                  widget.stats.planned.proteins, widget.proteinTarget, _proteinColor),
              _macroLine(context, 'Жиры', 'fats', widget.stats.actual.fats,
                  widget.stats.planned.fats, widget.fatTarget, _fatColor),
              _macroLine(context, 'Углеводы', 'carbs', widget.stats.actual.carbs,
                  widget.stats.planned.carbs, widget.carbTarget, _carbColor),
            ],
          ),
        ),
        _card(
          context,
          title: 'По приёмам',
          child: Column(children: _mealRows(context)),
        ),
        _card(
          context,
          title: 'Прочее за день',
          child: Row(
            children: [
              _tile(context, 'Вода', widget.waterMl == 0 ? '—' : '${_thousands(widget.waterMl)} мл'),
              const SizedBox(width: 10),
              _tile(context, 'Вес', _weight == null ? '—' : '$_weight кг'),
              const SizedBox(width: 10),
              // Потраченное на занятиях. Отдельной плиткой и без знака
              // «минус»: на остаток калорий оно не влияет.
              _tile(context, 'Потрачено',
                  widget.stats.burned == 0 ? '—' : '${_thousands(widget.stats.burned)} ккал'),
            ],
          ),
        ),
        if (planned > eaten)
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 2, 4, 0),
            child: Text(
              'Бледным — запланированное, но ещё не отмеченное съеденным.',
              style: TextStyle(fontSize: 11, color: t.textSecondary),
            ),
          ),
      ],
    );
  }

  Widget _card(BuildContext context, {String? title, required Widget child}) {
    final t = context.tokens;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (title != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  title.toUpperCase(),
                  style: TextStyle(
                    fontSize: 11,
                    letterSpacing: 0.5,
                    fontWeight: FontWeight.w700,
                    color: t.textSecondary,
                  ),
                ),
              ),
            child,
          ],
        ),
      ),
    );
  }

  /// Кольцо «съедено из нормы» и остаток.
  Widget _ring(BuildContext context, {required double eaten, required double target}) {
    final t = context.tokens;
    final left = target - eaten;
    final pct = target <= 0 ? 0 : (eaten / target * 100).round();
    return Row(
      children: [
        SizedBox(
          width: 92,
          height: 92,
          child: CustomPaint(
            painter: _RingPainter(
              ratio: target <= 0 ? 0 : (eaten / target).clamp(0.0, 1.0),
              // Перебор показываем цветом, а не полосой длиннее круга: круг
              // всё равно замкнётся, и человек решит, что всё ровно.
              color: eaten > target ? context.tokens.accent : context.cs.primary,
              track: context.tokens.border,
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('$pct%',
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                  Text('от цели', style: TextStyle(fontSize: 10, color: t.textSecondary)),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 14),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_thousands(eaten.round()),
                style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700, height: 1.1)),
            Text('съедено из ${_thousands(target.round())} ккал',
                style: TextStyle(fontSize: 12, color: t.textSecondary)),
          ],
        ),
        const Spacer(),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              left >= 0 ? _thousands(left.round()) : '+${_thousands((-left).round())}',
              style: TextStyle(
                fontSize: 21,
                fontWeight: FontWeight.w700,
                color: left >= 0 ? context.cs.primary : t.accent,
              ),
            ),
            Text(left >= 0 ? 'осталось' : 'перебор',
                style: TextStyle(fontSize: 12, color: t.textSecondary)),
          ],
        ),
      ],
    );
  }

  /// Нормы нет — вместо кольца приглашение её посчитать.
  ///
  /// Съеденное всё равно показываем: это честное число, и оно не зависит от
  /// нормы. Нарисовать же кольцо «74 %» от выдуманных двух тысяч нельзя.
  Widget _noTarget(BuildContext context, double eaten) {
    final t = context.tokens;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(_thousands(eaten.round()),
                style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700, height: 1.1)),
            const SizedBox(width: 6),
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Text('ккал съедено', style: TextStyle(fontSize: 12, color: t.textSecondary)),
            ),
          ],
        ),
        const SizedBox(height: 2),
        Text('Цель по калориям не задана — не с чем сравнивать.',
            style: TextStyle(fontSize: 12, color: t.textSecondary)),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: widget.onCalcTarget,
            icon: const Icon(Icons.calculate_outlined, size: 18),
            label: const Text('Посчитать'),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              visualDensity: VisualDensity.compact,
            ),
          ),
        ),
      ],
    );
  }

  /// Строка макроса: граммы к норме, доля калорий и полоса с бледным планом.
  Widget _macroLine(
    BuildContext context,
    String label,
    String key,
    double actual,
    double planned,
    double? target,
    Color color,
  ) {
    final t = context.tokens;
    // Доля калорий — от съеденного: вопрос «чего в рационе больше» не зависит
    // от того, задана ли норма.
    final a = widget.stats.actual;
    final totalKcal = a.proteins * _kcalPerGram['proteins']! +
        a.fats * _kcalPerGram['fats']! +
        a.carbs * _kcalPerGram['carbs']!;
    final share = totalKcal <= 0 ? null : (actual * _kcalPerGram[key]! / totalKcal * 100).round();
    // Полоса мерится нормой, если она есть; иначе планом — хоть какой-то
    // масштаб. Нет ни того, ни другого — полоса просто пустая.
    final scale = (target != null && target > 0) ? target : (planned > 0 ? planned : 0.0);

    return Padding(
      padding: const EdgeInsets.only(top: 9),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              SizedBox(width: 78, child: Text(label, style: const TextStyle(fontSize: 13))),
              if (share != null)
                Text('$share% калорий', style: TextStyle(fontSize: 12, color: t.textSecondary)),
              const Spacer(),
              Text(
                target == null
                    ? '${_g(actual)} г'
                    : '${_g(actual)} / ${_g(target)} г',
                style: TextStyle(fontSize: 12, color: t.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 5),
          _twoLayerBar(
            context,
            actual: actual,
            planned: planned,
            scale: scale,
            color: color,
          ),
        ],
      ),
    );
  }

  /// Полоса в два слоя: бледным — запланированное, плотным — съеденное.
  Widget _twoLayerBar(
    BuildContext context, {
    required double actual,
    required double planned,
    required double scale,
    required Color color,
  }) {
    double part(double v) => scale <= 0 ? 0 : (v / scale).clamp(0.0, 1.0);
    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: SizedBox(
        height: 7,
        child: Stack(
          children: [
            Positioned.fill(child: ColoredBox(color: context.tokens.border)),
            FractionallySizedBox(
              widthFactor: part(math.max(actual, planned)),
              child: ColoredBox(color: color.withValues(alpha: 0.28)),
            ),
            FractionallySizedBox(
              widthFactor: part(actual),
              child: ColoredBox(color: color),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _mealRows(BuildContext context) {
    final t = context.tokens;
    final slots = MealSlot.forPlan(widget.mealPlanType).toSet()
      ..addAll(widget.entries.map((e) => e.mealSlot));
    final ordered = MealSlot.values.where(slots.contains).toList();
    final values = {for (final s in ordered) s: _eatenIn(s)};
    final top = values.values.fold<double>(0, math.max);

    return [
      for (final s in ordered)
        Padding(
          padding: const EdgeInsets.only(top: 9),
          child: Row(
            children: [
              SizedBox(width: 86, child: Text(s.label, style: const TextStyle(fontSize: 13))),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: SizedBox(
                    height: 8,
                    child: Stack(
                      children: [
                        Positioned.fill(child: ColoredBox(color: t.border)),
                        FractionallySizedBox(
                          // Масштаб — самый крупный приём дня: так видно, где
                          // перебрал, а норма на один приём нам неизвестна.
                          widthFactor: top <= 0 ? 0 : (values[s]! / top).clamp(0.0, 1.0),
                          child: ColoredBox(color: context.cs.primary),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              SizedBox(
                width: 74,
                child: Text(
                  values[s]! <= 0 ? '—' : '${_thousands(values[s]!.round())} ккал',
                  textAlign: TextAlign.right,
                  style: TextStyle(fontSize: 12, color: t.textSecondary),
                ),
              ),
            ],
          ),
        ),
    ];
  }

  Widget _tile(BuildContext context, String title, String value) {
    final t = context.tokens;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 9),
        decoration: BoxDecoration(
          color: t.surfaceAlt,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TextStyle(fontSize: 11, color: t.textSecondary)),
            const SizedBox(height: 3),
            Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

  static String _g(double v) => v >= 10 ? v.round().toString() : v.toStringAsFixed(1);

  /// Тысячи с узким пробелом: «1 480» читается быстрее, чем «1480».
  static String _thousands(int v) {
    final s = v.abs().toString();
    final buf = StringBuffer(v < 0 ? '−' : '');
    for (var i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) buf.write(' ');
      buf.write(s[i]);
    }
    return buf.toString();
  }
}

class _RingPainter extends CustomPainter {
  final double ratio;
  final Color color;
  final Color track;
  _RingPainter({required this.ratio, required this.color, required this.track});

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 11.0;
    final rect = Offset(stroke / 2, stroke / 2) & Size(size.width - stroke, size.height - stroke);
    canvas.drawArc(
      rect,
      0,
      2 * math.pi,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..color = track,
    );
    canvas.drawArc(
      rect,
      -math.pi / 2,
      2 * math.pi * ratio.clamp(0.0, 1.0),
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.round
        ..color = color,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.ratio != ratio || old.color != color || old.track != track;
}
