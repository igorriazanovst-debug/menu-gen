// MG_INGROW: строка ингредиента в карточке рецепта.
//
// Раньше количество было обычным Text в Row: такой элемент получает
// неограниченную ширину, не переносится и при длинном значении («2 стакана
// (или 300 г)») вылезал за край — Flutter рисовал «RIGHT OVERFLOWED BY N PIXELS»
// и строка разъезжалась.
//
// Теперь количество ограничено долей ширины строки и переносится внутри неё,
// а название занимает всё остальное. Доля берётся от фактической ширины через
// LayoutBuilder, а не от ширины экрана: строка живёт внутри отступов карточки.
import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Какую часть строки максимум занимает количество.
const _amountMaxFraction = 0.4;

class RecipeIngredientRow extends StatelessWidget {
  final String name;
  final String amount;

  const RecipeIngredientRow({super.key, required this.name, this.amount = ''});

  /// Собирает подпись количества из полей ингредиента: «300 г», «2 шт».
  static String amountOf(Map<String, dynamic> ingredient) {
    final qty = ingredient['quantity']?.toString().trim() ?? '';
    final unit = (ingredient['unit'] as String?)?.trim() ?? '';
    return [qty, unit].where((s) => s.isNotEmpty).join(' ');
  }

  @override
  Widget build(BuildContext context) {
    final cs = context.cs;
    final tokens = context.tokens;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: tokens.surfaceAlt,
        borderRadius: BorderRadius.circular(14),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) => Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: cs.secondary, shape: BoxShape.circle),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                name,
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: cs.onSurface),
              ),
            ),
            if (amount.isNotEmpty) ...[
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: BoxConstraints(maxWidth: constraints.maxWidth * _amountMaxFraction),
                child: Text(
                  amount,
                  textAlign: TextAlign.end,
                  style: TextStyle(fontSize: 14, color: tokens.textSecondary),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
