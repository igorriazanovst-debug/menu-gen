// MG_BODYSIZE: контур тела с обхватами.
//
// Зачем картинка, а не пять строк с числами. Числа отвечают на вопрос
// «сколько», но не на вопрос «где»: на контуре сразу видно, какая линия куда
// идёт, и грудь не путается с подгрудной. Рядом с каждой линией — изменение с
// прошлого замера, и вся картина («талия ушла, бёдра стоят») читается одним
// взглядом.
//
// Силуэт мужской или женский — по полу из профиля; пол не указан — нейтральный.
// Разница только в фигуре: линии и подписи одни и те же.
import 'package:flutter/material.dart';

/// Обхваты в сантиметрах. null — не мерили, линия не рисуется.
class BodySizes {
  final double? neck;
  final double? chest;
  final double? underBust;
  final double? waist;
  final double? hips;
  const BodySizes({this.neck, this.chest, this.underBust, this.waist, this.hips});

  bool get isEmpty => neck == null && chest == null && underBust == null && waist == null && hips == null;

  // Сравнение по значениям: перерисовывать контур надо, когда изменились
  // замеры, а не когда родитель пересобрал список.
  @override
  bool operator ==(Object other) =>
      other is BodySizes &&
      other.neck == neck &&
      other.chest == chest &&
      other.underBust == underBust &&
      other.waist == waist &&
      other.hips == hips;

  @override
  int get hashCode => Object.hash(neck, chest, underBust, waist, hips);
}

enum BodyShape { male, female, neutral }

BodyShape bodyShapeFromGender(String? gender) {
  if (gender == 'male') return BodyShape.male;
  if (gender == 'female') return BodyShape.female;
  return BodyShape.neutral;
}

class BodyOutline extends StatelessWidget {
  final BodySizes sizes;
  final BodySizes? previous;
  final BodyShape shape;
  final Color accent;
  const BodyOutline({
    super.key,
    required this.sizes,
    required this.shape,
    required this.accent,
    this.previous,
  });

  @override
  Widget build(BuildContext context) {
    if (sizes.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Замеров пока нет — впишите хотя бы один обхват, и здесь появится контур.',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
      );
    }
    return SizedBox(
      height: 210,
      width: double.infinity,
      child: CustomPaint(
        painter: _OutlinePainter(
          sizes: sizes,
          previous: previous,
          shape: shape,
          accent: accent,
          textColor: Theme.of(context).colorScheme.onSurface,
        ),
      ),
    );
  }
}

class _Line {
  final String label;
  final double? value;
  final double? was;
  final double y; // доля высоты
  final double half; // доля ширины тела в каждую сторону
  const _Line(this.label, this.value, this.was, this.y, this.half);
}

class _OutlinePainter extends CustomPainter {
  final BodySizes sizes;
  final BodySizes? previous;
  final BodyShape shape;
  final Color accent;
  final Color textColor;
  _OutlinePainter({
    required this.sizes,
    required this.shape,
    required this.accent,
    required this.textColor,
    this.previous,
  });

  // Полуширина линии на каждом уровне — чтобы линия ложилась по контуру, а не
  // торчала за него. Женский силуэт уже в талии и шире в бёдрах, мужской
  // наоборот. Это рисунок, а не антропометрия: он подписан числами, и точность
  // пропорций ничего к нему не добавляет.
  List<double> get _halves {
    switch (shape) {
      case BodyShape.male:
        return [0.055, 0.165, 0.150, 0.135, 0.145];
      case BodyShape.female:
        return [0.048, 0.150, 0.125, 0.108, 0.160];
      case BodyShape.neutral:
        return [0.051, 0.156, 0.135, 0.120, 0.152];
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final halves = _halves;
    final lines = <_Line>[
      _Line('Шея', sizes.neck, previous?.neck, 0.20, halves[0]),
      _Line('Грудь', sizes.chest, previous?.chest, 0.34, halves[1]),
      _Line('Под грудью', sizes.underBust, previous?.underBust, 0.44, halves[2]),
      _Line('Талия', sizes.waist, previous?.waist, 0.55, halves[3]),
      _Line('Бёдра', sizes.hips, previous?.hips, 0.68, halves[4]),
    ];

    _paintBody(canvas, size, cx, halves);

    final dash = Paint()
      ..color = accent
      ..strokeWidth = 1.5;

    for (final line in lines) {
      if (line.value == null) continue;
      final y = size.height * line.y;
      final dx = size.width * line.half;
      _dashed(canvas, Offset(cx - dx, y), Offset(cx + dx, y), dash);

      _text(
        canvas,
        '${line.label} ${_fmt(line.value!)} см',
        Offset(cx + dx + 6, y - 6),
        textColor,
      );

      final was = line.was;
      if (was != null) {
        final delta = double.parse((line.value! - was).toStringAsFixed(1));
        if (delta != 0) {
          // Знак важнее цвета: «−2 см» на талии хорошо, а на груди у того, кто
          // набирает массу, — плохо, и решать это не картинке.
          final sign = delta > 0 ? '+' : '−';
          _text(
            canvas,
            '$sign${_fmt(delta.abs())}',
            Offset(cx - dx - 34, y - 6),
            Colors.grey.shade600,
          );
        }
      }
    }
  }

  String _fmt(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);

  void _paintBody(Canvas canvas, Size size, double cx, List<double> halves) {
    final body = Paint()..color = const Color(0xFFF5E7DC);
    final edge = Paint()
      ..color = const Color(0xFFD9C3B0)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    final h = size.height;
    // Голова отдельным кругом, туловище и ноги — одной фигурой по уровням
    // замеров: так контур сам собой согласован с линиями.
    canvas.drawCircle(Offset(cx, h * 0.09), h * 0.055, body);
    canvas.drawCircle(Offset(cx, h * 0.09), h * 0.055, edge);

    final w = size.width;
    final path = Path()
      ..moveTo(cx - w * halves[0], h * 0.17)
      ..lineTo(cx - w * halves[1], h * 0.30)
      ..lineTo(cx - w * halves[1], h * 0.36)
      ..lineTo(cx - w * halves[2], h * 0.45)
      ..lineTo(cx - w * halves[3], h * 0.56)
      ..lineTo(cx - w * halves[4], h * 0.68)
      ..lineTo(cx - w * halves[4] * 0.75, h * 0.98)
      ..lineTo(cx - w * 0.012, h * 0.98)
      ..lineTo(cx - w * 0.012, h * 0.74)
      ..lineTo(cx + w * 0.012, h * 0.74)
      ..lineTo(cx + w * 0.012, h * 0.98)
      ..lineTo(cx + w * halves[4] * 0.75, h * 0.98)
      ..lineTo(cx + w * halves[4], h * 0.68)
      ..lineTo(cx + w * halves[3], h * 0.56)
      ..lineTo(cx + w * halves[2], h * 0.45)
      ..lineTo(cx + w * halves[1], h * 0.36)
      ..lineTo(cx + w * halves[1], h * 0.30)
      ..lineTo(cx + w * halves[0], h * 0.17)
      ..close();
    canvas.drawPath(path, body);
    canvas.drawPath(path, edge);
  }

  void _dashed(Canvas canvas, Offset a, Offset b, Paint paint) {
    const dash = 4.0;
    const gap = 3.0;
    final total = (b - a).distance;
    final dir = (b - a) / total;
    var t = 0.0;
    while (t < total) {
      final end = (t + dash).clamp(0.0, total);
      canvas.drawLine(a + dir * t, a + dir * end, paint);
      t = end + gap;
    }
  }

  void _text(Canvas canvas, String text, Offset at, Color color) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: 11, color: color)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, at);
  }

  @override
  bool shouldRepaint(covariant _OutlinePainter old) =>
      old.sizes != sizes || old.previous != previous || old.shape != shape;
}
