// MG_BODYCHART: график веса по точкам замеров.
//
// Рисуется CustomPainter'ом, без библиотеки графиков: линия одна, точек
// десятки, а пакет ради этого тянуть незачем — он весит больше, чем весь экран
// дневника.
//
// MG_CHARTAXES: у первой версии не было ни осей, ни чисел — только линия. По
// такой картинке видно «вниз или вверх», но не видно ни насколько, ни когда.
// Теперь есть шкала слева (килограммы), шкала снизу (даты), числа у крайних
// точек и подпись сверху с разницей за период.
//
// Ось Y не начинается с нуля: вес меняется на проценты, и на шкале от нуля
// линия была бы прямой при любой динамике. Чтобы это не вводило в заблуждение,
// подписи слева показывают настоящие килограммы.
//
// По оси X точки расставлены равномерно, по номеру, а не по календарю: замеры
// делают неравномерно, и перерыв в две недели не должен съедать половину
// картинки. Даты под шкалой показывают, какому дню какая точка.
import 'package:flutter/material.dart';

class WeightPoint {
  final String date; // YYYY-MM-DD
  final double kg;
  const WeightPoint(this.date, this.kg);
}

String _fmtDate(String iso) =>
    iso.length >= 10 ? '${iso.substring(8, 10)}.${iso.substring(5, 7)}' : iso;

String _fmtKg(double v) =>
    v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);

class WeightChart extends StatelessWidget {
  /// Замеры в порядке возрастания даты.
  final List<WeightPoint> points;
  final Color color;
  const WeightChart({super.key, required this.points, required this.color});

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Для графика нужно хотя бы два замера — сделайте ещё один в другой день.',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
      );
    }
    final first = points.first;
    final last = points.last;
    final delta = double.parse((last.kg - first.kg).toStringAsFixed(1));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Легенда: что за линия, за какой период и куда сдвинулся вес.
        Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            children: [
              Container(width: 12, height: 2, color: color),
              const SizedBox(width: 6),
              Text('Вес, кг', style: TextStyle(fontSize: 11, color: Colors.grey.shade700)),
              const SizedBox(width: 8),
              Text('${_fmtDate(first.date)} — ${_fmtDate(last.date)}',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
              if (delta != 0) ...[
                const SizedBox(width: 8),
                Text(
                  '${delta > 0 ? '+' : '−'}${_fmtKg(delta.abs())} кг за период',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                ),
              ],
            ],
          ),
        ),
        SizedBox(
          height: 140,
          width: double.infinity,
          child: CustomPaint(
            painter: _WeightPainter(
              points: points,
              color: color,
              textColor: Theme.of(context).colorScheme.onSurface,
            ),
          ),
        ),
      ],
    );
  }
}

class _WeightPainter extends CustomPainter {
  final List<WeightPoint> points;
  final Color color;
  final Color textColor;
  _WeightPainter({required this.points, required this.color, required this.textColor});

  static const double padL = 34; // место под килограммы
  static const double padR = 8;
  static const double padT = 12;
  static const double padB = 20; // место под даты

  @override
  void paint(Canvas canvas, Size size) {
    final values = points.map((p) => p.kg).toList();
    final min = values.reduce((a, b) => a < b ? a : b);
    final max = values.reduce((a, b) => a > b ? a : b);
    // Плоский участок (все замеры равны) обнулил бы делитель; поле в 15%
    // держит линию посередине, а не по краю картинки.
    final span = (max - min) == 0 ? 1.0 : (max - min);
    final lo = min - span * 0.15;
    final hi = max + span * 0.15;
    final mid = (lo + hi) / 2;

    double dx(int i) => padL + i * (size.width - padL - padR) / (points.length - 1);
    double dy(double v) => padT + (hi - v) * (size.height - padT - padB) / (hi - lo);

    final grid = Paint()
      ..color = const Color(0xFFE7DDD3)
      ..strokeWidth = 1;
    final axis = Paint()
      ..color = const Color(0xFFD9C3B0)
      ..strokeWidth = 1;

    for (final kg in [hi, mid, lo]) {
      _dashed(canvas, Offset(padL, dy(kg)), Offset(size.width - padR, dy(kg)), grid);
      _text(canvas, _fmtKg(kg), Offset(padL - 6, dy(kg) - 6),
          const Color(0xFF8A7568), align: TextAlign.right, width: 30);
    }
    canvas.drawLine(Offset(padL, padT - 4), Offset(padL, size.height - padB), axis);
    canvas.drawLine(
        Offset(padL, size.height - padB), Offset(size.width - padR, size.height - padB), axis);

    final path = Path()..moveTo(dx(0), dy(values.first));
    for (var i = 1; i < points.length; i++) {
      path.lineTo(dx(i), dy(values[i]));
    }

    final fill = Path.from(path)
      ..lineTo(dx(points.length - 1), size.height - padB)
      ..lineTo(dx(0), size.height - padB)
      ..close();
    canvas.drawPath(fill, Paint()..color = color.withValues(alpha: 0.08));

    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round,
    );

    final dot = Paint()..color = color;
    for (var i = 0; i < points.length; i++) {
      canvas.drawCircle(Offset(dx(i), dy(values[i])), i == points.length - 1 ? 3.5 : 2.5, dot);
    }

    // Числа у крайних точек: с них начинают читать график, и наводить курсор в
    // приложении не на что — подсказок тут нет.
    _text(canvas, _fmtKg(values.first), Offset(dx(0) + 4, dy(values.first) - 16), textColor);
    _text(canvas, _fmtKg(values.last), Offset(dx(points.length - 1) - 34, dy(values.last) - 16),
        textColor, align: TextAlign.right, width: 32);

    // Даты под осью: первая, середина и последняя — больше на ширине телефона
    // не помещается, а частокол подписей читается хуже, чем их отсутствие.
    final ticks = points.length >= 4
        ? [0, (points.length - 1) ~/ 2, points.length - 1]
        : [0, points.length - 1];
    for (var n = 0; n < ticks.length; n++) {
      final i = ticks[n];
      final label = _fmtDate(points[i].date);
      final left = n == 0
          ? dx(i)
          : (n == ticks.length - 1 ? dx(i) - 34 : dx(i) - 17);
      _text(canvas, label, Offset(left, size.height - padB + 4), const Color(0xFF8A7568),
          align: n == 0
              ? TextAlign.left
              : (n == ticks.length - 1 ? TextAlign.right : TextAlign.center),
          width: 34);
    }
  }

  void _dashed(Canvas canvas, Offset a, Offset b, Paint paint) {
    const dash = 3.0;
    const gap = 3.0;
    final total = (b - a).distance;
    if (total <= 0) return;
    final dir = (b - a) / total;
    var t = 0.0;
    while (t < total) {
      final end = (t + dash).clamp(0.0, total);
      canvas.drawLine(a + dir * t, a + dir * end, paint);
      t = end + gap;
    }
  }

  void _text(Canvas canvas, String text, Offset at, Color color,
      {TextAlign align = TextAlign.left, double width = 40}) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: 10, color: color)),
      textDirection: TextDirection.ltr,
      textAlign: align,
    )..layout(maxWidth: width);
    // При выравнивании вправо/по центру TextPainter сам не сдвигает текст,
    // поэтому позиция уже посчитана вызывающим кодом с учётом ширины.
    tp.paint(canvas, at);
  }

  @override
  bool shouldRepaint(covariant _WeightPainter old) =>
      old.points != points || old.color != color;
}
