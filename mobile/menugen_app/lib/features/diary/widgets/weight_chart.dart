// MG_BODYCHART: график веса по точкам замеров.
//
// Рисуется CustomPainter'ом, без библиотеки графиков: линия одна, точек
// десятки, а пакет ради этого тянуть незачем — он весит больше, чем весь экран
// дневника.
//
// Ось Y не начинается с нуля. Вес человека меняется на проценты, и на шкале от
// нуля линия выглядела бы идеально прямой — то есть график отвечал бы «ничего
// не происходит» на любой вопрос. Берём диапазон замеров и добавляем поля.
//
// По оси X точки расставлены равномерно, по номеру, а не по календарю: замеры
// делают неравномерно, и перерыв в две недели не должен съедать половину
// картинки. Календарная точность живёт в списке замеров под графиком.
import 'package:flutter/material.dart';

class WeightChart extends StatelessWidget {
  /// Пары «дата → вес», в порядке возрастания даты.
  final List<double> values;
  final Color color;
  const WeightChart({super.key, required this.values, required this.color});

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Для графика нужно хотя бы два замера — сделайте ещё один в другой день.',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
      );
    }
    return SizedBox(
      height: 90,
      width: double.infinity,
      child: CustomPaint(painter: _WeightPainter(values, color)),
    );
  }
}

class _WeightPainter extends CustomPainter {
  final List<double> values;
  final Color color;
  _WeightPainter(this.values, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    const padY = 10.0;
    final min = values.reduce((a, b) => a < b ? a : b);
    final max = values.reduce((a, b) => a > b ? a : b);
    // Плоский участок (все замеры равны) обнулил бы делитель; поле в 15%
    // держит линию посередине, а не по краю картинки.
    final span = (max - min) == 0 ? 1.0 : (max - min);
    final lo = min - span * 0.15;
    final hi = max + span * 0.15;

    double dx(int i) => i * size.width / (values.length - 1);
    double dy(double v) => padY + (hi - v) * (size.height - padY * 2) / (hi - lo);

    final path = Path()..moveTo(dx(0), dy(values.first));
    for (var i = 1; i < values.length; i++) {
      path.lineTo(dx(i), dy(values[i]));
    }

    final fill = Path.from(path)
      ..lineTo(dx(values.length - 1), size.height)
      ..lineTo(dx(0), size.height)
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
    for (var i = 0; i < values.length; i++) {
      canvas.drawCircle(Offset(dx(i), dy(values[i])), i == values.length - 1 ? 3.5 : 2, dot);
    }
  }

  @override
  bool shouldRepaint(covariant _WeightPainter old) =>
      old.values != values || old.color != color;
}
