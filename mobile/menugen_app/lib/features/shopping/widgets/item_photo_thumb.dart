// MG_SHOPIMG: миниатюра фото товара в списке покупок.
//
// Фото прикладывают, чтобы показать другому человеку, что именно купить —
// конкретную упаковку, сорт, бренд. Раньше в списке оно было размером 30 пикселей
// и ни на что не реагировало: рассмотреть прикреплённое фото было негде.
// Открыть его можно было только через редактор заметки, да и то лишь тому, у
// кого есть права на изменение списка.
//
// Теперь по нажатию открывается полноэкранный просмотр с масштабированием —
// тот же, что у фото рецепта.
import 'package:flutter/material.dart';

import '../../../core/widgets/full_image_viewer.dart';

class ItemPhotoThumb extends StatelessWidget {
  final String url;
  final double size;

  const ItemPhotoThumb({super.key, required this.url, this.size = 36});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Фото товара',
      button: true,
      child: InkWell(
        onTap: () => FullImageViewer.open(context, url),
        borderRadius: BorderRadius.circular(6),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: Image.network(
            url,
            width: size,
            height: size,
            fit: BoxFit.cover,
            // Битую ссылку не прячем: пустое место выглядит как «фото нет», и
            // человек будет искать его снова. Значок сразу говорит, что фото
            // есть, но не загрузилось.
            errorBuilder: (_, __, ___) => Container(
              width: size,
              height: size,
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              child: const Icon(Icons.broken_image_outlined, size: 18, color: Colors.grey),
            ),
          ),
        ),
      ),
    );
  }
}
