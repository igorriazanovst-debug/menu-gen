// MG_NUTRIDETAIL: карточка настройки «сколько чисел показывать».
//
// Стоит в профиле рядом с оформлением, а не в самом дневнике: это настройка
// на всё приложение (дневник, меню, рецепты, подсказки при добавлении), и
// место ей там же, где остальные настройки отображения.
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../theme/app_theme.dart';
import 'food_text_scale.dart';
import 'nutrition_detail.dart';
import 'nutrition_detail_cubit.dart';

class NutritionDetailCard extends StatelessWidget {
  const NutritionDetailCard({super.key});

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Числа в списках еды',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              'Дневник, меню, рецепты и подсказки при добавлении. '
              'Настройка синхронизируется с веб-версией через ваш аккаунт.',
              style: TextStyle(fontSize: 12, color: t.textSecondary),
            ),
            const SizedBox(height: 12),
            BlocBuilder<DisplayPrefsCubit, DisplayPrefs>(
              builder: (context, current) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SegmentedButton<NutritionDetail>(
                    segments: [
                      for (final d in NutritionDetail.values)
                        ButtonSegment(value: d, label: Text(d.label)),
                    ],
                    selected: {current.detail},
                    showSelectedIcon: false,
                    onSelectionChanged: (v) =>
                        context.read<DisplayPrefsCubit>().setDetail(v.first),
                  ),
                  const SizedBox(height: 10),
                  // Что именно изменится — словами и примером. «Кратко» и
                  // «подробно» сами по себе не говорят, чего станет меньше, а
                  // проверять это, переключая и уходя в дневник, — лишний путь.
                  Text(current.detail.hint, style: TextStyle(fontSize: 12, color: t.textSecondary)),
                  const SizedBox(height: 10),
                  // MG_FOODSCALE: размер шрифта — рядом, потому что это об
                  // одном и том же: как читается список еды.
                  const Text('Размер шрифта',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  SegmentedButton<FoodTextScale>(
                    segments: [
                      for (final sc in FoodTextScale.values)
                        ButtonSegment(value: sc, label: Text(sc.label)),
                    ],
                    selected: {current.scale},
                    showSelectedIcon: false,
                    onSelectionChanged: (v) =>
                        context.read<DisplayPrefsCubit>().setScale(v.first),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Умножается на системный размер шрифта, а не заменяет его.',
                    style: TextStyle(fontSize: 12, color: t.textSecondary),
                  ),
                  const SizedBox(height: 8),
                  _Preview(detail: current.detail, scale: current.scale),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Строка-образец: ровно так запись выглядит в дневнике при этом выборе.
class _Preview extends StatelessWidget {
  final NutritionDetail detail;
  final FoodTextScale scale;
  const _Preview({required this.detail, required this.scale});

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final sub = [
      if (detail.showGrams) '250 г',
      if (detail.showMacros) macrosShort(proteins: 12, fats: 8, carbs: 30),
    ].where((e) => e.isNotEmpty).join(' · ');

    // Образец показывается тем же размером, что выбран: иначе проверять
    // настройку пришлось бы, уходя в дневник и обратно.
    final media = MediaQuery.of(context);
    return MediaQuery(
      data: media.copyWith(
        textScaler: TextScaler.linear(media.textScaler.scale(1) * scale.factor),
      ),
      child: Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: t.surfaceAlt,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Овсянка на молоке',
                    maxLines: 1, overflow: TextOverflow.ellipsis),
                if (sub.isNotEmpty)
                  Text(sub,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 12, color: t.textSecondary)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text('412 ккал',
              style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600, color: context.cs.primary)),
        ],
      ),
      ),
    );
  }
}
