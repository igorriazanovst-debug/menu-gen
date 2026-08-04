// MG_GALLERY: сбор фото рецепта и листание тапом по краям.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/recipes/widgets/recipe_gallery.dart';

const _photos = [
  RecipePhoto('https://menugen.ru/media/cover.png'),
  RecipePhoto('https://menugen.ru/media/side.png', caption: 'Вид сбоку'),
  RecipePhoto('https://menugen.ru/media/cut.png'),
];

Future<void> _pump(
  WidgetTester tester,
  List<RecipePhoto> photos, {
  void Function(RecipePhoto)? onZoom,
}) async {
  await tester.pumpWidget(MaterialApp(
    // Виджет берёт цвета из скин-токенов — нужна настоящая тема приложения.
    theme: AppTheme.light(),
    home: Scaffold(
      body: SizedBox(
        width: 400,
        height: 250,
        child: RecipeGallery(photos: photos, onZoom: onZoom),
      ),
    ),
  ));
  await tester.pump();
}

void main() {
  group('collectRecipePhotos', () {
    test('обложка первая, затем галерея по порядку', () {
      final photos = collectRecipePhotos({
        'image_url': '/media/cover.png',
        'gallery': [
          {'id': 1, 'url': '/media/a.png', 'caption': 'A'},
          {'id': 2, 'url': '/media/b.png'},
        ],
      });

      expect(photos.map((p) => p.url).toList(), ['/media/cover.png', '/media/a.png', '/media/b.png']);
      expect(photos[1].caption, 'A');
      expect(photos[2].caption, isNull);
    });

    test('дубль обложки в галерее отбрасывается', () {
      final photos = collectRecipePhotos({
        'image_url': '/media/cover.png',
        'gallery': [
          {'id': 1, 'url': '/media/cover.png'},
        ],
      });

      expect(photos, hasLength(1));
    });

    test('пустые адреса и подписи не ломают список', () {
      final photos = collectRecipePhotos({
        'image_url': '   ',
        'gallery': [
          {'id': 1, 'url': ''},
          {'id': 2, 'url': '/media/ok.png', 'caption': '  '},
        ],
      });

      expect(photos, hasLength(1));
      expect(photos.single.caption, isNull);
    });

    test('рецепт без фото даёт пустой список', () {
      expect(collectRecipePhotos(null), isEmpty);
      expect(collectRecipePhotos(const {}), isEmpty);
    });
  });

  group('RecipeGallery', () {
    testWidgets('без фото показывает заглушку, а не пустоту', (tester) async {
      await _pump(tester, const []);

      expect(find.byIcon(Icons.restaurant), findsOneWidget);
      expect(find.byType(PageView), findsNothing);
    });

    testWidgets('при одном фото счётчика и точек нет', (tester) async {
      await _pump(tester, const [_photos_single]);

      expect(find.textContaining('/'), findsNothing);
    });

    testWidgets('тап справа листает вперёд, слева — назад', (tester) async {
      await _pump(tester, _photos);
      final gallery = find.byType(RecipeGallery);

      expect(find.text('1 / 3'), findsOneWidget);

      // правая треть
      await tester.tapAt(tester.getCenter(gallery) + const Offset(160, 0));
      await tester.pumpAndSettle();
      expect(find.text('2 / 3'), findsOneWidget);

      // левая треть
      await tester.tapAt(tester.getCenter(gallery) - const Offset(160, 0));
      await tester.pumpAndSettle();
      expect(find.text('1 / 3'), findsOneWidget);
    });

    testWidgets('листание закольцовано', (tester) async {
      await _pump(tester, _photos);
      final gallery = find.byType(RecipeGallery);

      await tester.tapAt(tester.getCenter(gallery) - const Offset(160, 0));
      await tester.pumpAndSettle();

      expect(find.text('3 / 3'), findsOneWidget);
    });

    testWidgets('подпись показывается только у своего фото', (tester) async {
      await _pump(tester, _photos);
      final gallery = find.byType(RecipeGallery);

      expect(find.text('Вид сбоку'), findsNothing);

      await tester.tapAt(tester.getCenter(gallery) + const Offset(160, 0));
      await tester.pumpAndSettle();

      expect(find.text('Вид сбоку'), findsOneWidget);
    });

    testWidgets('тап по середине открывает текущее фото', (tester) async {
      final zoomed = <RecipePhoto>[];
      await _pump(tester, _photos, onZoom: zoomed.add);
      final gallery = find.byType(RecipeGallery);

      await tester.tapAt(tester.getCenter(gallery) + const Offset(160, 0));
      await tester.pumpAndSettle();
      await tester.tapAt(tester.getCenter(gallery));
      await tester.pumpAndSettle();

      expect(zoomed.single.url, _photos[1].url);
    });

    testWidgets('свайп тоже листает', (tester) async {
      await _pump(tester, _photos);

      await tester.drag(find.byType(PageView), const Offset(-300, 0));
      await tester.pumpAndSettle();

      expect(find.text('2 / 3'), findsOneWidget);
    });
  });
}

const _photos_single = RecipePhoto('https://menugen.ru/media/only.png');
