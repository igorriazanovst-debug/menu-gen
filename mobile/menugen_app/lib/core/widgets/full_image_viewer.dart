// MG_PHOTOZOOM: полноэкранный просмотр изображения с масштабированием.
//
// Был приватным классом внутри карточки рецепта. Понадобился второй раз — для
// фото товара в списке покупок, — поэтому вынесен сюда: два одинаковых
// просмотрщика разошлись бы по поведению (жесты, кнопка закрытия, заглушка при
// битой ссылке), а пользователь ждёт от «нажал на фото» одного и того же везде.
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';

class FullImageViewer extends StatelessWidget {
  final String url;

  /// Отдельное хранилище кэша: фото рецептов живут дольше и отдельно от прочих.
  final BaseCacheManager? cacheManager;

  const FullImageViewer({super.key, required this.url, this.cacheManager});

  /// Открывает просмотрщик поверх текущего экрана.
  static Future<void> open(BuildContext context, String url, {BaseCacheManager? cacheManager}) {
    return Navigator.of(context).push(
      PageRouteBuilder(
        opaque: false,
        barrierColor: Colors.black,
        pageBuilder: (_, __, ___) => FullImageViewer(url: url, cacheManager: cacheManager),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onTap: () => Navigator.of(context).maybePop(),
        child: Stack(
          children: [
            Positioned.fill(
              child: InteractiveViewer(
                minScale: 1,
                maxScale: 5,
                child: Center(
                  child: CachedNetworkImage(
                    imageUrl: url,
                    cacheManager: cacheManager,
                    fit: BoxFit.contain,
                    placeholder: (_, __) => const Center(
                      child: CircularProgressIndicator(color: Colors.white),
                    ),
                    errorWidget: (_, __, ___) => const Center(
                      child: Icon(Icons.broken_image, color: Colors.white54, size: 64),
                    ),
                  ),
                ),
              ),
            ),
            Positioned(
              top: MediaQuery.of(context).padding.top + 8,
              right: 8,
              child: IconButton(
                icon: const Icon(Icons.close, color: Colors.white, size: 30),
                onPressed: () => Navigator.of(context).maybePop(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
