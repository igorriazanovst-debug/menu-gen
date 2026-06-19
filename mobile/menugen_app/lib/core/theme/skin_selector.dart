import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'app_skin.dart';
import 'app_theme.dart';
import 'theme_cubit.dart';

// MG_SKIN: карточка выбора скина оформления (синкается через аккаунт).
class SkinSelectorCard extends StatelessWidget {
  const SkinSelectorCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Оформление',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            const Text(
              'Скин синхронизируется с веб-версией через ваш аккаунт.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 12),
            BlocBuilder<ThemeCubit, AppSkin>(
              builder: (context, current) => Row(
                children: [
                  for (final skin in AppSkin.values) ...[
                    Expanded(
                      child: _SkinOption(
                        skin: skin,
                        selected: current == skin,
                        onTap: () => context.read<ThemeCubit>().setSkin(skin),
                      ),
                    ),
                    if (skin != AppSkin.values.last) const SizedBox(width: 8),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SkinOption extends StatelessWidget {
  final AppSkin skin;
  final bool selected;
  final VoidCallback onTap;

  const _SkinOption({
    required this.skin,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final p = paletteForSkin(skin);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? p.primary.withOpacity(0.08) : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? p.primary : const Color(0xFFE0E0E0),
            width: selected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Flexible(
                  child: Text(
                    skin.label,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (selected)
                  Icon(Icons.check_circle, size: 16, color: p.primary),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _swatch(p.primary),
                _swatch(p.secondary),
                _swatch(p.accent),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _swatch(Color c) => Container(
        width: 18,
        height: 18,
        margin: const EdgeInsets.only(right: 6),
        decoration: BoxDecoration(
          color: c,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.black.withOpacity(0.05)),
        ),
      );
}
