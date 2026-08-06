// MG_NOOVERFLOW: строка «иконка + подпись», которая не вылезает за край.
//
// Образец повторялся в карточке рецепта, карусели меню и плитке рецепта: Row с
// Icon и обычным Text. Такой Text получает в Row неограниченную ширину, не
// переносится и при длинном значении («1 час 30 минут в мультиварке») выдавливал
// строку наружу — Flutter рисовал «RIGHT OVERFLOWED BY N PIXELS».
//
// Здесь подпись обёрнута в Flexible и обрезается многоточием: строка всегда
// умещается, а лишнее видно по «…».
import 'package:flutter/material.dart';

class IconLabel extends StatelessWidget {
  final IconData icon;
  final String text;
  final double iconSize;
  final double gap;
  final TextStyle? style;
  final Color? iconColor;

  const IconLabel({
    super.key,
    required this.icon,
    required this.text,
    this.iconSize = 16,
    this.gap = 4,
    this.style,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: iconSize, color: iconColor),
        SizedBox(width: gap),
        Flexible(
          child: Text(text, style: style, maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
      ],
    );
  }
}
